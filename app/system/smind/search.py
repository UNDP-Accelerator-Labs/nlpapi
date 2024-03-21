import traceback
from typing import Literal, Protocol, TypedDict

from qdrant_client import QdrantClient
from redipy import Redis
from scattermind.api.api import ScattermindAPI
from scattermind.system.names import GNamespace

from app.misc.util import to_list
from app.system.db.db import DBConnector
from app.system.smind.api import clear_redis, get_text_results_immediate
from app.system.smind.log import log_query
from app.system.smind.vec import (
    query_docs,
    query_embed_emu_filters,
    ResultChunk,
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


def vec_clear(
        vec_db: QdrantClient,
        qdrant_redis: Redis,
        smind_config: str,
        *,
        get_vec_db: GetVecDB,
        clear_rmain: bool,
        clear_rdata: bool,
        clear_rcache: bool,
        clear_rbody: bool,
        clear_rworker: bool,
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
    if clear_vecdb_all:
        try:
            vec_flushall(vec_db, qdrant_redis)
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
        "clear_vecdb_all": clear_vecdb_all,
        "clear_vecdb_main": clear_vecdb_main,
        "clear_vecdb_test": clear_vecdb_test,
        "index_vecdb_main": index_vecdb_main,
        "index_vecdb_test": index_vecdb_test,
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
        filters: dict[str, list[str]] | None,
        offset: int | None,
        limit: int,
        hit_limit: int,
        score_threshold: float | None) -> QueryEmbed:
    if filters is not None:
        filters = {
            key: to_list(value)
            for key, value in filters.items()
        }
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
    hits = query_embed_emu_filters(
        vec_db,
        articles,
        embed,
        offset=offset,
        limit=limit,
        hit_limit=hit_limit,
        score_threshold=score_threshold,
        filters=filters)
    return {
        "hits": hits,
        "status": "ok",
    }
