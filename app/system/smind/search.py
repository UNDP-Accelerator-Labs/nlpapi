import hashlib
import re
import traceback
import uuid
from typing import get_args, Literal, Protocol, TypeAlias, TypedDict

import numpy as np
from qdrant_client import QdrantClient
from redipy import Redis
from scattermind.api.api import ScattermindAPI
from scattermind.system.names import GNamespace

from app.misc.util import (
    fmt_time,
    json_compact_str,
    json_maybe_read,
    parse_time_str,
    to_list,
)
from app.system.db.db import DBConnector
from app.system.language.pipeline import extract_language
from app.system.location.pipeline import extract_locations
from app.system.location.response import DEFAULT_MAX_REQUESTS, GeoQuery
from app.system.smind.api import (
    clear_redis,
    get_text_results_immediate,
    snippify_text,
)
from app.system.smind.log import log_query
from app.system.smind.vec import (
    add_embed,
    EmbedChunk,
    EmbedMain,
    ExternalKey,
    query_docs,
    query_embed_emu_filters,
    ResultChunk,
    stat_embed,
    stat_total,
    StatEmbed,
    vec_flushall,
)


class GetVecDB(Protocol):  # pylint: disable=too-few-public-methods
    def __call__(
            self,
            name: Literal["main", "test"],
            force_clear: bool,
            force_index: bool) -> str:
        ...


ClearResponse = TypedDict('ClearResponse', {
    "clear_rmain": bool,
    "clear_rdata": bool,
    "clear_rcache": bool,
    "clear_rbody": bool,
    "clear_rworker": bool,
    "clear_veccache": bool,
    "clear_vecdb_all": bool,
    "clear_vecdb_main": bool,
    "clear_vecdb_test": bool,
    "index_vecdb_main": bool,
    "index_vecdb_test": bool,
})
AddEmbed = TypedDict('AddEmbed', {
    "previous": int,
    "snippets": int,
    "failed": int,
})
QueryEmbed = TypedDict('QueryEmbed', {
    "hits": list[ResultChunk],
    "status": Literal["ok", "error"],
})


CHUNK_SIZE = 600
SMALL_CHUNK_SIZE = 150
CHUNK_PADDING = 10
DEFAULT_HIT_LIMIT = 3


DocStatus: TypeAlias = Literal["public", "preview"]
DOC_STATUS: tuple[DocStatus] = get_args(DocStatus)


KNOWN_DOC_TYPES: dict[str, set[str]] = {
    "actionplan": {"action plan"},
    "experiment": {"experiment"},
    "solution": {"solution"},
}
DOC_TYPE_TO_BASE: dict[str, str] = {
    doc_type: base
    for base, doc_types in KNOWN_DOC_TYPES.items()
    for doc_type in doc_types
}


def vec_clear(
        vec_db: QdrantClient,
        smind_config: str,
        *,
        qdrant_cache: Redis,
        get_vec_db: GetVecDB,
        clear_rmain: bool,
        clear_rdata: bool,
        clear_rcache: bool,
        clear_rbody: bool,
        clear_rworker: bool,
        clear_veccache: bool,
        clear_vecdb_main: bool,
        clear_vecdb_test: bool,
        clear_vecdb_all: bool,
        index_vecdb_main: bool,
        index_vecdb_test: bool) -> ClearResponse:
    if clear_vecdb_all and (not clear_vecdb_main or not clear_vecdb_test):
        raise ValueError(
            "clear_vecdb_all must have "
            "clear_vecdb_main and clear_vecdb_test")
    if clear_rmain:
        try:
            clear_redis(smind_config, "rmain")
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            clear_rmain = False
    if clear_rdata:
        try:
            clear_redis(smind_config, "rdata")
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            clear_rdata = False
    if clear_rcache:
        try:
            clear_redis(smind_config, "rcache")
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            clear_rcache = False
    if clear_rbody:
        try:
            clear_redis(smind_config, "rbody")
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            clear_rbody = False
    if clear_rworker:
        try:
            clear_redis(smind_config, "rworker")
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            clear_rworker = False
    if clear_veccache:
        try:
            qdrant_cache.flushall()
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            clear_veccache = False
    if clear_vecdb_all:
        try:
            vec_flushall(vec_db)
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            clear_vecdb_all = False
            clear_vecdb_main = False
            clear_vecdb_test = False
    if clear_vecdb_main:
        try:
            get_vec_db("main", force_clear=True, force_index=False)
            index_vecdb_main = False
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            clear_vecdb_main = False
    if clear_vecdb_test:
        try:
            get_vec_db("test", force_clear=True, force_index=False)
            index_vecdb_test = False
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            clear_vecdb_test = False
    if index_vecdb_main:
        try:
            get_vec_db("main", force_clear=False, force_index=True)
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            index_vecdb_main = False
    if index_vecdb_test:
        try:
            get_vec_db("test", force_clear=False, force_index=True)
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            index_vecdb_test = False
    return {
        "clear_rmain": clear_rmain,
        "clear_rdata": clear_rdata,
        "clear_rcache": clear_rcache,
        "clear_rbody": clear_rbody,
        "clear_rworker": clear_rworker,
        "clear_veccache": clear_veccache,
        "clear_vecdb_all": clear_vecdb_all,
        "clear_vecdb_main": clear_vecdb_main,
        "clear_vecdb_test": clear_vecdb_test,
        "index_vecdb_main": index_vecdb_main,
        "index_vecdb_test": index_vecdb_test,
    }


def vec_add(
        db: DBConnector,
        vec_db: QdrantClient,
        smind: ScattermindAPI,
        input_str: str,
        *,
        qdrant_cache: Redis,
        articles: str,
        articles_ns: GNamespace,
        articles_input: str,
        articles_output: str,
        user: uuid.UUID,
        base: str,
        doc_id: int,
        url: str,
        title: str,
        meta_obj: dict[ExternalKey, list[str] | str],
        update_meta_only: bool) -> AddEmbed:
    qdrant_cache.flushall()
    # validate title
    title = title.strip()
    if not title:
        raise ValueError("title cannot be empty")
    # validate url
    url = url.strip()
    if not url:
        raise ValueError("url cannot be empty")
    # validate status
    if "status" not in meta_obj:
        raise ValueError(f"status is a mandatory field: {meta_obj}")
    if isinstance(meta_obj["status"], list):
        raise TypeError(f"status {meta_obj['status']} must be string")
    if meta_obj["status"] not in DOC_STATUS:
        raise ValueError(
            f"status must be one of {DOC_STATUS} got "
            f"{meta_obj['status']}")
    # validate doc_type
    if "doc_type" not in meta_obj:
        raise ValueError(f"doc_type is a mandatory field: {meta_obj}")
    doc_type = meta_obj["doc_type"]
    if isinstance(doc_type, list):
        raise TypeError(f"doc_type {doc_type} must be string")
    required_doc_types = KNOWN_DOC_TYPES.get(base)
    if required_doc_types is not None and doc_type not in required_doc_types:
        raise ValueError(
            f"base {base} requires doc_type from "
            f"{required_doc_types} not {doc_type}")
    required_base = DOC_TYPE_TO_BASE.get(doc_type)
    if required_base is not None and required_base != base:
        raise ValueError(
            f"doc_type {doc_type} requires base {required_base} != {base}")
    # validate date
    if "date" in meta_obj:
        if isinstance(meta_obj["date"], list):
            raise TypeError(f"date {meta_obj['date']} must be string")
        if meta_obj["date"] is not None:
            meta_obj["date"] = fmt_time(parse_time_str(meta_obj["date"]))
    # fill language if missing
    if "language" not in meta_obj and not update_meta_only:
        lang_res = extract_language(db, input_str, user)
        meta_obj["language"] = sorted({
            lang_obj["lang"]
            for lang_obj in lang_res["languages"]
        })
    elif "language" in meta_obj:
        meta_obj["language"] = sorted(set(to_list(meta_obj["language"])))
    # fill iso3 if missing
    if "iso3" not in meta_obj and not update_meta_only:
        geo_obj: GeoQuery = {
            "input": input_str,
            "return_input": False,
            "return_context": False,
            "strategy": "top",
            "language": "en",
            "max_requests": DEFAULT_MAX_REQUESTS,
        }
        geo_out = extract_locations(db, geo_obj, user)
        if geo_out["status"] != "invalid":
            meta_obj["iso3"] = sorted({
                geo_entity["location"]["country"]
                for geo_entity in geo_out["entities"]
                if geo_entity["location"] is not None
            })
    elif "iso3" in meta_obj:
        meta_obj["iso3"] = sorted(set(to_list(meta_obj["iso3"])))
    # compute embedding
    snippets = list(snippify_text(
        input_str,
        chunk_size=CHUNK_SIZE,
        chunk_padding=CHUNK_PADDING))
    embeds = get_text_results_immediate(
        snippets,
        smind=smind,
        ns=articles_ns,
        input_field=articles_input,
        output_field=articles_output,
        output_sample=[1.0])
    embed_main: EmbedMain = {
        "base": base,
        "doc_id": doc_id,
        "url": url,
        "title": title,
        "meta": meta_obj,
    }
    embed_chunks: list[EmbedChunk] = [
        {
            "chunk_id": chunk_id,
            "embed": embed,
            "snippet": snippet,
        }
        for chunk_id, (snippet, embed) in enumerate(zip(snippets, embeds))
        if embed is not None
    ]
    # add embedding to vecdb
    prev_count, new_count = add_embed(
        vec_db,
        name=articles,
        data=embed_main,
        chunks=embed_chunks,
        update_meta_only=update_meta_only)
    failed = sum(1 if embed is None else 0 for embed in embeds)
    return {
        "previous": prev_count,
        "snippets": new_count,
        "failed": failed,
    }


def get_filter_hash(filters: dict[ExternalKey, list[str]] | None) -> str:
    blake = hashlib.blake2b(digest_size=32)
    if filters is not None:
        for key, values in sorted(filters.items(), key=lambda kv: kv[0]):
            if not values:
                continue
            key_bytes = key.encode("utf-8")
            blake.update(f"{len(key_bytes)}:".encode("utf-8"))
            blake.update(key_bytes)
            blake.update(f"{len(values)}[".encode("utf-8"))
            for val in sorted(values):
                val_bytes = val.encode("utf-8")
                blake.update(f"{len(val_bytes)}:".encode("utf-8"))
                blake.update(val_bytes)
            blake.update(b"]")
    return blake.hexdigest()


def vec_filter_total(
        vec_db: QdrantClient,
        *,
        qdrant_cache: Redis,
        articles: str,
        filters: dict[ExternalKey, list[str]] | None) -> int:
    if filters is not None:
        filters = {
            key: to_list(value)
            for key, value in filters.items()
        }
    cache_key = f"total:{articles}:{get_filter_hash(filters)}"
    res = qdrant_cache.get_value(cache_key)
    if res is not None:
        print(f"TOTAL CACHE HIT {cache_key}")
        return int(res)
    print(f"TOTAL CACHE MISS {cache_key}")
    ret_val = stat_total(vec_db, articles, filters=filters)
    qdrant_cache.set_value(cache_key, f"{ret_val}")
    return ret_val


def vec_filter_field(
        vec_db: QdrantClient,
        field: ExternalKey,
        *,
        qdrant_cache: Redis,
        articles: str,
        filters: dict[ExternalKey, list[str]] | None) -> dict[str, int]:
    if filters is not None:
        filters = {
            key: to_list(value)
            for key, value in filters.items()
            if key != field
        }
    cache_key = f"field:{articles}:{field}:{get_filter_hash(filters)}"
    res = qdrant_cache.get_value(cache_key)
    if res is not None:
        ret_val: dict[str, int] | None = json_maybe_read(res)
        if ret_val is not None:
            print(f"FIELD CACHE HIT {cache_key}")
            return ret_val
    print(f"FIELD CACHE MISS {cache_key}")
    ret_val = stat_embed(vec_db, articles, field=field, filters=filters)
    qdrant_cache.set_value(cache_key, json_compact_str(ret_val))
    return ret_val


def vec_filter(
        vec_db: QdrantClient,
        *,
        qdrant_cache: Redis,
        articles: str,
        fields: set[ExternalKey],
        filters: dict[ExternalKey, list[str]] | None) -> StatEmbed:
    return {
        "doc_count": vec_filter_total(
            vec_db,
            qdrant_cache=qdrant_cache,
            articles=articles,
            filters=filters),
        "fields": {
            field: vec_filter_field(
                vec_db,
                field,
                qdrant_cache=qdrant_cache,
                articles=articles,
                filters=filters)
            for field in fields
        },
    }


def vec_search(
        db: DBConnector,
        vec_db: QdrantClient,
        smind: ScattermindAPI,
        input_str: str,
        *,
        articles: str,
        articles_ns: GNamespace,
        articles_input: str,
        articles_output: str,
        filters: dict[ExternalKey, list[str]] | None,
        offset: int | None,
        limit: int,
        hit_limit: int,
        score_threshold: float | None,
        short_snippets: bool) -> QueryEmbed:
    if filters is not None:
        filters = {
            key: to_list(value)
            for key, value in filters.items()
        }
        # NOTE: utilizing base vec index for known doc_types
        # each doc_type can only be in one base
        doc_type_filter = filters.get("doc_type")
        if doc_type_filter and "base" not in filters:
            bases: set[str] = set()
            for doc_type in doc_type_filter:
                fixed_base = DOC_TYPE_TO_BASE.get(doc_type)
                if fixed_base is None:
                    bases = set()
                    break
                bases.add(fixed_base)
            if bases:
                filters["base"] = sorted(bases)
    if offset == 0:
        offset = None
    if not input_str:
        res = query_docs(
            vec_db,
            articles,
            offset=offset,
            limit=limit,
            filters=filters)
        return {
            "hits": res,
            "status": "ok",
        }
    embed = get_text_results_immediate(
        [input_str],
        smind=smind,
        ns=articles_ns,
        input_field=articles_input,
        output_field=articles_output,
        output_sample=[1.0])[0]
    log_query(db, db_name=articles, text=input_str)
    if embed is None:
        return {
            "hits": [],
            "status": "error",
        }

    def snippet_post(snippets: list[str]) -> list[str]:
        if not short_snippets:
            return [re.sub(r"\s+", " ", snip).strip() for snip in snippets]
        small_snippets = [
            snap.strip()
            for snip in snippets
            for snap in snippify_text(
                re.sub(r"\s+", " ", snip).strip(),
                chunk_size=SMALL_CHUNK_SIZE,
                chunk_padding=CHUNK_PADDING)
            if snap.strip()
        ]
        sembeds = [
            (stxt, sembed)
            for stxt, sembed in zip(small_snippets, get_text_results_immediate(
                small_snippets,
                smind=smind,
                ns=articles_ns,
                input_field=articles_input,
                output_field=articles_output,
                output_sample=[1.0]))
            if sembed is not None
        ]
        mat_ref = np.array([embed])  # 1 x len(embed)
        mat_embed = np.array([
            sembed
            for (_, sembed) in sembeds
        ]).T  # len(embed) x len(semebds)
        dots = np.matmul(mat_ref, mat_embed).ravel()
        ixs = list(np.argsort(dots))[::-1]
        return [sembeds[ix][0] for ix in ixs[:hit_limit]]

    hits = query_embed_emu_filters(
        vec_db,
        articles,
        embed,
        offset=offset,
        limit=limit,
        hit_limit=hit_limit,
        score_threshold=score_threshold,
        filters=filters,
        snippet_post_processing=snippet_post)
    return {
        "hits": hits,
        "status": "ok",
    }
