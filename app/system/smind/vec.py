import collections
import re
import time
import uuid
from collections.abc import Callable
from typing import cast, Literal, TypeAlias, TypedDict

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import (
    ResponseHandlingException,
    UnexpectedResponse,
)
from qdrant_client.models import (
    Condition,
    DatetimeRange,
    Direction,
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchAny,
    MatchValue,
    OptimizersConfig,
    OrderBy,
    Payload,
    PointGroup,
    PointStruct,
    Record,
    VectorParams,
    WithLookup,
)
from redipy import Redis

from app.misc.util import get_time_str, parse_time_str
from app.system.config import Config


QDRANT_UUID = uuid.UUID("5c349547-396f-47e1-b0fb-22ed665bc112")
REF_KEY: Literal["main_uuid"] = "main_uuid"
DUMMY_VEC: list[float] = [1.0]


KEY_REGEX = re.compile(r"[a-z_0-9]+")
META_PREFIX = "meta_"
FORBIDDEN_META = ["base"]

ExternalKey: TypeAlias = str
InternalKey: TypeAlias = str

FIELDS_PREFIX = "fields"


StatEmbed = TypedDict('StatEmbed', {
    "doc_count": int,
    "fields": dict[ExternalKey, dict[str, int]],
})


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
    "meta": dict[ExternalKey, list[str] | str],
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
    "meta": dict[ExternalKey, list[str] | str],
})


FILE_PROTOCOL = "file://"


def convert_meta_key(key: ExternalKey) -> InternalKey:
    if KEY_REGEX.fullmatch(key) is None:
        raise ValueError(f"key '{key}' is not valid as meta key")
    if key in FORBIDDEN_META:
        raise ValueError(f"key '{key}' cannot be one of {FORBIDDEN_META}")
    return f"{META_PREFIX}{key}"


def unconvert_meta_key(key: InternalKey) -> ExternalKey | None:
    res = key.removeprefix(META_PREFIX)
    if res == key:
        return None
    return res


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


def vec_flushall(db: QdrantClient, redis: Redis) -> None:
    for collection in db.get_collections().collections:
        db.delete_collection(collection.name)
    redis.flushall()


def get_vec_stats(
        db: QdrantClient, name: str, *, is_vec: bool) -> VecDBStat | None:
    try:
        db_name = get_db_name(name, is_vec=is_vec)
        if not db.collection_exists(db_name):
            return None
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
        redis: Redis,
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

            for key in redis.keys(match=f"{name}:*", block=False):
                redis.delete(key)

            db.delete_payload_index(data_name, "main_id")
            db.create_payload_index(data_name, "main_id", "keyword")

            db.delete_payload_index(data_name, "base")
            db.create_payload_index(data_name, "base", "keyword")

            date_key = convert_meta_key("date")
            db.delete_payload_index(data_name, date_key)
            db.create_payload_index(data_name, date_key, "datetime")

            status_key = convert_meta_key("status")
            db.delete_payload_index(data_name, status_key)
            db.create_payload_index(data_name, status_key, "keyword")

            language_key = convert_meta_key("language")
            db.delete_payload_index(data_name, language_key)
            db.create_payload_index(data_name, language_key, "keyword")

            iso3_key = convert_meta_key("iso3")
            db.delete_payload_index(data_name, iso3_key)
            db.create_payload_index(data_name, iso3_key, "keyword")

        if not force_clear:
            need_create = False
            conn_error = 0
            while True:
                try:
                    vec_name = get_db_name(name, is_vec=True)
                    if db.collection_exists(collection_name=vec_name):
                        vec_status = db.get_collection(
                            collection_name=vec_name)
                        print(f"load {vec_name}: {vec_status.status}")
                    else:
                        need_create = True
                    data_name = get_db_name(name, is_vec=False)
                    if db.collection_exists(collection_name=data_name):
                        data_status = db.get_collection(
                            collection_name=data_name)
                        print(f"load {data_name}: {data_status.status}")
                    else:
                        need_create = True
                    break
                except (UnexpectedResponse, ResponseHandlingException):
                    conn_error += 1
                    if conn_error > 10:
                        raise
                    time.sleep(10.0)
        if force_clear or need_create:
            recreate()
    return name


def add_embed(
        db: QdrantClient,
        redis: Redis,
        *,
        name: str,
        data: EmbedMain,
        chunks: list[EmbedChunk],
        update_meta_only: bool) -> tuple[int, int]:
    new_count = len(chunks)
    if update_meta_only and new_count > 0:
        raise ValueError("'update_meta_only' requires chunks to be empty")
    print(f"add_embed {name} {new_count} items")
    base = data["base"]
    redis_base_key = f"{FIELDS_PREFIX}:base:{base}"
    main_id = f"{base}:{data['doc_id']}"
    main_uuid = f"{uuid.uuid5(QDRANT_UUID, main_id)}"

    def convert_chunk(chunk: EmbedChunk) -> PointStruct:
        point_id = f"{main_id}:{chunk['chunk_id']}"
        point_uuid = f"{uuid.uuid5(QDRANT_UUID, point_id)}"
        point_payload = {
            REF_KEY: main_uuid,
            "vector_id": point_id,
            "snippet": chunk["snippet"],
        }
        print(f"insert {point_id} ({len(chunk['embed'])})")
        return PointStruct(
            id=point_uuid,
            vector=chunk["embed"],
            payload=point_payload)

    meta_obj = data["meta"]
    data_name = get_db_name(name, is_vec=False)
    filter_data = Filter(
        must=[
            FieldCondition(key="main_id", match=MatchValue(value=main_id)),
        ])
    # FIXME: split in multiple calls using offset?
    prev_data, _ = db.scroll(
        collection_name=data_name,
        scroll_filter=filter_data,
        with_payload=True)
    meta_keys: set[ExternalKey] = set(meta_obj.keys())
    prev_meta: dict[ExternalKey, list[str] | str] = {}
    if len(prev_data):
        prev_payload = prev_data[0].payload
        assert prev_payload is not None
        prev_meta = fill_meta(prev_payload)
        meta_keys.update(prev_meta.keys())

    if "date" not in prev_meta and "date" not in meta_obj:
        meta_obj["date"] = get_time_str()
        meta_keys.add("date")

    def get_vals(val: list[str] | str) -> set[str]:
        if not val:
            return set()
        if isinstance(val, list):
            return set(val)
        return {val}

    def convert_val_for_redis(key: ExternalKey, val: str) -> str:
        if key == "date":
            dt = parse_time_str(val)
            return dt.date().isoformat()
        return val

    with redis.pipeline() as pipe:
        for meta_key in meta_keys:
            cur_new = get_vals(meta_obj.get(meta_key, []))
            cur_old = get_vals(prev_meta.get(meta_key, []))
            for val in cur_new.difference(cur_old):
                val = convert_val_for_redis(meta_key, val)
                pipe.sadd(f"{FIELDS_PREFIX}:{meta_key}:{val}", main_id)
            for val in cur_old.difference(cur_new):
                val = convert_val_for_redis(meta_key, val)
                pipe.srem(f"{FIELDS_PREFIX}:{meta_key}:{val}", main_id)

    main_payload = {
        "main_id": main_id,
        "doc_id": data["doc_id"],
        "base": base,
        "url": data["url"],
    }
    for key, value in meta_obj.items():
        meta_key = convert_meta_key(key)
        main_payload[meta_key] = value

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
    vec_name = get_db_name(name, is_vec=True)
    filter_docs = Filter(
        must=[
            FieldCondition(key=REF_KEY, match=MatchValue(value=main_uuid)),
        ])
    count_res = db.count(
        collection_name=vec_name,
        count_filter=filter_docs,
        exact=True)
    prev_count = count_res.count
    if prev_count > new_count or new_count == 0:
        db.delete(
            collection_name=vec_name,
            points_selector=FilterSelector(filter=filter_docs))
        if new_count == 0:
            redis.srem(redis_base_key, main_id)
            db.delete(
                collection_name=data_name,
                points_selector=FilterSelector(filter=filter_docs))
    else:
        redis.sadd(redis_base_key, main_id)
    if chunks:
        db.upsert(
            collection_name=vec_name,
            points=[convert_chunk(chunk) for chunk in chunks])
    return (prev_count, new_count)


def stat_embed(
        db: QdrantClient,
        redis: Redis,
        name: str,
        *,
        filters: dict[str, list[str]] | None) -> StatEmbed:
    query_filter = None if filters is None else get_filter(filters)
    data_name = get_db_name(name, is_vec=False)
    count_res = db.count(
        collection_name=data_name,
        count_filter=query_filter,
        exact=True)
    fields: collections.defaultdict[str, dict[str, int]] = \
        collections.defaultdict(dict)
    if filters is None:
        for key in redis.keys(match=f"{FIELDS_PREFIX}:*", block=False):
            _, f_name, f_value = key.split(":", 2)
            fields[f_name][f_value] = redis.scard(key)
    else:
        # FIXME: split in multiple calls using offset?
        main_ids_data, _ = db.scroll(
            collection_name=data_name,
            scroll_filter=query_filter,
            with_payload=["main_id"])
        main_ids = {
            data.payload["main_id"]
            for data in main_ids_data
            if data.payload is not None
        }
        for key in redis.keys(match=f"{FIELDS_PREFIX}:*", block=False):
            _, f_name, f_value = key.split(":", 2)
            # FIXME use redis intersection function
            f_count = len(main_ids.intersection(redis.smembers(key)))
            fields[f_name][f_value] = f_count
    return {
        "doc_count": count_res.count,
        "fields": fields,
    }


def fill_meta(payload: Payload) -> dict[ExternalKey, list[str] | str]:
    meta = {}
    for key, value in payload.items():
        meta_key = unconvert_meta_key(key)
        if meta_key is None:
            continue
        meta[meta_key] = value
    return meta


def get_filter(filters: dict[ExternalKey, list[str]]) -> Filter:
    conds: list[Condition] = []
    for key, values in filters.items():
        if not values:
            continue
        if key == "date":
            if len(values) != 2:
                raise ValueError(
                    f"date filter must be exactly two dates got {values}")
            key = convert_meta_key(key)
            dates = [parse_time_str(value) for value in values]
            conds.append(FieldCondition(
                key=key, range=DatetimeRange(gte=min(dates), lte=max(dates))))
            continue
        if key not in FORBIDDEN_META:
            key = convert_meta_key(key)
        conds.append(FieldCondition(key=key, match=MatchAny(any=values)))
    return Filter(must=conds)


def create_filter_fn(
        filters: dict[ExternalKey, list[str]] | None,
        ) -> Callable[[ResultChunk], bool]:
    if filters is None:
        return lambda _: True
    filters_conv: dict[ExternalKey, set[str]] = {
        key: set(values)
        for key, values in filters.items()
        if values
    }

    def filter_fn(chunk: ResultChunk) -> bool:
        for key, values in filters_conv.items():
            if key in FORBIDDEN_META:
                other_val: str | None = cast(dict, chunk).get(key)
                if other_val is None:
                    continue
                other_vals: list[str] | None = [other_val]
            else:
                vals = chunk["meta"].get(key)
                if vals is None or isinstance(vals, list):
                    other_vals = vals
                else:
                    other_vals = [vals]
            if other_vals is None:
                continue
            if values.isdisjoint(other_vals):
                return False
        return True

    return filter_fn


def query_embed_emu_filters(
        db: QdrantClient,
        name: str,
        embed: list[float],
        *,
        offset: int | None,
        limit: int,
        hit_limit: int,
        score_threshold: float | None,
        filters: dict[ExternalKey, list[str]] | None) -> list[ResultChunk]:
    real_offset = 0 if offset is None else offset
    total_limit = real_offset + limit
    filter_fn = create_filter_fn(filters)
    cur_offset = 0
    cur_limit = limit
    cur_res: list[ResultChunk] = []
    reached_end = False
    while not reached_end and len(cur_res) < total_limit:
        candidates = query_embed(
            db,
            name,
            embed,
            offset=cur_offset,
            limit=cur_limit,
            hit_limit=hit_limit,
            score_threshold=score_threshold,
            filters=None)
        if len(candidates) < cur_limit:
            reached_end = True
        for cand in candidates:
            if not filter_fn(cand):
                continue
            cur_res.append(cand)
        cur_offset += cur_limit
        cur_limit = min(10000, cur_limit * 2)
    return cur_res[real_offset:total_limit]


def query_embed(
        db: QdrantClient,
        name: str,
        embed: list[float],
        *,
        offset: int | None,
        limit: int,
        hit_limit: int,
        score_threshold: float | None,
        filters: dict[ExternalKey, list[str]] | None) -> list[ResultChunk]:
    real_offset = 0 if offset is None else offset
    total_limit = real_offset + limit
    print(f"query {name} offset={real_offset} limit={total_limit}")
    query_filter = None if filters is None else get_filter(filters)
    vec_name = get_db_name(name, is_vec=True)
    data_name = get_db_name(name, is_vec=False)
    hits = db.search_groups(
        collection_name=vec_name,
        query_vector=embed,
        group_by=REF_KEY,
        limit=total_limit,
        group_size=hit_limit,
        score_threshold=score_threshold,
        query_filter=query_filter,
        with_lookup=WithLookup(collection=data_name, with_payload=True))

    def convert_chunk(group: PointGroup) -> ResultChunk:
        score = None
        snippets = []
        for hit in group.hits:
            if score is None:
                score = hit.score
            hit_payload = hit.payload
            assert hit_payload is not None
            snippets.append(hit_payload["snippet"])
        assert score is not None
        lookup = group.lookup
        assert lookup is not None
        data_payload = lookup.payload
        assert data_payload is not None
        meta = fill_meta(data_payload)
        base = data_payload["base"]
        doc_id = data_payload["doc_id"]
        url = data_payload["url"]
        main_id = data_payload["main_id"]
        return {
            "main_id": main_id,
            "score": score,
            "base": base,
            "doc_id": doc_id,
            "snippets": snippets,
            "url": url,
            "meta": meta,
        }

    return [
        convert_chunk(group)
        for group in hits.groups[real_offset:total_limit]
    ]


def query_docs(
        db: QdrantClient,
        name: str,
        *,
        offset: int | None,
        limit: int,
        filters: dict[ExternalKey, list[str]] | None) -> list[ResultChunk]:
    real_offset = 0 if offset is None else offset
    total_limit = real_offset + limit
    print(f"scroll {name} offset={real_offset} limit={total_limit}")
    data_name = get_db_name(name, is_vec=False)
    query_filter = None if filters is None else get_filter(filters)
    hits, _ = db.scroll(
        collection_name=data_name,
        order_by=OrderBy(
            key=convert_meta_key("date"),
            direction=Direction.DESC),
        offset=0,
        limit=total_limit,
        scroll_filter=query_filter,
        with_payload=True)

    def convert_hit(hit: Record) -> ResultChunk:
        data_payload = hit.payload
        assert data_payload is not None
        meta = fill_meta(data_payload)
        base = data_payload["base"]
        doc_id = data_payload["doc_id"]
        url = data_payload["url"]
        main_id = data_payload["main_id"]
        return {
            "main_id": main_id,
            "score": 1.0,
            "base": base,
            "doc_id": doc_id,
            "snippets": [],
            "url": url,
            "meta": meta,
        }

    return [
        convert_hit(hit)
        for hit in hits[real_offset:total_limit]
    ]
