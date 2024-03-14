# pylint: disable=unused-argument
import hmac
import sys
import threading
import traceback
import uuid
from typing import Any, TypedDict

from quick_server import create_server, QuickServer
from quick_server import QuickServerRequestHandler as QSRH
from quick_server import ReqArgs, ReqNext, Response

from app.api.mod import Module
from app.api.mods.lang import LanguageModule
from app.api.mods.loc import LocationModule
from app.api.response_types import (
    AddEmbed,
    ClearResponse,
    QueryEmbed,
    StatsResponse,
    VersionResponse,
)
from app.misc.env import envload_int, envload_str
from app.misc.util import get_time_str
from app.misc.version import get_version
from app.system.config import get_config
from app.system.db.db import DBConnector
from app.system.jwt import is_valid_token
from app.system.language.langdetect import LangResponse
from app.system.language.pipeline import extract_language
from app.system.location.forwardgeo import OpenCageFormat
from app.system.location.pipeline import extract_locations, extract_opencage
from app.system.location.response import GeoOutput, GeoQuery

# from app.system.ops.ops import get_ops
from app.system.smind.api import (
    clear_redis,
    get_queue_stats,
    get_text_results_immediate,
    load_graph,
    load_smind,
    normalize_text,
    snippify_text,
)
from app.system.smind.log import log_query
from app.system.smind.vec import (
    add_embed,
    build_db_name,
    EmbedChunk,
    get_vec_client,
    get_vec_stats,
    query_embed,
    VecDBStat,
)


MAX_INPUT_LENGTH = 100 * 1024 * 1024  # 100MiB
MAX_LINKS = 20


VersionDict = TypedDict('VersionDict', {
    "python_version_detail": str,
    "python_version": str,
    "server_version": str,
    "app_version": str,
    "commit": str,
    "deploy_time": str,
    "start_time": str,
})


def get_version_strs() -> VersionDict:
    py_version_detail = f"{sys.version}"
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    version_name = get_version("name")
    version_hash = get_version("hash")
    version_date = get_version("date")
    server_start = get_time_str()
    return {
        "python_version_detail": py_version_detail,
        "python_version": py_version,
        "server_version": f"nlpapi/{version_name[1:]}",
        "app_version": version_name,
        "commit": version_hash,
        "deploy_time": version_date,
        "start_time": server_start,
    }


def setup(
        server: QuickServer,
        *,
        deploy: bool,
        versions: VersionDict) -> tuple[QuickServer, str]:
    prefix = "/api"

    server.suppress_noise = True

    def report_slow_requests(
            method_str: str, path: str, duration: float) -> None:
        print(f"slow request {method_str} {path} ({duration}s)")

    max_upload = 120 * 1024 * 1024  # 120MiB
    server_timeout = 10 * 60
    server.report_slow_requests = report_slow_requests
    server.max_file_size = max_upload
    server.max_chunk_size = max_upload
    server.timeout = server_timeout
    server.socket.settimeout(server_timeout)

    if deploy:
        server.no_command_loop = True

    server.update_version_string(versions["server_version"])

    server.set_common_invalid_paths(["/", "//"])

    server.set_default_token_expiration(48 * 60 * 60)  # 2 days

    config = get_config()
    db = DBConnector(config["db"])
    # ops = get_ops("db", config)

    vec_db = get_vec_client(config)

    smind_config = config["smind"]
    smind = load_smind(smind_config)
    graph_embed = load_graph(config, smind, "graph_embed.json")

    articles_ns, articles_input, articles_output, articles_size = graph_embed
    if articles_size is None:
        raise ValueError(f"graph {graph_embed} as variable shape")

    def get_vec_db(force_clear: bool) -> str:
        return build_db_name(
            "articles_main",
            distance_fn="dot",
            db=vec_db,
            embed_size=articles_size,
            force_clear=force_clear)

    articles_main = get_vec_db(force_clear=False)

    write_token = envload_str("WRITE_TOKEN")
    tanuki_token = envload_str("TANUKI")  # the nuke key

    vec_cfg = config["vector"]
    server.bind_proxy(
        "/qdrant/", f"http://{vec_cfg['host']}:{vec_cfg['port']}")

    # TODO: deduplicate results (only one result for each document)
    # TODO: allow flushing of db
    # FIXME: make proxy forwarding work with qdrant dashboard
    # TODO: caching
    # TODO: filtering
    # TODO: infinite scroll
    # TODO: score threshold
    # TODO: add date module
    # TODO: node claim stats

    def verify_token(
            _req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        token = rargs.get("post", {}).get("token")
        if token is None:
            token = rargs.get("query", {}).get("token")
        if token is None:
            raise KeyError("'token' not set")
        user = is_valid_token(config, f"{token}")
        if user is None:
            return Response("invalid token provided", 401)
        rargs["meta"]["user"] = user
        return okay

    def verify_readonly(
            _req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        token = rargs.get("post", {}).get("write_access")
        if token is not None:
            raise ValueError(
                "'write_access' was passed for readonly operation! this might "
                "be an error in the script that is accessing the API")
        return okay

    def verify_write(
            _req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        token = rargs.get("post", {}).get("write_access")
        if token is None:
            raise KeyError("'write_access' not set")
        if not hmac.compare_digest(write_token, token):
            raise ValueError("invalid 'write_access' token!")
        return okay

    def verify_tanuki(
            _req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        req_tanuki = rargs.get("post", {}).get("tanuki")
        if req_tanuki is None:
            raise KeyError("'tanuki' not set")
        if not hmac.compare_digest(tanuki_token, req_tanuki):
            raise ValueError("invalid 'tanuki'!")
        return okay

    def verify_input(
            _req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        args = rargs.get("post", {})
        text = args.get("input")
        if text is None:
            text = rargs.get("query", {}).get("q")
        if text is None:
            raise KeyError("POST 'input' or GET 'q' not set")
        text = f"{text}"
        if len(text) > MAX_INPUT_LENGTH:
            return Response(
                f"input length exceeds {MAX_INPUT_LENGTH} bytes", 413)
        rargs["meta"]["input"] = normalize_text(text)
        return okay

    # *** misc ***

    @server.json_get(f"{prefix}/version")
    @server.middleware(verify_readonly)
    def _get_version(_req: QSRH, _rargs: ReqArgs) -> VersionResponse:
        return {
            "app_name": versions["app_version"],
            "app_commit": versions["commit"],
            "python": versions["python_version"],
            "deploy_date": versions["deploy_time"],
            "start_date": versions["start_time"],
            "error": None,
        }

    @server.json_get(f"{prefix}/stats")
    @server.middleware(verify_readonly)
    def _get_stats(_req: QSRH, _rargs: ReqArgs) -> StatsResponse:
        vecdbs: list[VecDBStat] = []
        articles_stats = get_vec_stats(vec_db, articles_main)
        if articles_stats is not None:
            vecdbs.append(articles_stats)
        return {
            "vecdbs": vecdbs,
            "queues": get_queue_stats(smind),
        }

    # # *** sources ***
    #
    # @server.json_post(f"{prefix}/source")
    # def _post_source(_req: QSRH, rargs: ReqArgs) -> SourceResponse:
    #     args = rargs["post"]
    #     source = f"{args['source']}"
    #     ops.add_source(source)
    #     return {
    #         "source": source,
    #     }
    #
    # @server.json_get(f"{prefix}/source")
    # def _get_source(_req: QSRH, _rargs: ReqArgs) -> SourceListResponse:
    #     return {
    #         "sources": ops.get_sources(),
    #     }

    # # # SECURE # # #
    server.add_middleware(verify_token)

    # *** system ***

    @server.json_post(f"{prefix}/clear")
    @server.middleware(verify_write)
    @server.middleware(verify_tanuki)
    def _post_clear(_req: QSRH, rargs: ReqArgs) -> ClearResponse:
        args = rargs["post"]
        clear_rmain = bool(args["clear_rmain"])
        clear_rdata = bool(args["clear_rdata"])
        clear_rcache = bool(args["clear_rcache"])
        clear_vecdb = bool(args["clear_vecdb"])
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
        if clear_vecdb:
            try:
                get_vec_db(force_clear=True)
            except Exception:  # pylint: disable=broad-except
                print(traceback.format_exc())
                clear_vecdb = False
        return {
            "clear_rmain": clear_rmain,
            "clear_rdata": clear_rdata,
            "clear_rcache": clear_rcache,
            "clear_vecdb": clear_vecdb,
        }

    # *** embeddings ***

    @server.json_post(f"{prefix}/add_embed")
    @server.middleware(verify_write)
    @server.middleware(verify_input)
    def _post_add_embed(_req: QSRH, rargs: ReqArgs) -> AddEmbed:
        args = rargs["post"]
        meta = rargs["meta"]
        input_str: str = meta["input"]
        base = args["base"]
        doc_id = int(args["doc_id"])
        url = args["url"]
        meta = args.get("meta", {})
        snippets = list(snippify_text(input_str, 600))
        embeds = get_text_results_immediate(
            snippets,
            smind=smind,
            ns=graph_embed[0],
            input_field=graph_embed[1],
            output_field=graph_embed[2],
            output_sample=[1.0])
        embed_chunks: list[EmbedChunk] = [
            {
                "base": base,
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "embed": embed,
                "snippet": snippet,
                "url": url,
                "meta": meta,
            }
            for chunk_id, (snippet, embed) in enumerate(zip(snippets, embeds))
            if embed is not None
        ]
        count = add_embed(vec_db, articles_main, embed_chunks)
        failed = sum(1 if embed is None else 0 for embed in embed_chunks)
        return {
            "snippets": count,
            "failed": failed,
        }

    @server.json_post(f"{prefix}/query_embed")
    @server.middleware(verify_readonly)
    @server.middleware(verify_input)
    def _post_query_embed(_req: QSRH, rargs: ReqArgs) -> QueryEmbed:
        args = rargs["post"]
        meta = rargs["meta"]
        input_str: str = meta["input"]
        offset: int | None = int(args.get("offset", 0))
        if offset == 0:
            offset = None
        limit = int(args["limit"])
        embed = get_text_results_immediate(
            [input_str],
            smind=smind,
            ns=articles_ns,
            input_field=articles_input,
            output_field=articles_output,
            output_sample=[1.0])[0]
        log_query(db, input_str)
        if embed is None:
            return {
                "hits": [],
                "status": "error",
            }
        hits = query_embed(
            vec_db, articles_main, embed, offset=offset, limit=limit)
        return {
            "hits": hits,
            "status": "ok",
        }

    # *** location ***

    @server.json_get(f"{prefix}/geoforward")
    @server.middleware(verify_readonly)
    @server.middleware(verify_input)
    def _get_geoforward(_req: QSRH, rargs: ReqArgs) -> OpenCageFormat:
        meta = rargs["meta"]
        input_str: str = meta["input"]
        user: uuid.UUID = meta["user"]
        return extract_opencage(db, input_str, user)

    @server.json_post(f"{prefix}/locations")
    @server.middleware(verify_readonly)
    @server.middleware(verify_input)
    def _post_locations(_req: QSRH, rargs: ReqArgs) -> GeoOutput:
        args = rargs["post"]
        meta = rargs["meta"]
        input_str: str = meta["input"]
        user: uuid.UUID = meta["user"]
        obj: GeoQuery = {
            "input": input_str,
            "return_input": args.get("return_input", False),
            "return_context": args.get("return_context", True),
            "strategy": args.get("strategy", "top"),
            "language": args.get("language", "en"),
            "max_requests": args.get("max_requests", 5),
        }
        return extract_locations(db, obj, user)

    # *** language ***

    @server.json_post(f"{prefix}/language")
    @server.middleware(verify_readonly)
    @server.middleware(verify_input)
    def _post_language(_req: QSRH, rargs: ReqArgs) -> LangResponse:
        meta = rargs["meta"]
        input_str: str = meta["input"]
        user: uuid.UUID = meta["user"]
        return extract_language(db, input_str, user)

    # *** generic ***

    mods: dict[str, Module] = {}

    def add_mod(mod: Module) -> None:
        mods[mod.name()] = mod

    add_mod(LocationModule(db))
    add_mod(LanguageModule(db))

    @server.json_post(f"{prefix}/extract")
    @server.middleware(verify_readonly)
    @server.middleware(verify_input)
    def _post_extract(_req: QSRH, rargs: ReqArgs) -> dict[str, Any]:
        args = rargs["post"]
        meta = rargs["meta"]
        input_str: str = meta["input"]
        user: uuid.UUID = meta["user"]
        res: dict[str, Any] = {}
        for module in args.get("modules", []):
            name = module["name"]
            mod = mods.get(name)
            if mod is None:
                raise ValueError(f"unknown module {module}")
            res[name] = mod.execute(input_str, user, module.get("args", {}))
        return res

    return server, prefix


def setup_server(
        *,
        deploy: bool,
        addr: str | None,
        port: int | None,
        versions: VersionDict) -> tuple[QuickServer, str]:
    if addr is None:
        addr = envload_str("HOST", default="127.0.0.1")
    if port is None:
        port = envload_int("PORT", default=8080)

    server: QuickServer = create_server(
        (addr, port),
        parallel=True,
        thread_factory=threading.Thread,
        token_handler=None,
        worker_constructor=None,
        soft_worker_death=True)
    success = False
    try:
        res = setup(server, deploy=deploy, versions=versions)
        success = True
        return res
    finally:
        if not success:
            server.socket.close()
            server.done = True
            server.server_close()


def fallback_server(
        *,
        deploy: bool,
        addr: str | None,
        port: int | None,
        versions: VersionDict,
        exc_strs: list[str]) -> tuple[QuickServer, str]:
    if addr is None:
        addr = envload_str("HOST", default="127.0.0.1")
    if port is None:
        port = envload_int("PORT", default=8080)
    server: QuickServer = create_server(
        (addr, port),
        parallel=True,
        thread_factory=threading.Thread,
        token_handler=None,
        worker_constructor=None,
        soft_worker_death=True)

    prefix = "/api"

    server_timeout = 10 * 60
    server.timeout = server_timeout
    server.socket.settimeout(server_timeout)

    if deploy:
        server.no_command_loop = True

    server.update_version_string(versions["server_version"])

    server.set_common_invalid_paths(["/", "//"])

    # *** misc ***

    @server.json_get(f"{prefix}/version")
    def _get_version(_req: QSRH, _rargs: ReqArgs) -> VersionResponse:
        return {
            "app_name": versions["app_version"],
            "app_commit": versions["commit"],
            "python": versions["python_version_detail"],
            "deploy_date": versions["deploy_time"],
            "start_date": versions["start_time"],
            "error": exc_strs,
        }

    return server, prefix


def start(server: QuickServer, prefix: str) -> None:
    addr, port = server.server_address
    if not isinstance(addr, str):
        addr = addr.decode("utf-8")
    print(
        f"starting API at http://{addr}:{port}{prefix}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print("shutting down..")
        server.server_close()
