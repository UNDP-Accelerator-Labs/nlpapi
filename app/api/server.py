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
import hmac
import os
import sys
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from typing import Any, cast, Literal, TypedDict

from qdrant_client import QdrantClient
from quick_server import create_server, MiddlewareF, QuickServer
from quick_server import QuickServerRequestHandler as QSRH
from quick_server import ReqArgs, ReqNext, Response
from redipy import Redis
from redipy.util import fmt_time

from app.api.mod import Module
from app.api.mods.lang import LanguageModule
from app.api.mods.loc import LocationModule
from app.api.response_types import (
    AddQueue,
    BuildIndexResponse,
    CollectionListResponse,
    CollectionOptionsResponse,
    CollectionResponse,
    CollectionStats,
    DateResponse,
    DocumentListResponse,
    DocumentResponse,
    ErrorProcessQueue,
    FulltextResponse,
    RequeueResponse,
    Snippy,
    SnippyResponse,
    StatsResponse,
    TagClustersResponse,
    TagDocsResponse,
    TagListResponse,
    TitleResponse,
    TitlesResponse,
    URLInspectResponse,
    UserResponse,
    VersionResponse,
)
from app.misc.env import envload_bool, envload_int, envload_path, envload_str
from app.misc.util import (
    CHUNK_PADDING,
    CHUNK_SIZE,
    DEFAULT_HIT_LIMIT,
    get_time_str,
    maybe_float,
    maybe_int,
    SMALL_CHUNK_SIZE,
    to_bool,
)
from app.misc.version import get_version
from app.system.auth import get_session, is_valid_token, SessionInfo
from app.system.autotag.autotag import (
    get_main_ids_for_tag,
    get_tag_cluster_id,
    get_tag_clusters,
    get_tag_group,
    get_tags_for_main_id,
)
from app.system.autotag.cluster import register_tagger
from app.system.config import get_config
from app.system.dates.datetranslate import extract_date
from app.system.db.db import DBConnector
from app.system.deepdive.collection import (
    add_collection,
    add_documents,
    CollectionOptions,
    get_collections,
    get_deep_dives,
    get_documents,
    requeue,
    requeue_error,
    requeue_meta,
    segment_stats,
    set_options,
)
from app.system.deepdive.diver import maybe_diver_thread
from app.system.language.langdetect import LangResponse
from app.system.language.pipeline import extract_language
from app.system.location.forwardgeo import OpenCageFormat
from app.system.location.pipeline import extract_locations, extract_opencage
from app.system.location.response import (
    DEFAULT_MAX_REQUESTS,
    GeoOutput,
    GeoQuery,
    LanguageStr,
)
from app.system.prep.clean import normalize_text, sanity_check
from app.system.prep.fulltext import (
    AllDocsFn,
    create_all_docs,
    create_full_text,
    create_is_remove,
    create_status_date_type,
    create_tag_fn,
    create_url_title,
    FullTextFn,
    IsRemoveFn,
    StatusDateTypeFn,
    TagFn,
    UrlTitleFn,
)
from app.system.prep.snippify import snippify_text
from app.system.smind.adder import register_adder
from app.system.smind.api import (
    get_queue_stats,
    get_redis,
    GraphProfile,
    load_graph,
    load_smind,
)
from app.system.smind.keepalive import set_main_articles
from app.system.smind.search import (
    AddEmbed,
    ClearResponse,
    vec_add,
    vec_clear,
    vec_filter,
    vec_search,
)
from app.system.smind.vec import (
    build_db_name,
    build_scalar_index,
    DBName,
    DBS,
    get_vec_client,
    get_vec_stats,
    MetaKey,
    QueryEmbed,
    StatEmbed,
    VecDBStat,
)
from app.system.stats import create_length_counter
from app.system.urlinspect.inspect import inspect_url
from app.system.workqueues.queue import (
    get_process_queue_errors,
    maybe_process_thread,
    process_queue_info,
    requeue_errors,
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


def get_vec_db(
        vec_db: QdrantClient,
        *,
        name: DBName,
        graph_embed: GraphProfile,
        force_clear: bool,
        force_index: bool) -> str:
    return build_db_name(
        f"articles_{name}",
        distance_fn="dot",
        db=vec_db,
        embed_size=graph_embed.get_output_size(),
        force_clear=force_clear,
        force_index=force_index)


def add_vec_features(
        server: QuickServer,
        db: DBConnector,
        vec_db: QdrantClient,
        *,
        prefix: str,
        process_queue_redis: Redis,
        qdrant_cache: Redis,
        smind_config: str,
        graph_embed: GraphProfile,
        ner_graphs: dict[LanguageStr, GraphProfile],
        get_all_docs: AllDocsFn,
        doc_is_remove: IsRemoveFn,
        get_full_text: FullTextFn,
        get_url_title: UrlTitleFn,
        get_tag: TagFn,
        get_status_date_type: StatusDateTypeFn,
        maybe_session: MiddlewareF,
        verify_readonly: MiddlewareF,
        verify_input: MiddlewareF,
        verify_token: MiddlewareF,
        verify_write: MiddlewareF,
        verify_tanuki: MiddlewareF) -> Callable[[], dict[DBName, str]]:
    cond = threading.Condition()
    articles_dict: dict[DBName, str] = {}

    def init_vec_db() -> None:
        """
        Asynchronously initializes the vector databases. This can be really
        slow and it could happen that qdrant is not available for a while.
        If any call times out this function will repeat trying to access the
        databases. Once everything is connected properly, the process queue
        is started.
        """
        time.sleep(60.0)  # NOTE: give qdrant plenty of time...
        try:
            tstart = time.monotonic()
            print("start loading vector database...")
            articles_main = get_vec_db(
                vec_db,
                name="main",
                graph_embed=graph_embed,
                force_clear=False,
                force_index=False)
            articles_dict["main"] = articles_main

            articles_test = get_vec_db(
                vec_db,
                name="test",
                graph_embed=graph_embed,
                force_clear=False,
                force_index=False)
            articles_dict["test"] = articles_test

            articles_rave_ce = get_vec_db(
                vec_db,
                name="rave_ce",
                graph_embed=graph_embed,
                force_clear=False,
                force_index=False)
            articles_dict["rave_ce"] = articles_rave_ce

            set_main_articles(
                db,
                vec_db,
                articles=articles_main,
                articles_graph=graph_embed,
                vec_search_fn=vec_search)

            with cond:
                cond.notify_all()
            maybe_process_thread(process_queue_redis)
            print(
                "loading vector database complete "
                f"in {time.monotonic() - tstart}s!")
        except BaseException:  # pylint: disable=broad-except
            print(
                "ERROR! loading vector database "
                f"failed:\n{traceback.format_exc()}")
            # NOTE: RecursionError will also be caught here
            init_vec_db()

    th = threading.Thread(target=init_vec_db, daemon=True)
    th.start()

    def parse_vdb(vdb_str: str) -> DBName:
        """
        Converts a string into the external database name type.

        Args:
            vdb_str (str): The string.

        Raises:
            ValueError: If the string is not a valid external vector database
                name.

        Returns:
            DBName: The external vector database name.
        """
        if vdb_str not in DBS:
            raise ValueError(f"db ({vdb_str}) must be one of {DBS}")
        return cast(DBName, vdb_str)

    def get_articles(vdb_str: str) -> str:
        """
        Converts an external vector database name into an internal vector
        database name.

        Args:
            vdb_str (str): The external database name.

        Raises:
            ValueError: If the string is not a valid external vector database
                name or the databases have not been loaded yet.

        Returns:
            str: The internal name for the given vector database.
        """
        vdb = parse_vdb(vdb_str)
        res = articles_dict.get(vdb)
        if res:
            return res
        with cond:
            res = cond.wait_for(lambda: articles_dict.get(vdb), 120.0)
        if res:
            return res
        raise ValueError("vector database is not ready yet!")

    def get_articles_dict() -> dict[DBName, str]:
        """
        Retrieve all loaded vector databases.

        Returns:
            dict[DBName, str]: The external name mapped to the internal name.
        """
        return dict(articles_dict)

    @server.json_post(f"{prefix}/stats")
    @server.middleware(verify_readonly)
    @server.middleware(maybe_session)
    def _post_stats(_req: QSRH, rargs: ReqArgs) -> StatEmbed:
        """
        The `/api/stats` endpoint provides document counts for semantic search
        queries. If the session cookie is not provided or invalid only public
        documents are considered for the stats.

        @readonly
        @cookie (optional)

        Args:
            _req (QSRH): The request.
            rargs (ReqArgs): The arguments.
                POST
                    "fields": A set of field types expected to be returned.
                    "filters": A dictionary of field types to lists of filter
                        values. The date field, if given, expects a list of
                        exactly two values, the start and end date
                        (both inclusive). If the session cookie is missing or
                        invalid the "status" filter gets overwritten to
                        include "public" documents only.
                    "vecdb": The vector database.
        Returns:
            StatEmbed: Vector database document counts.
        """
        session: SessionInfo | None = rargs["meta"].get("session")
        args = rargs["post"]
        fields = set(args["fields"])
        filters: dict[MetaKey, list[str]] = args.get("filters", {})
        if session is None:  # NOTE: not logged in!
            filters["status"] = ["public"]
        articles = get_articles(args.get("vecdb", "main"))
        return vec_filter(
            vec_db,
            qdrant_cache=qdrant_cache,
            articles=articles,
            fields=fields,
            filters=filters)

    @server.json_post(f"{prefix}/search")
    @server.middleware(verify_readonly)
    @server.middleware(maybe_session)
    @server.middleware(verify_input)
    def _post_search(_req: QSRH, rargs: ReqArgs) -> QueryEmbed:
        session: SessionInfo | None = rargs["meta"].get("session")
        args = rargs["post"]
        meta = rargs["meta"]
        input_str: str = meta["input"]
        filters: dict[MetaKey, list[str]] = args.get("filters", {})
        if session is None:  # NOTE: not logged in!
            filters["status"] = ["public"]
        offset: int = int(args.get("offset", 0))
        limit: int = int(args["limit"])
        hit_limit: int = int(args.get("hit_limit", DEFAULT_HIT_LIMIT))
        score_threshold: float | None = maybe_float(
            args.get("score_threshold"))
        short_snippets = bool(args.get("short_snippets", True))
        order_by: MetaKey = "date"  # FIXME: order_by
        articles = get_articles(args.get("vecdb", "main"))
        return vec_search(
            db,
            vec_db,
            input_str,
            articles=articles,
            articles_graph=graph_embed,
            filters=filters,
            order_by=order_by,
            offset=offset,
            limit=limit,
            hit_limit=hit_limit,
            score_threshold=score_threshold,
            short_snippets=short_snippets,
            no_log=False)

    def get_ctx_vec_db(
            *,
            name: Literal["main", "test"],
            force_clear: bool,
            force_index: bool) -> str:
        return get_vec_db(
            vec_db,
            name=name,
            graph_embed=graph_embed,
            force_clear=force_clear,
            force_index=force_index)

    # *** system ***

    @server.json_get(f"{prefix}/queue/error")
    def _get_queue_error(_req: QSRH, _rargs: ReqArgs) -> ErrorProcessQueue:
        return {
            "errors": get_process_queue_errors(process_queue_redis),
        }

    with server.middlewares(verify_token):
        @server.json_post(f"{prefix}/clear")
        @server.middleware(verify_write)
        @server.middleware(verify_tanuki)
        def _post_clear(_req: QSRH, rargs: ReqArgs) -> ClearResponse:
            args = rargs["post"]
            clear_rmain = bool(args.get("clear_rmain", False))
            clear_rdata = bool(args.get("clear_rdata", False))
            clear_rcache = bool(args.get("clear_rcache", False))
            clear_rbody = bool(args.get("clear_rbody", False))
            clear_rworker = bool(args.get("clear_rworker", False))
            clear_process_queue = bool(args.get("clear_process_queue", False))
            clear_veccache = bool(args.get("clear_veccache", False))
            clear_vecdb_main = bool(args.get("clear_vecdb_main", False))
            clear_vecdb_test = bool(args.get("clear_vecdb_test", False))
            clear_vecdb_all = bool(args.get("clear_vecdb_all", False))
            index_vecdb_main = bool(args.get("index_vecdb_main", False))
            index_vecdb_test = bool(args.get("index_vecdb_test", False))
            return vec_clear(
                vec_db,
                smind_config,
                process_queue_redis=process_queue_redis,
                qdrant_cache=qdrant_cache,
                get_vec_db=get_ctx_vec_db,
                clear_rmain=clear_rmain,
                clear_rdata=clear_rdata,
                clear_rcache=clear_rcache,
                clear_rbody=clear_rbody,
                clear_rworker=clear_rworker,
                clear_process_queue=clear_process_queue,
                clear_veccache=clear_veccache,
                clear_vecdb_main=clear_vecdb_main,
                clear_vecdb_test=clear_vecdb_test,
                clear_vecdb_all=clear_vecdb_all,
                index_vecdb_main=index_vecdb_main,
                index_vecdb_test=index_vecdb_test)

        # *** embeddings ***

        base_processor, adder_processor = register_adder(
            db,
            vec_db,
            process_queue_redis=process_queue_redis,
            qdrant_cache=qdrant_cache,
            graph_embed=graph_embed,
            ner_graphs=ner_graphs,
            get_articles=get_articles,
            get_all_docs=get_all_docs,
            doc_is_remove=doc_is_remove,
            get_full_text=get_full_text,
            get_url_title=get_url_title,
            get_tag=get_tag,
            get_status_date_type=get_status_date_type)

        @server.json_post(f"{prefix}/queue/requeue")
        @server.middleware(verify_write)
        def _post_queue_requeue(
                _req: QSRH, _rargs: ReqArgs) -> AddQueue:
            res = requeue_errors(process_queue_redis)
            return {
                "enqueued": res,
            }

        @server.json_post(f"{prefix}/embed/add")
        @server.middleware(verify_write)
        def _post_embed_add(_req: QSRH, rargs: ReqArgs) -> AddQueue:
            args = rargs["post"]
            meta = rargs["meta"]
            main_id = args.get("main_id")
            bases = args.get("bases")
            if (main_id is None) == (bases is None):
                raise ValueError("must use either main_id or base")
            vdb_str: str = args["db"]
            user: uuid.UUID = meta["user"]
            if main_id is not None:
                adder_processor(vdb_str=vdb_str, main_id=main_id, user=user)
            if bases is not None:
                base_processor(vdb_str=vdb_str, bases=list(bases), user=user)
            return {
                "enqueued": True,
            }

        @server.json_post(f"{prefix}/add_embed")
        @server.middleware(verify_write)
        @server.middleware(verify_input)
        def _post_add_embed(_req: QSRH, rargs: ReqArgs) -> AddEmbed:
            args = rargs["post"]
            meta = rargs["meta"]
            input_str: str = meta["input"]
            vdb_str: str = args["db"]
            articles = get_articles(vdb_str)
            base: str = args["base"]
            if not base:
                raise ValueError(f"{base=} must be set")
            doc_id = int(args["doc_id"])
            url: str = args["url"]
            if not url:
                raise ValueError(f"{url=} must be set")
            title: str | None = args["title"]
            meta_obj = args.get("meta", {})
            user: uuid.UUID = meta["user"]
            return vec_add(
                db,
                vec_db,
                input_str,
                qdrant_cache=qdrant_cache,
                articles=articles,
                articles_graph=graph_embed,
                ner_graphs=ner_graphs,
                get_tag=get_tag,
                user=user,
                base=base,
                doc_id=doc_id,
                url=url,
                title=title,
                meta_obj=meta_obj)

        @server.json_post(f"{prefix}/build_index")
        @server.middleware(verify_write)
        def _post_build_index(
                _req: QSRH, rargs: ReqArgs) -> BuildIndexResponse:
            args = rargs["post"]
            vdb_str = args["db"]
            articles = get_articles(vdb_str)
            count = build_scalar_index(vec_db, articles, full_stats=None)
            return {
                "new_index_count": count,
            }

        @server.json_post(f"{prefix}/stat_embed")
        @server.middleware(verify_readonly)
        def _post_stat_embed(_req: QSRH, rargs: ReqArgs) -> StatEmbed:
            args = rargs["post"]
            vdb_str = args["db"]
            articles = get_articles(vdb_str)
            fields = set(args["fields"])
            filters: dict[MetaKey, list[str]] | None = args.get("filters")
            return vec_filter(
                vec_db,
                qdrant_cache=qdrant_cache,
                articles=articles,
                fields=fields,
                filters=filters)

        @server.json_post(f"{prefix}/query_embed")
        @server.middleware(verify_readonly)
        @server.middleware(verify_input)
        def _post_query_embed(_req: QSRH, rargs: ReqArgs) -> QueryEmbed:
            args = rargs["post"]
            meta = rargs["meta"]
            input_str: str = meta["input"]
            vdb_str = args["db"]
            articles = get_articles(vdb_str)
            filters: dict[MetaKey, list[str]] | None = args.get("filters")
            offset: int = int(args.get("offset", 0))
            limit: int = int(args["limit"])
            hit_limit: int = int(args.get("hit_limit", DEFAULT_HIT_LIMIT))
            score_threshold: float | None = maybe_float(
                args.get("score_threshold"))
            short_snippets = bool(args.get("short_snippets", True))
            order_by: MetaKey = "date"  # FIXME: order_by
            return vec_search(
                db,
                vec_db,
                input_str,
                articles=articles,
                articles_graph=graph_embed,
                filters=filters,
                order_by=order_by,
                offset=offset,
                limit=limit,
                hit_limit=hit_limit,
                score_threshold=score_threshold,
                short_snippets=short_snippets,
                no_log=False)

    return get_articles_dict


def setup(
        server: QuickServer,
        *,
        deploy: bool,
        versions: VersionDict) -> tuple[QuickServer, str]:
    prefix = "/api"

    server.suppress_noise = True

    server.register_shutdown()

    def report_slow_requests(
            method_str: str,
            path: str,
            duration: float,
            complete: bool) -> None:
        duration_str = f"({duration}s)" if complete else "pending"
        print(f"slow request {method_str} {path} {duration_str}")

    max_upload = 120 * 1024 * 1024  # 120MiB
    server_timeout = 10 * 60
    server.report_slow_requests = (30.0, report_slow_requests)
    server.max_file_size = max_upload
    server.max_chunk_size = max_upload
    server.timeout = server_timeout
    server.socket.settimeout(server_timeout)

    server.link_empty_favicon_fallback()

    server.cross_origin = True  # FIXME: for now...

    if deploy:
        server.no_command_loop = True

    server.update_version_string(versions["server_version"])

    server.set_common_invalid_paths(["/", "//"])

    server.set_default_token_expiration(48 * 60 * 60)  # 2 days

    config = get_config()
    db = DBConnector(config["db"])
    all_platforms = {
        pname: DBConnector(pconfig)
        for pname, pconfig in config["platforms"].items()
    }
    platforms: dict[str, DBConnector] = {
        pname: pdb
        for pname, pdb in all_platforms.items()
        if pname != "login"
    }
    try:
        login_db = all_platforms["login"]
    except KeyError as kerr:
        ps_str = envload_str("LOGIN_DB_NAME_PLATFORMS", default="")
        raise ValueError(
            f"must define login in {ps_str}. "
            "format is '<short>:<dbname>'") from kerr
    blogs = {
        bname: DBConnector(bconfig)
        for bname, bconfig in config["blogs"].items()
    }
    if "blog" not in blogs:
        bs_str = envload_str("BLOGS_DB_NAMES", default="")
        raise ValueError(
            f"must define blog in {bs_str}. "
            "format is '<short>:<dbname>'")

    vec_db = get_vec_client(config)

    smind_config = config["smind"]
    smind = load_smind(smind_config)
    graph_embed = load_graph(config, smind, "graph_embed.json")
    graph_tags = load_graph(config, smind, "graph_tags.json")

    if envload_bool("HAS_LLAMA", default=False):
        graph_llama = load_graph(config, smind, "graph_llama.json")
    else:
        graph_llama = None

    get_all_docs = create_all_docs(platforms, blogs)
    doc_is_remove = create_is_remove(platforms, blogs)
    get_full_text = create_full_text(
        platforms,
        blogs,
        combine_title=True,
        ignore_unpublished=True)
    get_url_title = create_url_title(
        platforms,
        blogs,
        get_full_text=get_full_text,
        ignore_unpublished=True)
    get_tag = create_tag_fn(platforms, blogs, ignore_unpublished=True)
    get_status_date_type = create_status_date_type(
        platforms, blogs, ignore_unpublished=True)
    if graph_llama is not None:

        def _maybe_start_dive() -> None:
            maybe_diver_thread(
                db,
                smind,
                graph_llama,
                get_full_text,
                get_url_title,
                get_tag)

        maybe_start_dive = _maybe_start_dive
    else:

        def nop() -> None:
            pass

        maybe_start_dive = nop

    maybe_start_dive()

    ner_graphs: dict[LanguageStr, GraphProfile] = {
        "en": load_graph(config, smind, "graph_ner_en.json"),
        "xx": load_graph(config, smind, "graph_ner_xx.json"),
    }

    qdrant_cache = get_redis(
        smind_config, redis_name="rcache", overwrite_prefix="qdrant")
    process_queue_redis = get_redis(
        smind_config, redis_name="rmain", overwrite_prefix="embed_add")

    write_token = config["write_token"]
    tanuki_token = config["tanuki"]  # the nuke key

    vec_cfg = config["vector"]
    if vec_cfg is not None:
        server.bind_proxy(
            "/qdrant/", f"http://{vec_cfg['host']}:{vec_cfg['port']}")
        # FIXME: fix for https://github.com/qdrant/qdrant-web-ui/issues/94
        # server.set_debug_proxy(True)
        server.bind_proxy(
            "/dashboard/",
            f"http://{vec_cfg['host']}:{vec_cfg['port']}/dashboard")
        server.bind_proxy(
            "/collections/",
            f"http://{vec_cfg['host']}:{vec_cfg['port']}/collections")
        server.bind_proxy(
            "/cluster/",
            f"http://{vec_cfg['host']}:{vec_cfg['port']}/cluster")
        server.bind_proxy(
            "/telemetry/",
            f"http://{vec_cfg['host']}:{vec_cfg['port']}/telemetry")

    public_path = envload_path("UI_PATH", default="build/")
    server.bind_path("/", public_path)

    def file_fallback(_: str) -> str:
        return os.path.join(public_path, "index.html")

    server.set_file_fallback_hook(file_fallback)

    force_user_str = envload_str("FORCE_USER", default="").strip()
    if force_user_str:
        force_user = uuid.UUID(force_user_str)
        print(f"WARNING: forcing user {force_user.hex}")
    else:
        force_user = None

    def maybe_session(_req: QSRH, rargs: ReqArgs, okay: ReqNext) -> ReqNext:
        if force_user is not None:
            session: SessionInfo | None = {
                "name": "ADMIN",
                "uuid": force_user,
            }
            rargs["meta"]["session"] = session
            return okay
        cookie = rargs["cookie"]
        if cookie is None:
            return okay
        session_cookie = cookie.get("acclab_platform-session")
        if session_cookie is None:
            return okay
        session_str = session_cookie.value
        session = get_session(login_db, session_str)
        if session is not None:
            rargs["meta"]["session"] = session
        return okay

    def verify_session(
            req: QSRH, rargs: ReqArgs, okay: ReqNext) -> Response | ReqNext:
        inner = maybe_session(req, rargs, okay)
        if inner is not okay:
            return inner
        session: SessionInfo | None = rargs["meta"].get("session")
        if session is None:
            return Response("not logged in", 401)
        return okay

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
        rargs["meta"]["input"] = normalize_text(sanity_check(text))
        return okay

    if vec_db is not None:
        get_articles_dict = add_vec_features(
            server,
            db,
            vec_db,
            prefix=prefix,
            process_queue_redis=process_queue_redis,
            qdrant_cache=qdrant_cache,
            smind_config=smind_config,
            graph_embed=graph_embed,
            ner_graphs=ner_graphs,
            get_all_docs=get_all_docs,
            doc_is_remove=doc_is_remove,
            get_full_text=get_full_text,
            get_url_title=get_url_title,
            get_tag=get_tag,
            get_status_date_type=get_status_date_type,
            maybe_session=maybe_session,
            verify_readonly=verify_readonly,
            verify_input=verify_input,
            verify_token=verify_token,
            verify_write=verify_write,
            verify_tanuki=verify_tanuki)
    else:

        def no_articles() -> dict[DBName, str]:
            return {}

        get_articles_dict = no_articles

    # *** misc ***

    @server.json_get(f"{prefix}/version")
    @server.middleware(verify_readonly)
    def _get_version(_req: QSRH, _rargs: ReqArgs) -> VersionResponse:
        articles_dbs = sorted(get_articles_dict().keys())
        return {
            "app_name": versions["app_version"],
            "app_commit": versions["commit"],
            "python": versions["python_version"],
            "deploy_date": versions["deploy_time"],
            "start_date": versions["start_time"],
            "has_vecdb": vec_db is not None,
            "has_llm": graph_llama is not None,
            "vecdb_ready": bool(articles_dbs),
            "vecdbs": articles_dbs,
            "deepdives": sorted(get_deep_dives(db)),
            "error": None,
        }

    @server.json_post(f"{prefix}/user")
    @server.middleware(maybe_session)
    def _post_user(_req: QSRH, rargs: ReqArgs) -> UserResponse:
        session: SessionInfo | None = rargs["meta"].get("session")
        return {
            "uuid": None if session is None else session["uuid"].hex,
            "name": None if session is None else session["name"],
        }

    @server.json_get(f"{prefix}/info")
    @server.middleware(verify_readonly)
    def _get_info(_req: QSRH, _rargs: ReqArgs) -> StatsResponse:
        vecdbs: list[VecDBStat] = []
        if vec_db is not None:
            for ext_name, article in get_articles_dict().items():
                for is_vec in [False, True]:
                    article_stats = get_vec_stats(
                        vec_db, article, is_vec=is_vec)
                    if article_stats is not None:
                        article_stats["ext_name"] = ext_name
                        vecdbs.append(article_stats)
        return {
            "vecdbs": vecdbs,
            "queues": get_queue_stats(smind),
            "process_queue": process_queue_info(process_queue_redis),
        }

    @server.json_post(f"{prefix}/tags/clusters")
    def _post_tags_clusters(_req: QSRH, rargs: ReqArgs) -> TagClustersResponse:
        args = rargs["post"]
        tag_group: int | None = maybe_int(args.get("tag_group"))
        name: str | None = args.get("name")
        if tag_group is not None and name is not None:
            raise ValueError(f"{tag_group=} or {name=} cannot both be set")
        with db.get_session() as session:
            if tag_group is None:
                tag_group = get_tag_group(session, name)
            clusters = get_tag_clusters(session, tag_group)
        return {
            "clusters": clusters,
            "tag_group": tag_group,
        }

    @server.json_post(f"{prefix}/tags/docs")
    def _post_tags_docs(_req: QSRH, rargs: ReqArgs) -> TagDocsResponse:
        args = rargs["post"]
        tag_group: int = int(args["tag_group"])
        cluster: str | None = args.get("cluster")
        cluster_id: int | None = maybe_int(args.get("cluster_id"))
        if cluster is not None and cluster_id is not None:
            raise ValueError(f"{cluster=} or {cluster_id=} cannot both be set")
        with db.get_session() as session:
            if cluster_id is None:
                if cluster is None:
                    raise ValueError(
                        "either cluster or cluster_id must be set")
                cluster_id = get_tag_cluster_id(session, tag_group, cluster)
            main_ids = get_main_ids_for_tag(session, tag_group, cluster_id)
        return {
            "main_ids": sorted(main_ids),
            "tag_group": tag_group,
            "cluster_id": cluster_id,
        }

    @server.json_post(f"{prefix}/tags/list")
    def _post_tags_list(_req: QSRH, rargs: ReqArgs) -> TagListResponse:
        args = rargs["post"]
        tag_group: int | None = maybe_int(args.get("tag_group"))
        name: str | None = args.get("name")
        if tag_group is not None and name is not None:
            raise ValueError(f"{tag_group=} or {name=} cannot both be set")
        main_ids: list[str] = list(args["main_ids"])
        tags: dict[str, list[str]] = {}
        with db.get_session() as session:
            if tag_group is None:
                tag_group = get_tag_group(session, name)
            for main_id in main_ids:
                tags[main_id] = sorted(
                    get_tags_for_main_id(session, tag_group, main_id))
        return {
            "tags": tags,
            "tag_group": tag_group,
        }

    # # # SECURE # # #
    with server.middlewares(verify_token):
        # *** auto tag ***
        tag_processor = register_tagger(
            db,
            global_db=login_db,
            platforms=platforms,
            process_queue_redis=process_queue_redis,
            articles_graph=graph_embed,
            graph_tags=graph_tags,
            get_all_docs=get_all_docs,
            doc_is_remove=doc_is_remove,
            get_full_text=get_full_text)

        @server.json_post(f"{prefix}/tags/create")
        @server.middleware(verify_write)
        def _post_tags_create(_req: QSRH, rargs: ReqArgs) -> AddQueue:
            args = rargs["post"]
            name: str | None = args.get("name")
            bases: list[str] = list(args["bases"])
            is_updating = to_bool(args.get("is_updating", True))
            cluster_args = args.get("cluster_args", {})
            tag_processor(
                name=name,
                bases=bases,
                is_updating=is_updating,
                cluster_args=cluster_args)
            return {
                "enqueued": True,
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
                "max_requests": args.get("max_requests", DEFAULT_MAX_REQUESTS),
            }
            return extract_locations(db, ner_graphs, obj, user)

        # *** language ***

        @server.json_post(f"{prefix}/language")
        @server.middleware(verify_readonly)
        @server.middleware(verify_input)
        def _post_language(_req: QSRH, rargs: ReqArgs) -> LangResponse:
            meta = rargs["meta"]
            input_str: str = meta["input"]
            user: uuid.UUID = meta["user"]
            return extract_language(db, input_str, user)

        # *** misc ***

        @server.json_post(f"{prefix}/inspect")
        @server.middleware(verify_readonly)
        def _post_inspect(_req: QSRH, rargs: ReqArgs) -> URLInspectResponse:
            args = rargs["post"]
            url = args["url"]
            iso3 = inspect_url(url)
            return {
                "url": url,
                "iso3": iso3,
            }

        @server.json_post(f"{prefix}/date")
        @server.middleware(verify_readonly)
        def _post_date(_req: QSRH, rargs: ReqArgs) -> DateResponse:
            args = rargs["post"]
            raw_html = args["raw_html"]
            posted_date_str = args.get("posted_date_str")
            language = args.get("language")
            use_date_str = bool(args.get("use_date_str", True))
            lnc, _ = create_length_counter()
            date = extract_date(
                raw_html,
                posted_date_str=posted_date_str,
                language=language,
                use_date_str=use_date_str,
                lnc=lnc)
            return {
                "date": None if date is None else fmt_time(date),
            }

        @server.json_post(f"{prefix}/snippify")
        @server.middleware(verify_readonly)
        @server.middleware(verify_input)
        def _post_snippify(_req: QSRH, rargs: ReqArgs) -> SnippyResponse:
            args = rargs["post"]
            meta = rargs["meta"]
            input_str: str = meta["input"]
            chunk_size = args.get("chunk_size")
            chunk_padding = args.get("chunk_padding")
            small_snippets = bool(args.get("small_snippets"))
            if chunk_size is None:
                chunk_size = SMALL_CHUNK_SIZE if small_snippets else CHUNK_SIZE
            if chunk_padding is None:
                chunk_padding = CHUNK_PADDING
            res: list[Snippy] = [
                {
                    "text": text,
                    "offset": offset,
                }
                for (text, offset) in snippify_text(
                    input_str,
                    chunk_size=chunk_size,
                    chunk_padding=chunk_padding)
            ]
            return {
                "count": len(res),
                "snippets": res,
            }

        # *** generic ***

        mods: dict[str, Module] = {}

        def add_mod(mod: Module) -> None:
            mods[mod.name()] = mod

        add_mod(LocationModule(db, ner_graphs))
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
                res[name] = mod.execute(
                    input_str, user, module.get("args", {}))
            return res

    @server.json_get(f"{prefix}/collection/stats")
    def _get_collection_stats(_req: QSRH, _rargs: ReqArgs) -> CollectionStats:
        stats = list(segment_stats(db))
        return {
            "segments": stats,
        }

    # # # SESSION # # #
    def get_doc_info(main_id: str, *, is_logged_in: bool) -> TitleResponse:
        url_title, error_msg = get_url_title(
            main_id, is_logged_in=is_logged_in)
        if url_title is None:
            return {
                "url": None,
                "title": None,
                "error": error_msg,
            }
        url, title = url_title
        return {
            "url": url,
            "title": title,
            "error": error_msg,
        }

    @server.json_post(f"{prefix}/documents/info")
    @server.middleware(maybe_session)
    def _post_documents_info(
            _req: QSRH, rargs: ReqArgs) -> TitleResponse:
        session: SessionInfo | None = rargs["meta"].get("session")
        args = rargs["post"]
        main_id: str = args["main_id"]
        is_logged_in = session is not None
        return get_doc_info(main_id, is_logged_in=is_logged_in)

    @server.json_post(f"{prefix}/documents/infos")
    @server.middleware(maybe_session)
    def _post_documents_infos(
            _req: QSRH, rargs: ReqArgs) -> TitlesResponse:
        session: SessionInfo | None = rargs["meta"].get("session")
        args = rargs["post"]
        main_ids: list[str] = args["main_ids"]
        is_logged_in = session is not None
        info: list[TitleResponse] = [
            get_doc_info(main_id, is_logged_in=is_logged_in)
            for main_id in main_ids
        ]
        return {
            "info": info,
        }

    with server.middlewares(verify_session):
        # *** collections ***

        @server.json_post(f"{prefix}/collection/add")
        def _post_collection_add(
                _req: QSRH, rargs: ReqArgs) -> CollectionResponse:
            args = rargs["post"]
            name: str = args["name"]
            deep_dive = args["deep_dive"]
            session: SessionInfo = rargs["meta"]["session"]
            res = add_collection(db, session["uuid"], name, deep_dive)
            return {
                "collection_id": res,
            }

        @server.json_post(f"{prefix}/collection/list")
        def _post_collection_list(
                _req: QSRH, rargs: ReqArgs) -> CollectionListResponse:
            session: SessionInfo = rargs["meta"]["session"]
            return {
                "collections": [
                    {
                        "id": obj["id"],
                        "user": obj["user"].hex,
                        "name": obj["name"],
                        "deep_dive_name": obj["deep_dive_name"],
                        "is_public": obj["is_public"],
                    }
                    for obj in get_collections(db, session["uuid"])
                ],
            }

        @server.json_post(f"{prefix}/collection/options")
        def _post_collection_options(
                _req: QSRH, rargs: ReqArgs) -> CollectionOptionsResponse:
            args = rargs["post"]
            collection_id = int(args["collection_id"])
            options: CollectionOptions = args["options"]
            session: SessionInfo = rargs["meta"]["session"]
            set_options(db, collection_id, options, session["uuid"])
            return {
                "success": True,
            }

        @server.json_post(f"{prefix}/documents/add")
        def _post_documents_add(
                _req: QSRH, rargs: ReqArgs) -> DocumentResponse:
            args = rargs["post"]
            collection_id = int(args["collection_id"])
            main_ids: list[str] = args["main_ids"]
            session: SessionInfo = rargs["meta"]["session"]
            res = add_documents(db, collection_id, main_ids, session["uuid"])
            maybe_start_dive()
            return {
                "document_ids": res,
            }

        @server.json_post(f"{prefix}/documents/list")
        def _post_documents_list(
                _req: QSRH, rargs: ReqArgs) -> DocumentListResponse:
            args = rargs["post"]
            collection_id = int(args["collection_id"])
            session: SessionInfo = rargs["meta"]["session"]
            is_readonly, docs = get_documents(
                db, collection_id, session["uuid"])
            return {
                "documents": docs,
                "is_readonly": is_readonly,
            }

        @server.json_post(f"{prefix}/documents/fulltext")
        def _post_documents_fulltext(
                _req: QSRH, rargs: ReqArgs) -> FulltextResponse:
            args = rargs["post"]
            main_id: str = args["main_id"]
            content, error_msg = get_full_text(main_id)
            return {
                "content": normalize_text(content),
                "error": error_msg,
            }

        @server.json_post(f"{prefix}/documents/requeue")
        def _post_documents_requeue(
                _req: QSRH, rargs: ReqArgs) -> RequeueResponse:
            args = rargs["post"]
            collection_id = int(args["collection_id"])
            main_ids: list[str] = args["main_ids"]
            meta_only = to_bool(args.get("meta_only", False))
            error_only = to_bool(args.get("error_only", False))
            session: SessionInfo = rargs["meta"]["session"]
            if meta_only:
                requeue_meta(db, collection_id, session["uuid"], main_ids)
            elif error_only:
                requeue_error(db, collection_id, session["uuid"], main_ids)
            else:
                requeue(db, collection_id, session["uuid"], main_ids)
            maybe_start_dive()
            return {
                "done": True,
            }

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
            "has_vecdb": False,
            "has_llm": False,
            "vecdb_ready": False,
            "vecdbs": [],
            "deepdives": [],
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
