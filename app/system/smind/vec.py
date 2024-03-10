from typing import Literal, TypedDict

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    ScoredPoint,
    VectorParams,
)

from app.system.config import Config


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


EMBED_SIZE = 384  # 768  # FIXME: read from graph definition


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


def build_db_name(
        name: str,
        *,
        distance_fn: DistanceFn,
        db: QdrantClient | None) -> str:
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
        config = VectorParams(size=EMBED_SIZE, distance=distance)
        db.recreate_collection(collection_name=name, vectors_config=config)
    return name


def add_embed(db: QdrantClient, name: str, chunks: list[EmbedChunk]) -> int:

    def convert_chunk(chunk: EmbedChunk) -> PointStruct:
        point_id = f"{chunk['base']}:{chunk['doc_id']}:{chunk['chunk_id']}"
        payload = {
            "doc_id": chunk["doc_id"],
            "base": chunk["base"],
            "url": chunk["url"],
            "snippet": chunk["snippet"],
        }
        for key, value in chunk["meta"].items():
            payload[f"meta:{key}"] = value
        return PointStruct(id=point_id, vector=chunk["embed"], payload=payload)

    db.upsert(
        collection_name=name,
        points=[convert_chunk(chunk) for chunk in chunks])
    return len(chunks)


def query_embed(
        db: QdrantClient,
        name: str,
        embed: list[float],
        *,
        limit: int,
        offset: int | None = None) -> list[ResultChunk]:
    hits = db.search(
        collection_name=name,
        query_vector=embed,
        offset=offset,
        limit=limit)

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
            "vector_id": f"{hit.id}",
            "score": hit.score,
            "base": payload["base"],
            "doc_id": payload["doc_id"],
            "snippet": payload["snippet"],
            "url": payload["url"],
            "meta": meta,
        }

    return [convert_chunk(hit) for hit in hits]