# NLP-API provides useful Natural Language Processing capabilities as API.
# Copyright (C) 2024 UNDP Accelerator Labs, Josua Krause
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""High level access to semantic search functionality."""
import hashlib
import re
import time
import traceback
import uuid
from collections.abc import Callable
from typing import Literal, Protocol, TypedDict

from qdrant_client import QdrantClient
from redipy import Redis
from scattermind.system.util import maybe_first

from app.misc.math import dot_order
from app.misc.util import (
    CHUNK_PADDING,
    CHUNK_SIZE,
    DOC_STATUS,
    fmt_time,
    json_compact_str,
    json_maybe_read,
    parse_time_str,
    SMALL_CHUNK_SIZE,
    TITLE_CHUNK_SIZE,
    to_list,
)
from app.system.db.db import DBConnector
from app.system.language.pipeline import extract_language
from app.system.location.response import LanguageStr
from app.system.prep.clean import normalize_text, sanity_check
from app.system.prep.fulltext import TagFn
from app.system.prep.snippify import snippify_text
from app.system.smind.api import (
    clear_redis,
    get_text_results_immediate,
    GraphProfile,
)
from app.system.smind.cache import cached, clear_cache
from app.system.smind.keepalive import update_last_query
from app.system.smind.log import log_query
from app.system.smind.vec import (
    add_embed,
    EmbedChunk,
    EmbedMain,
    get_doc,
    MetaKey,
    MetaObject,
    query_docs,
    query_embed,
    QueryEmbed,
    ResultChunk,
    search_docs,
    stat_embed,
    stat_total,
    StatEmbed,
    to_result,
    vec_flushall,
)
from app.system.urlinspect.inspect import inspect_url


AddEmbed = TypedDict('AddEmbed', {
    "previous": int,
    "snippets": int,
    "failed": int,
})
"""Information about the document added to the vector database. `previous` is
the previous number of snippets, `snippets` is the new number of snippets, and
`failed` is snippets that could not be added."""


class GetVecDB(Protocol):  # pylint: disable=too-few-public-methods
    """Function to get the internal name of a vector database."""
    def __call__(
            self,
            *,
            name: Literal["main", "test"],
            force_clear: bool,
            force_index: bool) -> str:
        """
        Get the internal name from the external vector database name.

        Args:
            name (Literal['main', 'test']): The external database name.
            force_clear (bool): Whether to force dropping the entire database.
                This is an irreversible action.
            force_index (bool): Whether to force full index creation.

        Returns:
            str: The internal database name.
        """


ClearResponse = TypedDict('ClearResponse', {
    "clear_rmain": bool,
    "clear_rdata": bool,
    "clear_rcache": bool,
    "clear_rbody": bool,
    "clear_rworker": bool,
    "clear_process_queue": bool,
    "clear_veccache": bool,
    "clear_vecdb_all": bool,
    "clear_vecdb_main": bool,
    "clear_vecdb_test": bool,
    "index_vecdb_main": bool,
    "index_vecdb_test": bool,
})
"""Which app components were cleared / deleted / dropped / indexed."""


def vec_clear(
        vec_db: QdrantClient,
        smind_config: str,
        *,
        process_queue_redis: Redis,
        qdrant_cache: Redis,
        get_vec_db: GetVecDB,
        clear_rmain: bool,
        clear_rdata: bool,
        clear_rcache: bool,
        clear_rbody: bool,
        clear_rworker: bool,
        clear_process_queue: bool,
        clear_veccache: bool,
        clear_vecdb_main: bool,
        clear_vecdb_test: bool,
        clear_vecdb_all: bool,
        index_vecdb_main: bool,
        index_vecdb_test: bool) -> ClearResponse:
    """
    Clears / indexes app components.

    Args:
        vec_db (QdrantClient): The vector database client.
        smind_config (str): The scattermind config file.
        process_queue_redis (Redis): The processing queue redis.
        qdrant_cache (Redis): The vector database cache redis.
        get_vec_db (GetVecDB): Function to get the internal name of a database.
        clear_rmain (bool): Clears the scattermind main redis.
        clear_rdata (bool): Clears the scattermind data redis.
        clear_rcache (bool): Clears the scattermind cache redis.
        clear_rbody (bool): Clears the scattermind body redis.
        clear_rworker (bool): Clears the scattermind worker redis.
        clear_process_queue (bool): Clears the processing queue redis.
        clear_veccache (bool): Clears the vector database cache.
        clear_vecdb_main (bool): Drops the main vector database.
        clear_vecdb_test (bool): Drops the test vector database.
        clear_vecdb_all (bool): Drops all vector databases.
        index_vecdb_main (bool): Indexes the main vector database.
        index_vecdb_test (bool): Indexes the test vector database.

    Returns:
        ClearResponse: Which app components were dropped / cleared / indexed.
    """
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
    if clear_process_queue:
        try:
            process_queue_redis.flushall()
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            clear_process_queue = False
    if clear_veccache:
        try:
            clear_cache(qdrant_cache, db_name=None)
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
            get_vec_db(name="main", force_clear=True, force_index=False)
            index_vecdb_main = False
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            clear_vecdb_main = False
    if clear_vecdb_test:
        try:
            get_vec_db(name="test", force_clear=True, force_index=False)
            index_vecdb_test = False
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            clear_vecdb_test = False
    if index_vecdb_main:
        try:
            get_vec_db(name="main", force_clear=False, force_index=True)
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            index_vecdb_main = False
    if index_vecdb_test:
        try:
            get_vec_db(name="test", force_clear=False, force_index=True)
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            index_vecdb_test = False
    return {
        "clear_rmain": clear_rmain,
        "clear_rdata": clear_rdata,
        "clear_rcache": clear_rcache,
        "clear_rbody": clear_rbody,
        "clear_rworker": clear_rworker,
        "clear_process_queue": clear_process_queue,
        "clear_veccache": clear_veccache,
        "clear_vecdb_all": clear_vecdb_all,
        "clear_vecdb_main": clear_vecdb_main,
        "clear_vecdb_test": clear_vecdb_test,
        "index_vecdb_main": index_vecdb_main,
        "index_vecdb_test": index_vecdb_test,
    }


LOW_CUTOFF_DATE = parse_time_str("1971-01-01T00:00:00.000+0000").date()
"""Cutoff date for invalid / non-sensical dates."""


def vec_add(
        db: DBConnector,
        vec_db: QdrantClient,
        input_str: str,
        *,
        qdrant_cache: Redis,
        articles: str,
        articles_graph: GraphProfile,
        ner_graphs: dict[LanguageStr, GraphProfile],
        get_tag: TagFn,
        user: uuid.UUID,
        base: str,
        doc_id: int,
        url: str,
        title: str | None,
        meta_obj: MetaObject) -> AddEmbed:
    """
    Adds a document to the vector database.

    Args:
        db (DBConnector): The database connector.
        vec_db (QdrantClient): The vector database client.
        input_str (str): The full document content.
        qdrant_cache (Redis): The vector database cache redis.
        articles (str): The internal vector database name.
        articles_graph (GraphProfile): The embedding model.
        ner_graphs (dict[LanguageStr, GraphProfile]): NER models for different
            languages.
        get_tag (TagFn): Function to return the tag (i.e., country) of the
            document.
        user (uuid.UUID): The user uuid.
        base (str): The document base.
        doc_id (int): The document id.
        url (str): The document URL.
        title (str | None): The document title. If None it will be inferred.
        meta_obj (MetaObject): The document meta data.

    Returns:
        AddEmbed: Information about the added snippets.
    """
    update_last_query(long_time=True)
    main_id = f"{base}:{doc_id}"
    # FIXME: make "smart" features optional
    full_start = time.monotonic()
    # clear caches
    cache_start = time.monotonic()
    clear_cache(qdrant_cache, db_name=articles)
    cache_time = time.monotonic() - cache_start
    preprocess_start = time.monotonic()
    # validate title
    title = normalize_text(sanity_check(title))
    if not title:
        title_loc = maybe_first(snippify_text(
            input_str,
            chunk_size=TITLE_CHUNK_SIZE,
            chunk_padding=CHUNK_PADDING))
        if title_loc is None:
            raise ValueError(f"cannot infer title for {input_str=}")
        title, _ = title_loc
    # validate url
    url = sanity_check(url.strip())
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
    meta_date = meta_obj.get("date")
    if meta_date is not None:
        if isinstance(meta_obj["date"], list):
            raise TypeError(f"date {meta_obj['date']} must be string")
        meta_obj["date"] = fmt_time(parse_time_str(meta_date))
        if parse_time_str(meta_date).date() < LOW_CUTOFF_DATE:
            meta_obj.pop("date", None)  # NOTE: 1970 dates are invalid dates!
    # fill language if missing
    language_start = time.monotonic()
    if meta_obj.get("language") is None:
        lang_res = extract_language(db, input_str, user)
        meta_obj["language"] = {
            lang_obj["lang"]: lang_obj["score"]
            for lang_obj in lang_res["languages"]
        }
    else:
        meta_obj["language"] = dict(meta_obj["language"].items())
    language_time = time.monotonic() - language_start
    # fill iso3 if missing
    country_start = time.monotonic()
    if meta_obj.get("iso3") is None:
        assert ner_graphs  # NOTE: avoiding unused argument note
        # geo_obj: GeoQuery = {
        #     "input": input_str,
        #     "return_input": False,
        #     "return_context": False,
        #     "strategy": "top",
        #     "language": "xx",
        #     "max_requests": DEFAULT_MAX_REQUESTS,
        # }
        # geo_out = extract_locations(db, ner_graphs, geo_obj, user)
        # if geo_out["status"] != "invalid":
        #     total: int = 0
        #     countries: dict[str, int] = {}
        #     for geo_entity in geo_out["entities"]:
        #         if geo_entity["location"] is None:
        #             continue
        #         cur_country = geo_entity["location"]["country"]
        #         prev_ccount = countries.get(cur_country, 0)
        #         geo_count = geo_entity["count"]
        #         total += geo_count
        #         countries[cur_country] = prev_ccount + geo_count
        #     meta_obj["iso3"] = {
        #         country: count / total
        #         for country, count in countries.items()
        #     }
        # else:
        meta_obj["iso3"] = {}
    else:
        meta_obj["iso3"] = dict(meta_obj["iso3"].items())
    # inspect URL and amend iso3 if country found
    url_iso3 = inspect_url(url)
    if url_iso3 is None:
        tag_iso3, tag_reason = get_tag(main_id)
        print(f"tag retrieved: {tag_iso3} {tag_reason}")
        if tag_iso3 is not None:
            meta_obj["iso3"][tag_iso3] = 1.0
    else:
        meta_obj["iso3"][url_iso3] = 1.0
    country_time = time.monotonic() - country_start
    preprocess_time = time.monotonic() - preprocess_start
    # compute embedding
    embed_start = time.monotonic()
    if not input_str:
        snippets: list[str] = []
        embeds: list[list[float] | None] = []
    else:
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
    embed_time = time.monotonic() - embed_start
    # add embedding to vecdb
    vec_start = time.monotonic()
    # print(f"{len(input_str)=} vs {len(embed_chunks)=}")
    prev_count, new_count = add_embed(
        vec_db,
        name=articles,
        data=embed_main,
        embed_size=articles_graph.get_output_size(),
        chunks=embed_chunks)
    failed = sum(1 if embed is None else 0 for embed in embeds)
    vec_time = time.monotonic() - vec_start
    full_time = time.monotonic() - full_start
    print(
        f"adding {main_id} took "
        f"{full_time=}s {preprocess_time=}s {embed_time=}s {vec_time=}s "
        f"{language_time=}s {country_time=}s {cache_time=}s "
        f"{prev_count=} {new_count=} {failed=}")
    return {
        "previous": prev_count,
        "snippets": new_count,
        "failed": failed,
    }


def get_filter_hash(filters: dict[MetaKey, list[str]] | None) -> str:
    """
    Compute the hash value of the given filter.

    Args:
        filters (dict[MetaKey, list[str]] | None): The filter.

    Returns:
        str: The hash value.
    """
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
    """
    Computes how many documents in total are retained after using the given
    filter.

    Args:
        vec_db (QdrantClient): The vector database client.
        qdrant_cache (Redis): The vector database cache redis
        articles (str): The internal vector database name.
        filters (dict[MetaKey, list[str]] | None): The filter.

    Returns:
        int: Number of documents after applying the filter.
    """
    if filters is not None:
        filters = {
            key: to_list(value)
            for key, value in filters.items()
            if to_list(value)
        }
    return cached(
        qdrant_cache,
        cache_type="total",
        db_name=articles,
        cache_hash=get_filter_hash(filters),
        compute_fn=lambda: stat_total(vec_db, articles, filters=filters),
        pre_cache_fn=str,
        post_fn=int)


def vec_filter_field(
        vec_db: QdrantClient,
        field: MetaKey,
        *,
        qdrant_cache: Redis,
        articles: str,
        filters: dict[MetaKey, list[str]] | None) -> dict[str, int]:
    """
    Return the number of documents for each field value after applying the
    filter.

    Args:
        vec_db (QdrantClient): The vector database client.
        field (MetaKey): The field to retrieve information for.
        qdrant_cache (Redis): The vector database cache redis.
        articles (str): The internal vector database name.
        filters (dict[MetaKey, list[str]] | None): The filters.

    Returns:
        dict[str, int]: Field values mapped to counts.
    """
    if filters is not None:
        filters = {
            key: to_list(value)
            for key, value in filters.items()
            if key != field and to_list(value)
        }
    return cached(
        qdrant_cache,
        cache_type="field",
        db_name=f"{articles}:{field}",
        cache_hash=get_filter_hash(filters),
        compute_fn=lambda: stat_embed(
            vec_db, articles, field=field, filters=filters),
        pre_cache_fn=json_compact_str,
        post_fn=json_maybe_read)


def vec_filter(
        vec_db: QdrantClient,
        *,
        qdrant_cache: Redis,
        articles: str,
        fields: set[MetaKey],
        filters: dict[MetaKey, list[str]] | None) -> StatEmbed:
    """
    Provide full information about document counts after applying a filter.

    Args:
        vec_db (QdrantClient): The vector database client.
        qdrant_cache (Redis): The vector database cache redis.
        articles (str): The internal vector database name.
        fields (set[MetaKey]): The fields to retrieve detailed information.
        filters (dict[MetaKey, list[str]] | None): The filters.

    Returns:
        StatEmbed: Statistics about total document counts and requested field
            document counts.
    """
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
    """
    Applies a function to snippets.

    Args:
        hits (list[ResultChunk]): The query results.
        fn (Callable[[int], list[str]]): Function to apply. Gets provided the
            hit index and should return snippets as list.

    Returns:
        list[ResultChunk]: _description_
    """

    def apply(ix: int, hit: ResultChunk) -> ResultChunk:
        res = hit.copy()
        res["snippets"] = fn(ix)
        return res

    return [apply(ix, hit) for (ix, hit) in enumerate(hits)]


def snippet_post(
        hits: list[ResultChunk],
        *,
        embed: list[float],
        articles_graph: GraphProfile,
        short_snippets: bool,
        hit_limit: int) -> tuple[list[ResultChunk], int]:
    """
    Performs snippet refinement for the given query results.

    Args:
        hits (list[ResultChunk]): The query results.
        embed (list[float]): Query embedding.
        articles_graph (GraphProfile): The embedding model.
        short_snippets (bool): Whether to return short snippets. That is the
            hit snippets get further refined to more precisely match the search
            query.
        hit_limit (int): The number of hits to return per result.

    Returns:
        tuple[list[ResultChunk], int]: The results and the number of short
            snippets generated.
    """

    def process_snippets(ix: int) -> list[str]:
        return [
            re.sub(r"\s+", " ", snip).strip()
            for snip in hits[ix]["snippets"]
        ]

    if not short_snippets:
        return (apply_snippets(hits, process_snippets), 0)
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

    return (apply_snippets(hits, apply_dot), len(small_snippets))


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
        short_snippets: bool,
        no_log: bool) -> QueryEmbed:
    """
    Searches for the given string in the vector database. If the search
    query is empty the latest documents are returned instead. If the search
    query starts with `=` followed by a main id (e.g., `=solution:1234`)
    a nearest neighbor search to the given document is performed. Snippets
    are only generated for regular searches.

    Args:
        db (DBConnector): The database connector.
        vec_db (QdrantClient): The vector database client.
        input_str (str): The search query.
        articles (str): The vector database name.
        articles_graph (GraphProfile): The embedding model.
        filters (dict[MetaKey, list[str]] | None): Query filters. A mapping
            of meta data fields to a list of included values. The date
            field, if given, expects a list of exactly two values, the
            start and end date (both inclusive). If None defaults to
            the empty filter.
        order_by (MetaKey | tuple[MetaKey, str] | None): Which way to order
            non-search results.
        offset (int | None): The offset of the returned results. If None
            defaults to 0.
        limit (int): The maximum number of returned results.
        hit_limit (int): The maximum number of hit snippets generated per
            result.
        score_threshold (float | None): Allows to limit the number of
            results further by cutting off at a given score threshold.
            If None defaults to not limiting by score.
        short_snippets (bool): Whether hit snippets should be further
            refined to give more precise and relevant snippets.
        no_log (bool): If True, no log entry is created for the query.

    Returns:
        QueryEmbed: Vector database search results.
    """
    update_last_query(long_time=False)
    if filters is not None:
        filters = {
            key: to_list(value)
            for key, value in filters.items()
            if to_list(value)
        }
    if offset == 0:
        offset = None
    if not input_str:
        res: list[ResultChunk] = query_docs(
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
    full_start = time.monotonic()
    log_start = time.monotonic()
    if not no_log:
        log_query(db, db_name=articles, text=input_str, filters=filters)
    log_time = time.monotonic() - log_start

    if input_str[0] == "=":
        q_main_id = input_str.strip().removeprefix("=")
        doc_start = time.monotonic()
        doc_embed = get_doc(vec_db, articles, q_main_id)
        doc_time = time.monotonic() - doc_start
        if doc_embed is not None:
            dq_start = time.monotonic()
            res_docs = search_docs(
                vec_db,
                articles,
                doc_embed["embed"],
                offset=offset,
                limit=limit,
                score_threshold=score_threshold,
                filters=filters,
                exclude_main_id=q_main_id,
                with_vectors=False)
            res = [to_result(doc_result) for doc_result in res_docs]
            dq_time = time.monotonic() - dq_start
            full_time = time.monotonic() - full_start
            print(
                f"query for '{input_str}' took "
                f"{full_time=}s {log_time=}s {doc_time=}s {dq_time=}s ")
            return {
                "hits": res,
                "status": "ok",
            }
    embed_start = time.monotonic()
    embed = get_text_results_immediate(
        [input_str],
        graph_profile=articles_graph,
        output_sample=[1.0])[0]
    embed_time = time.monotonic() - embed_start

    if embed is None:
        return {
            "hits": [],
            "status": "error",
        }

    query_start = time.monotonic()
    hits = query_embed(
        vec_db,
        articles,
        embed,
        offset=offset,
        limit=limit,
        hit_limit=hit_limit,
        score_threshold=score_threshold,
        filters=filters)
    query_time = time.monotonic() - query_start

    snippy_start = time.monotonic()
    final_hits, snippy_embeds = snippet_post(
        hits,
        embed=embed,
        articles_graph=articles_graph,
        short_snippets=short_snippets,
        hit_limit=hit_limit)
    snippy_time = time.monotonic() - snippy_start

    full_time = time.monotonic() - full_start
    print(
        f"query for '{input_str}' took "
        f"{full_time=}s {log_time=}s {embed_time=}s {query_time=}s "
        f"{snippy_time=}s {snippy_embeds=}")
    return {
        "hits": final_hits,
        "status": "ok",
    }
