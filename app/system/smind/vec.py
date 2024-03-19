import re
import traceback
import uuid
from typing import Literal, TypedDict

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import (
    ResponseHandlingException,
    UnexpectedResponse,
)
from qdrant_client.models import (
    Condition,
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchAny,
    MatchValue,
    OptimizersConfig,
    Payload,
    PointGroup,
    PointStruct,
    Record,
    ScoredPoint,
    VectorParams,
    WithLookup,
)

from app.system.config import Config


QDRANT_UUID = uuid.UUID("5c349547-396f-47e1-b0fb-22ed665bc112")
REF_KEY: Literal["main_id"] = "main_id"
DUMMY_VEC: list[float] = [1.0]


KEY_REGEX = re.compile(r"[a-z_0-9]+")
META_PREFIX = "meta_"
FORBIDDEN_META = ["base"]


def convert_meta_key(key: str) -> str:
    if KEY_REGEX.fullmatch(key) is None:
        raise ValueError(f"key '{key}' is not valid as meta key")
    if key in FORBIDDEN_META:
        raise ValueError(f"key '{key}' cannot be one of {FORBIDDEN_META}")
    return f"{META_PREFIX}{key}"


def unconvert_meta_key(key: str) -> str | None:
    res = key.removeprefix(META_PREFIX)
    if res == key:
        return None
    return res


VecDBStat = TypedDict('VecDBStat', {
    "name": str,
    "db_name": str,
    "status": str,
    "count": int,
})


VecDBConfig = TypedDict('VecDBConfig', {
    "host": str,
    "port": int,
    "grpc": int,
    "token": str | None,
})


DistanceFn = Literal[
    "cos",
    "dot",
    "man",
    "euc",
]


EmbedMain = TypedDict('EmbedMain', {
    "doc_id": int,
    "base": str,
    "url": str,
    "meta": dict[str, str | int | bool],
})


EmbedChunk = TypedDict('EmbedChunk', {
    "chunk_id": int,
    "embed": list[float],
    "snippet": str,
})


ResultChunk = TypedDict('ResultChunk', {
    "main_id": str,
    "score": float,
    "doc_id": int,
    "base": str,
    "url": str,
    "snippets": list[str],
    "meta": dict[str, str | int | bool],
})


FILE_PROTOCOL = "file://"


def ensure_valid_name(name: str) -> str:
    if "-" in name or ":" in name:
        raise ValueError(f"invalid name {name}")
    return name


def get_vec_client(config: Config) -> QdrantClient:
    vec_db = config["vector"]
    host = vec_db["host"]
    if host.startswith(FILE_PROTOCOL):
        print(f"loading db file: {host.removeprefix(FILE_PROTOCOL)}")
        db = QdrantClient(path=host.removeprefix(FILE_PROTOCOL))
    else:
        print(f"loading db: {host}")
        token = vec_db["token"]
        if not token:
            token = None
        db = QdrantClient(
            host=host,
            port=vec_db["port"],
            grpc_port=vec_db["grpc"],
            https=False,
            # prefer_grpc=True,
            api_key=token)
    return db


def vec_flushall(db: QdrantClient) -> None:
    for collection in db.get_collections().collections:
        db.delete_collection(collection.name)


def get_vec_stats(
        db: QdrantClient, name: str, *, is_vec: bool) -> VecDBStat | None:
    try:
        db_name = get_db_name(name, is_vec=is_vec)
        status = db.get_collection(collection_name=db_name)
        count = db.count(collection_name=db_name)
        return {
            "name": name,
            "db_name": db_name,
            "status": status.status,
            "count": count.count,
        }
    except (UnexpectedResponse, ResponseHandlingException):
        return None


def get_db_name(name: str, *, is_vec: bool) -> str:
    return f"{name}_vec" if is_vec else f"{name}_data"


def build_db_name(
        name: str,
        *,
        distance_fn: DistanceFn,
        embed_size: int,
        db: QdrantClient,
        force_clear: bool) -> str:
    name = f"{ensure_valid_name(name)}_{distance_fn}"
    if db is not None:
        if distance_fn == "dot":
            distance: Distance = Distance.DOT
        elif distance_fn == "cos":
            distance = Distance.COSINE
        elif distance_fn == "euc":
            distance = Distance.EUCLID
        elif distance_fn == "man":
            distance = Distance.MANHATTAN
        else:
            raise ValueError(f"invalid distance name: {distance_fn}")

        def recreate() -> None:
            print(f"create {name} size={embed_size} distance={distance}")
            vec_name = get_db_name(name, is_vec=True)
            config = VectorParams(
                size=embed_size,
                distance=distance,
                on_disk=True)
            optimizers = OptimizersConfig(
                deleted_threshold=0.2,
                vacuum_min_vector_number=1000,
                default_segment_number=0,
                memmap_threshold=512*1024,
                indexing_threshold=512*1024,
                flush_interval_sec=60,
                max_optimization_threads=4)
            db.recreate_collection(
                collection_name=vec_name,
                vectors_config=config,
                optimizers_config=optimizers,
                on_disk_payload=True)

            data_name = get_db_name(name, is_vec=False)
            db.recreate_collection(
                collection_name=data_name,
                vectors_config=VectorParams(size=1, distance=distance),
                on_disk_payload=True)

            db.delete_payload_index(data_name, REF_KEY)
            db.create_payload_index(data_name, REF_KEY, "keyword")

        if not force_clear:
            need_create = False
            try:
                vec_name = get_db_name(name, is_vec=True)
                if db.collection_exists(collection_name=vec_name):
                    vec_status = db.get_collection(collection_name=vec_name)
                    print(f"load {vec_name}: {vec_status.status}")
                else:
                    need_create = True
                data_name = get_db_name(name, is_vec=False)
                if db.collection_exists(collection_name=data_name):
                    data_status = db.get_collection(collection_name=data_name)
                    print(f"load {data_name}: {data_status.status}")
                else:
                    need_create = True
            except (UnexpectedResponse, ResponseHandlingException):
                print(traceback.format_exc())
                need_create = True
        if force_clear or need_create:
            recreate()
    return name


def add_embed(
        db: QdrantClient,
        *,
        name: str,
        data: EmbedMain,
        chunks: list[EmbedChunk],
        update_meta_only: bool) -> tuple[int, int]:
    new_count = len(chunks)
    if update_meta_only and new_count > 0:
        raise ValueError("'update_meta_only' requires chunks to be empty")
    print(f"add_embed {name} {new_count} items")
    main_id = f"{data['base']}:{data['doc_id']}"
    main_uuid = f"{uuid.uuid5(QDRANT_UUID, main_id)}"
    main_payload = {
        REF_KEY: main_id,
        "doc_id": data["doc_id"],
        "base": data["base"],
        "url": data["url"],
    }
    point_payload_template: dict[str, str | int | bool] = {
        "doc_id": data["doc_id"],
        "base": data["base"],
        "url": data["url"],
    }
    for key, value in data["meta"].items():
        meta_key = convert_meta_key(key)
        main_payload[meta_key] = value
        point_payload_template[meta_key] = value

    def convert_chunk(chunk: EmbedChunk) -> PointStruct:
        point_id = f"{main_id}:{chunk['chunk_id']}"
        point_uuid = f"{uuid.uuid5(QDRANT_UUID, point_id)}"
        point_payload = {
            REF_KEY: main_id,
            "vector_id": point_id,
            "snippet": chunk["snippet"],
            **point_payload_template,
        }
        print(f"insert {point_id} ({len(chunk['embed'])})")
        return PointStruct(
            id=point_uuid,
            vector=chunk["embed"],
            payload=point_payload)

    data_name = get_db_name(name, is_vec=False)
    db.upsert(
        collection_name=data_name,
        points=[
            PointStruct(
                id=main_uuid,
                vector=DUMMY_VEC,
                payload=main_payload),
        ])
    if update_meta_only:
        return (0, 0)
    filter_docs = Filter(
        must=[
            FieldCondition(key=REF_KEY, match=MatchValue(value=main_id)),
        ])
    vec_name = get_db_name(name, is_vec=True)
    count_res = db.count(
        collection_name=vec_name,
        count_filter=filter_docs,
        exact=True)
    prev_count = count_res.count
    if prev_count > new_count or new_count == 0:
        db.delete(
            collection_name=vec_name,
            points_selector=FilterSelector(filter=filter_docs))
    if chunks:
        db.upsert(
            collection_name=vec_name,
            points=[convert_chunk(chunk) for chunk in chunks])
    return (prev_count, new_count)


def get_filter(filters: dict[str, list[str]]) -> Filter:
    conds: list[Condition] = []
    for key, values in filters.items():
        if not values:
            continue
        if key not in FORBIDDEN_META:
            key = convert_meta_key(key)
        conds.append(FieldCondition(key=key, match=MatchAny(any=values)))
    return Filter(must=conds)


def query_embed(
        db: QdrantClient,
        name: str,
        embed: list[float],
        *,
        offset: int | None,
        limit: int,
        hit_limit: int,
        score_threshold: float | None,
        filters: dict[str, list[str]] | None) -> list[ResultChunk]:
    print(f"query {name} offset={offset} limit={limit}")
    query_filter = None if filters is None else get_filter(filters)
    vec_name = get_db_name(name, is_vec=True)
    data_name = get_db_name(name, is_vec=False)
    # FIXME make search work on lookup (data instead of vec)
    hits = db.search_groups(
        collection_name=vec_name,
        query_vector=embed,
        group_by=REF_KEY,
        limit=limit,
        group_size=hit_limit,
        score_threshold=score_threshold,
        query_filter=query_filter,
        with_lookup=WithLookup(collection=data_name, with_payload=True))

    def fill_meta(payload: Payload) -> dict[str, str | int | bool]:
        meta = {}
        for key, value in payload.items():
            meta_key = unconvert_meta_key(key)
            if meta_key is None:
                continue
            meta[meta_key] = value
        return meta

    def convert_chunk(group: PointGroup) -> ResultChunk:
        ref_id = f"{group.id}"
        score = None
        meta = None
        base = None
        doc_id = None
        url = None
        snippets = []
        for hit in group.hits:
            if score is None:
                score = hit.score
            hit_payload = hit.payload
            assert hit_payload is not None
            snippets.append(hit_payload["snippet"])
            # FIXME: try avoid storing meta data in vec points
            if meta is None:
                meta = fill_meta(hit_payload)
            if base is None:
                base = hit_payload["base"]
            if doc_id is None:
                doc_id = hit_payload["doc_id"]
            if url is None:
                url = hit_payload["url"]
        assert score is not None
        lookup: Record | ScoredPoint | None = group.lookup
        # FIXME: figure out why lookup does not work
        if meta is None or base is None or doc_id is None or url is None:
            if lookup is None:
                filter_cur = Filter(
                    must=[
                        FieldCondition(
                            key=REF_KEY, match=MatchValue(value=group.id)),
                    ])
                lookups = db.search(
                    data_name, DUMMY_VEC, query_filter=filter_cur, limit=1)
                if not lookups:
                    return {
                        REF_KEY: ref_id,
                        "score": score,
                        "base": "?" if base is None else base,
                        "doc_id": -1 if doc_id is None else doc_id,
                        "snippets": snippets,
                        "url": "?" if url is None else url,
                        "meta": {} if meta is None else meta,
                    }
                lookup = lookups[0]
            data_payload = lookup.payload
            assert data_payload is not None
            if meta is None:
                meta = fill_meta(data_payload)
            if base is None:
                base = data_payload["base"]
            if doc_id is None:
                doc_id = data_payload["doc_id"]
            if url is None:
                url = data_payload["url"]
        return {
            REF_KEY: ref_id,
            "score": score,
            "base": base,
            "doc_id": doc_id,
            "snippets": snippets,
            "url": url,
            "meta": meta,
        }

    return [convert_chunk(group) for group in hits.groups]
