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
    PointStruct,
    ScoredPoint,
    VectorParams,
)

from app.system.config import Config


QDRANT_UUID = uuid.UUID("5c349547-396f-47e1-b0fb-22ed665bc112")


VecDBStat = TypedDict('VecDBStat', {
    "name": str,
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


EmbedChunk = TypedDict('EmbedChunk', {
    "doc_id": int,
    "chunk_id": int,
    "base": str,
    "embed": list[float],
    "url": str,
    "snippet": str,
    "meta": dict[str, str | int | bool],
})


ResultChunk = TypedDict('ResultChunk', {
    "score": float,
    "vector_id": str,
    "doc_id": int,
    "base": str,
    "url": str,
    "snippet": str,
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
            api_key=token)
    return db


def get_vec_stats(db: QdrantClient, name: str) -> VecDBStat | None:
    try:
        status = db.get_collection(collection_name=name)
        count = db.count(collection_name=name)
        return {
            "name": name,
            "status": status.status,
            "count": count.count,
        }
    except (UnexpectedResponse, ResponseHandlingException):
        return None


def build_db_name(
        name: str,
        *,
        distance_fn: DistanceFn,
        embed_size: int,
        db: QdrantClient,
        force_clear: bool) -> str:
    name = f"{ensure_valid_name(name)}-{distance_fn}"
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
                collection_name=name,
                vectors_config=config,
                optimizers_config=optimizers,
                on_disk_payload=True)

        if force_clear:
            recreate()
        else:
            try:
                status = db.get_collection(collection_name=name)
                print(f"load {name}: {status.status}")
            except (UnexpectedResponse, ResponseHandlingException):
                print(traceback.format_exc())
                recreate()
    return name


def add_embed(
        db: QdrantClient,
        name: str,
        chunks: list[EmbedChunk]) -> tuple[int, int]:
    # TODO: potentially separate meta data storage
    print(f"add_embed {name} {len(chunks)} items")
    base = None
    doc_id = None
    for chunk in chunks:
        if base is None:
            base = chunk["base"]
        elif base != chunk["base"]:
            raise ValueError("all chunks must be from the same document")
        if doc_id is None:
            doc_id = chunk["doc_id"]
        elif doc_id != chunk["doc_id"]:
            raise ValueError("all chunks must be from the same document")
    if base is None or doc_id is None:
        return (0, 0)

    def convert_chunk(chunk: EmbedChunk) -> PointStruct:
        point_id = f"{chunk['base']}:{chunk['doc_id']}:{chunk['chunk_id']}"
        payload = {
            "vector_id": point_id,
            "doc_id": chunk["doc_id"],
            "base": chunk["base"],
            "url": chunk["url"],
            "snippet": chunk["snippet"],
        }
        for key, value in chunk["meta"].items():
            payload[f"meta:{key}"] = value
        print(f"insert {point_id} ({len(chunk['embed'])})")
        return PointStruct(
            id=f"{uuid.uuid5(QDRANT_UUID, point_id)}",
            vector=chunk["embed"],
            payload=payload)

    filter_docs = Filter(
        must=[
            FieldCondition(key="base", match=MatchValue(value=base)),
            FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
        ])
    count_res = db.count(
        collection_name=name,
        count_filter=filter_docs,
        exact=True)
    db.delete(
        collection_name=name,
        points_selector=FilterSelector(filter=filter_docs))
    db.upsert(
        collection_name=name,
        points=[convert_chunk(chunk) for chunk in chunks])
    return (count_res.count, len(chunks))


def query_embed(
        db: QdrantClient,
        name: str,
        embed: list[float],
        *,
        limit: int,
        offset: int | None,
        score_threshold: float | None,
        filter_base: list[str] | None,
        filter_meta: dict[str, list[str]] | None) -> list[ResultChunk]:
    # TODO: maybe use grouping
    print(f"query {name} offset={offset} limit={limit}")
    query_filter = None
    if filter_base is not None or filter_meta is not None:
        conds: list[Condition] = []
        if filter_base is not None:
            conds.append(
                FieldCondition(key="base", match=MatchAny(any=filter_base)))
        if filter_meta is not None:
            for meta_key, meta_values in filter_meta.items():
                conds.append(FieldCondition(
                    key=f"meta:{meta_key}",
                    match=MatchAny(any=meta_values)))
        query_filter = Filter(must=conds)
    hits = db.search(
        collection_name=name,
        query_vector=embed,
        offset=offset,
        limit=limit,
        score_threshold=score_threshold,
        query_filter=query_filter)

    def convert_chunk(hit: ScoredPoint) -> ResultChunk:
        payload = hit.payload
        assert payload is not None
        meta = {}
        for key, value in payload.items():
            meta_key = key.removeprefix("meta:")
            if meta_key == key:
                continue
            meta[meta_key] = value
        return {
            "vector_id": payload["vector_id"],
            "score": hit.score,
            "base": payload["base"],
            "doc_id": payload["doc_id"],
            "snippet": payload["snippet"],
            "url": payload["url"],
            "meta": meta,
        }

    return [convert_chunk(hit) for hit in hits]
