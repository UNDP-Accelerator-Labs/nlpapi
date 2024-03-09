# pylint: disable=unused-argument
import sys
import threading
import uuid
from typing import Any

from quick_server import create_server, QuickServer
from quick_server import QuickServerRequestHandler as QSRH
from quick_server import ReqArgs, ReqNext, Response

from app.api.mod import Module
from app.api.mods.lang import LanguageModule
from app.api.mods.loc import LocationModule
from app.api.response_types import (
    AddEmbed,
    QueryEmbed,
    SourceListResponse,
    SourceResponse,
    VersionResponse,
)
from app.misc.env import envload_int, envload_str
from app.misc.version import get_version
from app.system.config import get_config
from app.system.db.db import DBConnector
from app.system.jwt import is_valid_token
from app.system.language.langdetect import LangResponse
from app.system.language.pipeline import extract_language
from app.system.location.forwardgeo import OpenCageFormat
from app.system.location.pipeline import extract_locations, extract_opencage
from app.system.location.response import GeoOutput, GeoQuery
from app.system.ops.ops import get_ops
from app.system.smind.api import (
    get_text_results_immediate,
    load_graph,
    load_smind,
    normalize_text,
    snippify_text,
)
from app.system.smind.vec import (
    add_embed,
    build_db_name,
    EmbedChunk,
    get_vec_client,
    query_embed,
)


MAX_INPUT_LENGTH = 100 * 1024 * 1024  # 100MiB
MAX_LINKS = 20


def setup(
        addr: str,
        port: int,
        parallel: bool,
        deploy: bool) -> tuple[QuickServer, str]:
    server: QuickServer = create_server(
        (addr, port),
        parallel=parallel,
        thread_factory=threading.Thread,
        token_handler=None,
        worker_constructor=None,
        soft_worker_death=True)

    prefix = "/api"

    server.bind_proxy("/qdrant/", "http://localhost:6663/")

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

    py_version_detail = f"{sys.version}"
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    version_name = get_version(return_hash=False)
    version_hash = get_version(return_hash=True)
    print(f"python version: {py_version_detail}")
    print(f"app version: {version_name}")
    print(f"app commit: {version_hash}")

    server.update_version_string(f"nlpapi/{version_name[1:]}")

    server.set_default_token_expiration(48 * 60 * 60)  # 2 days

    config = get_config()
    db = DBConnector(config["db"])
    ops = get_ops("db", config)

    vec_db = get_vec_client(config)
    articles_main = build_db_name(
        "articles_main", distance_fn="dot", db=vec_db)

    smind = load_smind(config["smind"])
    graph_embed = load_graph(smind, "graph_embed.json")

    write_token = envload_str("WRITE_TOKEN")

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

    def verify_write(
            _req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        token = rargs.get("post", {}).get("write_access")
        if token is None:
            raise KeyError("'write_access' not set")
        if write_token != token:
            raise ValueError("invalid write_access token!")
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
    def _get_version(_req: QSRH, _rargs: ReqArgs) -> VersionResponse:
        return {
            "app_name": version_name,
            "app_commit": version_hash,
            "python": py_version,
        }

    # *** sources ***

    @server.json_post(f"{prefix}/source")
    def _post_source(_req: QSRH, rargs: ReqArgs) -> SourceResponse:
        args = rargs["post"]
        source = f"{args['source']}"
        ops.add_source(source)
        return {
            "source": source,
        }

    @server.json_get(f"{prefix}/source")
    def _get_source(_req: QSRH, _rargs: ReqArgs) -> SourceListResponse:
        return {
            "sources": ops.get_sources(),
        }

    # # # SECURE # # #
    server.add_middleware(verify_token)

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
            ns=graph_embed[0],
            input_field=graph_embed[1],
            output_field=graph_embed[2],
            output_sample=[1.0])[0]
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
    @server.middleware(verify_input)
    def _get_geoforward(_req: QSRH, rargs: ReqArgs) -> OpenCageFormat:
        meta = rargs["meta"]
        input_str: str = meta["input"]
        user: uuid.UUID = meta["user"]
        return extract_opencage(db, input_str, user)

    @server.json_post(f"{prefix}/locations")
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
        deploy: bool,
        addr: str | None,
        port: int | None) -> tuple[QuickServer, str]:
    if addr is None:
        addr = envload_str("HOST", default="127.0.0.1")
    if port is None:
        port = envload_int("PORT", default=8080)
    return setup(addr, port, parallel=True, deploy=deploy)


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
