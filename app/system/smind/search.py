import hashlib
import re
import traceback
import uuid
from collections.abc import Callable
from typing import Literal, Protocol, TypedDict

import numpy as np
from qdrant_client import QdrantClient
from redipy import Redis

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
from app.system.location.response import (
    DEFAULT_MAX_REQUESTS,
    GeoQuery,
    LanguageStr,
)
from app.system.prep.clean import normalize_text
from app.system.prep.snippify import snippify_text
from app.system.smind.api import (
    clear_redis,
    get_text_results_immediate,
    GraphProfile,
)
from app.system.smind.log import log_query
from app.system.smind.vec import (
    add_embed,
    DOC_STATUS,
    EmbedChunk,
    EmbedMain,
    MetaKey,
    MetaObject,
    query_docs,
    query_embed,
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
SMALL_CHUNK_SIZE = 120
CHUNK_PADDING = 10
DEFAULT_HIT_LIMIT = 1


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
        input_str: str,
        *,
        qdrant_cache: Redis,
        articles: str,
        articles_graph: GraphProfile,
        ner_graphs: dict[LanguageStr, GraphProfile],
        user: uuid.UUID,
        base: str,
        doc_id: int,
        url: str,
        title: str,
        meta_obj: MetaObject) -> AddEmbed:
    qdrant_cache.flushall()
    # validate title
    title = normalize_text(title)
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
    if not isinstance(doc_type, str):
        raise TypeError(f"doc_type {doc_type} must be string")
    # validate date
    if meta_obj.get("date") is not None:
        if isinstance(meta_obj["date"], list):
            raise TypeError(f"date {meta_obj['date']} must be string")
        if meta_obj["date"] is not None:
            meta_obj["date"] = fmt_time(parse_time_str(meta_obj["date"]))
    # fill language if missing
    if meta_obj.get("language") is None:
        lang_res = extract_language(db, input_str, user)
        meta_obj["language"] = {
            lang_obj["lang"]: lang_obj["score"]
            for lang_obj in lang_res["languages"]
        }
    else:
        meta_obj["language"] = dict(meta_obj["language"].items())
    # fill iso3 if missing
    if meta_obj.get("iso3") is None:
        geo_obj: GeoQuery = {
            "input": input_str,
            "return_input": False,
            "return_context": False,
            "strategy": "top",
            "language": "xx",
            "max_requests": DEFAULT_MAX_REQUESTS,
        }
        geo_out = extract_locations(db, ner_graphs, geo_obj, user)
        if geo_out["status"] != "invalid":
            total: int = 0
            countries: dict[str, int] = {}
            for geo_entity in geo_out["entities"]:
                if geo_entity["location"] is None:
                    continue
                cur_country = geo_entity["location"]["country"]
                prev_ccount = countries.get(cur_country, 0)
                countries[cur_country] = prev_ccount + geo_entity["count"]
            meta_obj["iso3"] = {
                country: count / total
                for country, count in countries.items()
            }
        else:
            meta_obj["iso3"] = {}
    else:
        meta_obj["iso3"] = dict(meta_obj["iso3"].items())
    # compute embedding
    snippets = [
        snippet
        for (snippet, _) in snippify_text(
            input_str,
            chunk_size=CHUNK_SIZE,
            chunk_padding=CHUNK_PADDING)
    ]
    embeds = get_text_results_immediate(
        snippets,
        graph_profile=articles_graph,
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
        chunks=embed_chunks)
    failed = sum(1 if embed is None else 0 for embed in embeds)
    return {
        "previous": prev_count,
        "snippets": new_count,
        "failed": failed,
    }


def get_filter_hash(filters: dict[MetaKey, list[str]] | None) -> str:
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
        filters: dict[MetaKey, list[str]] | None) -> int:
    if filters is not None:
        filters = {
            key: to_list(value)
            for key, value in filters.items()
            if to_list(value)
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
        field: MetaKey,
        *,
        qdrant_cache: Redis,
        articles: str,
        filters: dict[MetaKey, list[str]] | None) -> dict[str, int]:
    if filters is not None:
        filters = {
            key: to_list(value)
            for key, value in filters.items()
            if key != field and to_list(value)
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
        fields: set[MetaKey],
        filters: dict[MetaKey, list[str]] | None) -> StatEmbed:
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


def apply_snippets(
        hits: list[ResultChunk],
        fn: Callable[[int], list[str]]) -> list[ResultChunk]:

    def apply(ix: int, hit: ResultChunk) -> ResultChunk:
        res = hit.copy()
        res["snippets"] = fn(ix)
        return res

    return [apply(ix, hit) for (ix, hit) in enumerate(hits)]


def dot_order(
        embed: list[float],
        sembeds: list[tuple[tuple[int, str], list[float]]],
        hit_limit: int) -> dict[int, list[str]]:
    mat_ref = np.array([embed])  # 1 x len(embed)

    def dot_hit(group: list[tuple[str, list[float]]]) -> list[str]:
        mat_embed = np.array([
            sembed
            for (_, sembed) in group
        ]).T  # len(embed) x len(group)
        dots = np.matmul(mat_ref, mat_embed).ravel()
        ixs = list(np.argsort(dots))[::-1]
        return [group[ix][0] for ix in ixs[:hit_limit]]

    lookup: dict[int, list[tuple[str, list[float]]]] = {}
    for ((pos, txt), cur_embed) in sembeds:
        cur: list[tuple[str, list[float]]] | None = lookup.get(pos)
        if cur is None:
            cur = []
            lookup[pos] = cur
        cur.append((txt, cur_embed))
    return {
        pos: dot_hit(cur_group)
        for (pos, cur_group) in lookup.items()
    }


def snippet_post(
        hits: list[ResultChunk],
        *,
        embed: list[float],
        articles_graph: GraphProfile,
        short_snippets: bool,
        hit_limit: int) -> list[ResultChunk]:

    def process_snippets(ix: int) -> list[str]:
        return [
            re.sub(r"\s+", " ", snip).strip()
            for snip in hits[ix]["snippets"]
        ]

    if not short_snippets:
        return apply_snippets(hits, process_snippets)
    small_snippets: list[tuple[int, str]] = [
        (ix, snap.strip())
        for (ix, hit) in enumerate(hits)
        for snip in hit["snippets"]
        for (snap, _) in snippify_text(
            re.sub(r"\s+", " ", snip).strip(),
            chunk_size=SMALL_CHUNK_SIZE,
            chunk_padding=CHUNK_PADDING)
        if snap.strip()
    ]
    sembeds: list[tuple[tuple[int, str], list[float]]] = [
        (ssnip, sembed)
        for ssnip, sembed in zip(small_snippets, get_text_results_immediate(
            [snip for (_, snip) in small_snippets],
            graph_profile=articles_graph,
            output_sample=[1.0]))
        if sembed is not None
    ]
    lookup = dot_order(embed, sembeds, hit_limit)

    def apply_dot(ix: int) -> list[str]:
        return lookup.get(ix, [])

    return apply_snippets(hits, apply_dot)


def vec_search(
        db: DBConnector,
        vec_db: QdrantClient,
        input_str: str,
        *,
        articles: str,
        articles_graph: GraphProfile,
        filters: dict[MetaKey, list[str]] | None,
        order_by: MetaKey | tuple[MetaKey, str] | None,
        offset: int | None,
        limit: int,
        hit_limit: int,
        score_threshold: float | None,
        short_snippets: bool) -> QueryEmbed:
    if filters is not None:
        filters = {
            key: to_list(value)
            for key, value in filters.items()
            if to_list(value)
        }
    if offset == 0:
        offset = None
    if not input_str:
        res = query_docs(
            vec_db,
            articles,
            offset=offset,
            limit=limit,
            filters=filters,
            order_by=order_by)
        return {
            "hits": res,
            "status": "ok",
        }
    embed = get_text_results_immediate(
        [input_str],
        graph_profile=articles_graph,
        output_sample=[1.0])[0]
    log_query(db, db_name=articles, text=input_str)
    if embed is None:
        return {
            "hits": [],
            "status": "error",
        }

    hits = query_embed(
        vec_db,
        articles,
        embed,
        offset=offset,
        limit=limit,
        hit_limit=hit_limit,
        score_threshold=score_threshold,
        filters=filters)
    return {
        "hits": snippet_post(
            hits,
            embed=embed,
            articles_graph=articles_graph,
            short_snippets=short_snippets,
            hit_limit=hit_limit),
        "status": "ok",
    }
