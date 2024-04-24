import collections
import hashlib
import time
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import (
    Any,
    cast,
    get_args,
    Literal,
    NotRequired,
    TypeAlias,
    TypedDict,
    TypeVar,
)

from qdrant_client import QdrantClient
from qdrant_client.conversions.common_types import PayloadSchemaType
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
    HnswConfigDiff,
    MatchAny,
    MatchValue,
    OptimizersConfig,
    OrderBy,
    Payload,
    PayloadIndexInfo,
    PointGroup,
    PointStruct,
    Record,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    VectorParams,
    WithLookup,
)

from app.misc.util import get_time_str, parse_time_str
from app.system.config import Config


T = TypeVar('T')


QDRANT_UUID = uuid.UUID("5c349547-396f-47e1-b0fb-22ed665bc112")
REF_KEY: Literal["main_uuid"] = "main_uuid"
DUMMY_VEC: list[float] = [1.0]


META_CAT = "_"
META_PREFIX = f"meta{META_CAT}"


DBName: TypeAlias = str
InternalDataKey: TypeAlias = str
InternalSnippetKey: TypeAlias = str


HashTup: TypeAlias = tuple[str, int]


DocStatus: TypeAlias = Literal["public", "preview"]
DOC_STATUS: tuple[DocStatus] = get_args(DocStatus)


MetaObject = TypedDict('MetaObject', {
    "date": NotRequired[str],
    "status": DocStatus,
    "doc_type": str,
    "language": dict[str, float],
    "iso3": dict[str, float],
})
MetaObjectOpt = TypedDict('MetaObjectOpt', {
    "date": NotRequired[str],
    "status": DocStatus,
    "doc_type": str,
    "language": dict[str, float],
    "iso3": dict[str, float],
}, total=False)
MetaKey = Literal["date", "status", "doc_type", "language", "iso3"]
META_KEYS: set[MetaKey] = set(get_args(MetaKey))
META_SCALAR: set[MetaKey] = {"language", "iso3"}
META_SNIPPET_INDEX: dict[MetaKey, PayloadSchemaType] = {
    "date": "datetime",
    "status": "keyword",
    "doc_type": "keyword",
    "language": "keyword",
    "iso3": "keyword",
}


KNOWN_DOC_TYPES: dict[str, set[str]] = {
    "actionplan": {"action plan"},
    "experiment": {"experiment"},
    "solution": {"solution"},
}
DOC_TYPE_TO_BASE: dict[str, str] = {
    doc_type: base
    for base, doc_types in KNOWN_DOC_TYPES.items()
    for doc_type in doc_types
}


StatEmbed = TypedDict('StatEmbed', {
    "doc_count": int,
    "fields": dict[MetaKey, dict[str, int]],
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
    "title": str,
    "meta": MetaObject,
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
    "title": str,
    "updated": str,
    "snippets": list[str],
    "meta": dict[MetaKey, list[str] | str | int],
})


FILE_PROTOCOL = "file://"


def convert_meta_key_data(
        key: MetaKey, variant: str | None) -> InternalDataKey:
    if key not in META_KEYS:
        raise ValueError(f"{key} is not a valid meta key")
    if key in META_SCALAR and variant is not None:
        return f"{META_PREFIX}{key}{META_CAT}{variant}"
    return f"{META_PREFIX}{key}"


def convert_meta_key_snippet(key: MetaKey) -> InternalSnippetKey:
    if key not in META_KEYS:
        raise ValueError(f"{key} is not a valid meta key")
    return f"{META_PREFIX}{key}"


def unconvert_meta_key_data(
        key: InternalDataKey) -> tuple[MetaKey, str | None] | None:
    res = key.removeprefix(META_PREFIX)
    if res == key:
        return None
    for mkey in META_KEYS:
        m_value = res.removeprefix(mkey)
        if res != m_value:
            value = m_value.removeprefix(META_CAT)
            if value == m_value:
                return (mkey, None)
            return (mkey, value)
    return None


def unconvert_meta_key_snippet(key: InternalSnippetKey) -> MetaKey | None:
    res = key.removeprefix(META_PREFIX)
    if res == key:
        return None
    if res not in META_KEYS:
        return None
    return cast(MetaKey, res)


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


def retry_err(
        call: Callable[..., T],
        *args: Any,
        max_retry: int = 3,
        sleep: float = 3.0) -> T:
    error = 0
    while True:
        try:
            return call(*args)
        except ResponseHandlingException:
            error += 1
            if error > max_retry:
                raise
            if sleep > 0.0:
                time.sleep(sleep)


def vec_flushall(db: QdrantClient) -> None:
    for collection in retry_err(lambda: db.get_collections().collections):
        retry_err(
            lambda name: db.delete_collection(name, timeout=600),
            collection.name)


def get_vec_stats(
        db: QdrantClient, name: str, *, is_vec: bool) -> VecDBStat | None:
    try:
        db_name = get_db_name(name, is_vec=is_vec)
        if not retry_err(lambda: db.collection_exists(db_name)):
            return None
        status = retry_err(
            lambda: db.get_collection(db_name))
        count = retry_err(lambda: db.count(db_name))
        return {
            "name": name,
            "db_name": db_name,
            "status": status.status,
            "count": count.count,
        }
    except (UnexpectedResponse, ResponseHandlingException):
        return None


def get_db_name(name: str, *, is_vec: bool) -> DBName:
    return f"{name}_vec" if is_vec else f"{name}_data"


def build_db_name(
        name: str,
        *,
        distance_fn: DistanceFn,
        embed_size: int,
        db: QdrantClient,
        force_clear: bool,
        force_index: bool) -> str:
    name = f"{ensure_valid_name(name)}_{distance_fn}"
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
        # FIXME test no replication
        print(f"create {name} size={embed_size} distance={distance}")
        vec_name = get_db_name(name, is_vec=True)
        config = VectorParams(
            size=embed_size,
            distance=distance,
            on_disk=True,
            hnsw_config=HnswConfigDiff(
                m=64,
                ef_construct=512,
                full_scan_threshold=10000,
                on_disk=True),
            quantization_config=ScalarQuantization(
                scalar=ScalarQuantizationConfig(
                    type=ScalarType.INT8,
                    always_ram=True)))
        optimizers = OptimizersConfig(
            deleted_threshold=0.2,
            vacuum_min_vector_number=1000,
            default_segment_number=0,
            memmap_threshold=20000,
            indexing_threshold=20000,
            flush_interval_sec=60,
            max_optimization_threads=4)
        db.recreate_collection(
            vec_name,
            vectors_config=config,
            optimizers_config=optimizers,
            on_disk_payload=True,
            replication_factor=3,
            shard_number=6,
            timeout=600)

        data_name = get_db_name(name, is_vec=False)
        db.recreate_collection(
            data_name,
            vectors_config=VectorParams(size=1, distance=distance),
            on_disk_payload=True,
            replication_factor=3,
            shard_number=6,
            timeout=600)

    need_create = False
    if not force_clear and not force_index:
        vec_name_read = get_db_name(name, is_vec=True)
        data_name_read = get_db_name(name, is_vec=False)
        if retry_err(
                lambda: db.collection_exists(vec_name_read),
                max_retry=60,
                sleep=5.0):
            vec_status = retry_err(
                lambda: db.get_collection(vec_name_read))
            print(f"load {vec_name_read}: {vec_status.status}")
        else:
            need_create = True
        if retry_err(
                lambda: db.collection_exists(data_name_read)):
            data_status = retry_err(
                lambda: db.get_collection(data_name_read))
            print(f"load {data_name_read}: {data_status.status}")
        else:
            need_create = True
    if force_clear or need_create:
        recreate()
        force_index = True
    if force_index:
        recreate_index(db, name, force_recreate=True)
    return name


def create_index(
        db: QdrantClient,
        db_name: DBName,
        field_name: str,
        field_schema: PayloadSchemaType,
        *,
        db_schema: dict[str, PayloadIndexInfo],
        force_recreate: bool) -> None:
    if force_recreate:
        retry_err(
            lambda key: db.delete_payload_index(db_name, key), field_name)
    else:
        schema = db_schema.get(field_name)
        if schema is not None and schema.data_type == field_schema:
            return
    db.create_payload_index(db_name, field_name, field_schema, wait=False)


def recreate_index(
        db: QdrantClient, name: str, *, force_recreate: bool) -> None:
    # * vec keys *
    vec_name = get_db_name(name, is_vec=True)
    vec_schema = db.get_collection(vec_name).payload_schema

    create_index(
        db,
        vec_name,
        "base",
        "keyword",
        db_schema=vec_schema,
        force_recreate=force_recreate)

    # * data keys *
    data_name = get_db_name(name, is_vec=False)
    data_schema = db.get_collection(vec_name).payload_schema

    create_index(
        db,
        data_name,
        "main_id",
        "keyword",
        db_schema=data_schema,
        force_recreate=force_recreate)
    create_index(
        db,
        data_name,
        "base",
        "keyword",
        db_schema=data_schema,
        force_recreate=force_recreate)

    # * meta keys *
    for meta_key in META_KEYS:
        snippet_meta_key = convert_meta_key_snippet(meta_key)
        index_type = META_SNIPPET_INDEX[meta_key]
        create_index(
            db,
            vec_name,
            snippet_meta_key,
            index_type,
            db_schema=vec_schema,
            force_recreate=force_recreate)
        data_meta_key = convert_meta_key_data(meta_key, None)
        create_index(
            db,
            data_name,
            data_meta_key,
            index_type,
            db_schema=vec_schema,
            force_recreate=force_recreate)


def build_scalar_index(db: QdrantClient, name: str) -> None:
    recreate_index(db, name, force_recreate=False)
    data_name = get_db_name(name, is_vec=False)
    data_schema = db.get_collection(data_name).payload_schema
    for meta_key in META_SCALAR:
        # NOTE: no caching!
        stats = stat_embed(db, name, field=meta_key, filters=None)
        for variant in stats.keys():
            data_meta_key = convert_meta_key_data(meta_key, variant)
            create_index(
                db,
                data_name,
                data_meta_key,
                "float",
                db_schema=data_schema,
                force_recreate=False)


def full_scroll(
        db: QdrantClient,
        name: str,
        *,
        scroll_filter: Filter | None,
        with_payload: bool | Sequence[str]) -> list[Record]:
    offset = None
    cur_limit = 10
    res: list[Record] = []
    while True:
        cur, next_offset = db.scroll(
            name,
            scroll_filter=scroll_filter,
            offset=offset,
            limit=cur_limit,
            with_payload=with_payload)
        res.extend(cur)
        print(
            f"scroll with offset={offset} limit={cur_limit} "
            f"chunk={len(cur)} results={len(res)} next={next_offset}")
        if next_offset is None:
            break
        offset = next_offset
        cur_limit = int(max(1, min(100, cur_limit * 1.2)))
    return res


def compute_chunk_hash(chunks: list[EmbedChunk]) -> HashTup:
    blake = hashlib.blake2b(digest_size=32)
    blake.update(f"{len(chunks)}:".encode("utf-8"))
    for chunk in chunks:
        snippet = chunk["snippet"]
        blake.update(f"{len(snippet)}:".encode("utf-8"))
        blake.update(snippet.encode("utf-8"))
    return (blake.hexdigest(), len(chunks))


def get_main_id(data: EmbedMain) -> str:
    return f"{data['base']}:{data['doc_id']}"


def get_main_uuid(data: EmbedMain) -> str:
    return f"{uuid.uuid5(QDRANT_UUID, get_main_id(data))}"


def to_data_payload(
        data: EmbedMain,
        chunk_hash: HashTup,
        ) -> dict[InternalDataKey, list[str] | str | float | int]:
    hash_str, count = chunk_hash
    res: dict[InternalDataKey, list[str] | str | float | int] = {
        "main_id": get_main_id(data),
        "doc_id": data["doc_id"],
        "base": data["base"],
        "url": data["url"],
        "title": data["title"],
        "updated": get_time_str(),
        "hash": hash_str,
        "count": count,
    }
    for (mkey, value) in data["meta"].items():
        key = cast(MetaKey, mkey)
        if key in META_SCALAR:
            inner: dict[str, float] = cast(dict, value)
            for variant, scalar in inner.items():
                if scalar > 0.0:
                    res[convert_meta_key_data(key, variant)] = scalar
            res[convert_meta_key_data(key, None)] = [
                variant
                for variant, scalar in sorted(
                    inner.items(), key=lambda item: item[1], reverse=True)
                if scalar > 0.0
            ]
        else:
            val = cast(str | int, value)
            res[convert_meta_key_data(key, None)] = val
    return res


def to_snippet_payload_template(
        data: EmbedMain,
        ) -> dict[InternalSnippetKey, list[str] | str | int]:
    res: dict[InternalSnippetKey, list[str] | str | int] = {
        REF_KEY: get_main_uuid(data),
    }
    for mkey, value in data["meta"].items():
        key = cast(MetaKey, mkey)
        if key in META_SCALAR:
            inner: dict[str, float] = cast(dict, value)
            res[convert_meta_key_snippet(key)] = [
                variant
                for variant, scalar in sorted(
                    inner.items(), key=lambda item: item[1], reverse=True)
                if scalar > 0.0
            ]
        else:
            val = cast(str | int, value)
            res[convert_meta_key_snippet(key)] = val
    return res


def add_embed(
        db: QdrantClient,
        *,
        name: str,
        data: EmbedMain,
        chunks: list[EmbedChunk]) -> tuple[int, int]:
    chunk_hash = compute_chunk_hash(chunks)
    cur_hash, new_count = chunk_hash
    main_id = get_main_id(data)
    main_uuid = get_main_uuid(data)

    data_name = get_db_name(name, is_vec=False)
    filter_data = Filter(
        must=[
            FieldCondition(
                key="main_id",
                match=MatchValue(value=main_id)),
        ])
    prev_data = full_scroll(
        db,
        data_name,
        scroll_filter=filter_data,
        with_payload=["hash", "count"])
    prev_hash: str | None = None
    prev_count: int = 0
    if len(prev_data) > 0:
        prev_payload = prev_data[0].payload
        assert prev_payload is not None
        prev_hash = prev_payload["hash"]
        prev_count = prev_payload["count"]

    meta_obj = data["meta"]
    if meta_obj.get("date") is None:
        meta_obj.pop("date", None)

    base = data["base"]
    doc_type = meta_obj["doc_type"]
    required_doc_types = KNOWN_DOC_TYPES.get(base)
    if required_doc_types is not None and doc_type not in required_doc_types:
        raise ValueError(
            f"base {base} requires doc_type from "
            f"{required_doc_types} not {doc_type}")
    required_base = DOC_TYPE_TO_BASE.get(doc_type)
    if required_base is not None and required_base != base:
        raise ValueError(
            f"doc_type {doc_type} requires base {required_base} != {base}")

    vec_name = get_db_name(name, is_vec=True)

    def empty_previous() -> None:
        if prev_count <= new_count and new_count > 0:
            return
        filter_docs = Filter(
            must=[
                FieldCondition(
                    key=REF_KEY,
                    match=MatchValue(value=main_uuid)),
            ])
        retry_err(lambda: db.delete(
            vec_name,
            points_selector=FilterSelector(filter=filter_docs)))

    def insert_chunks() -> None:
        vec_payload_template = to_snippet_payload_template(data)
        all_chunks = [
            convert_chunk(chunk, vec_payload_template)
            for chunk in chunks
        ]
        batch_size = 20
        for offset in range(0, len(all_chunks), batch_size):
            cur_chunks = all_chunks[offset:offset + batch_size]
            print(f"insert range {offset}:{offset + len(cur_chunks)}")
            retry_err(
                lambda cur: db.upsert(vec_name, points=cur, wait=False),
                cur_chunks)

    def convert_chunk(
            chunk: EmbedChunk,
            vec_payload_template: dict[
                InternalSnippetKey, list[str] | str | int],
            ) -> PointStruct:
        point_id = f"{main_id}:{chunk['chunk_id']}"
        point_uuid = f"{uuid.uuid5(QDRANT_UUID, point_id)}"
        point_payload: dict[InternalSnippetKey, list[str] | str | int] = {
            "vector_id": point_id,
            "snippet": chunk["snippet"],
            **vec_payload_template,
        }
        return PointStruct(
            id=point_uuid,
            vector=chunk["embed"],
            payload=point_payload)

    if prev_hash != cur_hash and prev_count != new_count:
        empty_previous()
        if chunks:
            insert_chunks()

    if new_count != 0:
        retry_err(lambda: db.upsert(
            data_name,
            points=[
                PointStruct(
                    id=main_uuid,
                    vector=DUMMY_VEC,
                    payload=to_data_payload(data, chunk_hash)),
            ],
            wait=False))
    else:
        retry_err(lambda: db.delete(
            data_name,
            points_selector=filter_data))

    return (prev_count, new_count)


def stat_total(
        db: QdrantClient,
        name: str,
        *,
        filters: dict[MetaKey, list[str]] | None) -> int:
    query_filter = get_filter(filters, for_vec=False, skip_fields=None)
    data_name = get_db_name(name, is_vec=False)
    count_res = retry_err(
        lambda: db.count(data_name, count_filter=query_filter, exact=True))
    return count_res.count


def stat_embed(
        db: QdrantClient,
        name: str,
        *,
        field: MetaKey,
        filters: dict[MetaKey, list[str]] | None,
        ) -> dict[str, int]:
    query_filter = get_filter(filters, for_vec=False, skip_fields={field})
    data_name = get_db_name(name, is_vec=False)

    field_key = convert_meta_key_data(field, None)
    main_ids_data = full_scroll(
        db,
        data_name,
        scroll_filter=query_filter,
        with_payload=[field_key])

    def convert(val: str | list[str]) -> list[str]:
        if isinstance(val, list):
            return val
        return [val]

    def convert_for_date(val: str) -> str:
        if isinstance(val, datetime):
            dt = val
        else:
            dt = parse_time_str(val)
        return dt.date().isoformat()

    def convert_for_value(val: str) -> str:
        return val

    if field == "date":
        convert_for_stat = convert_for_date
    else:
        convert_for_stat = convert_for_value

    counts: collections.Counter[str] = collections.Counter(
        convert_for_stat(value)
        for data in main_ids_data
        if data.payload is not None
        for value in convert(data.payload.get(field_key, []))
        if value is not None)
    return dict(counts)


def fill_meta_data(payload: Payload) -> MetaObjectOpt:
    meta: MetaObjectOpt = {}
    for key, value in payload.items():
        meta_info = unconvert_meta_key_data(key)
        if meta_info is None:
            continue
        meta_key, meta_value = meta_info
        if meta_value is not None:
            inner: dict[str, float] = cast(dict, meta.get(meta_key))
            if inner is None:
                inner = {}
                meta[meta_key] = inner
            inner[meta_value] = value
        elif meta_key not in META_SCALAR:
            meta[meta_key] = value
    return meta


def get_filter(
        filters: dict[MetaKey, list[str]] | None,
        *,
        for_vec: bool,
        skip_fields: set[MetaKey] | None) -> Filter | None:
    if filters is None:
        return None

    def cmkd(key: MetaKey) -> InternalDataKey:
        return convert_meta_key_data(key, None)

    if for_vec:
        convert_meta_key = convert_meta_key_snippet
    else:
        convert_meta_key = cmkd

    conds: list[Condition] = []
    for key, values in filters.items():
        if skip_fields is not None and key in skip_fields:
            continue
        if not values:
            continue
        if key == "date":
            if len(values) != 2:
                raise ValueError(
                    f"date filter must be exactly two dates got {values}")
            ikey = convert_meta_key(key)
            dates = [parse_time_str(value) for value in values]
            conds.append(FieldCondition(
                key=ikey, range=DatetimeRange(gte=min(dates), lte=max(dates))))
            continue
        if key == "doc_type":
            # NOTE: utilizing base vec index for known doc_types
            # each doc_type can only be in one base
            bases: set[str] = set()
            for doc_type in values:
                fixed_base = DOC_TYPE_TO_BASE.get(doc_type)
                if fixed_base is None:
                    bases = set()
                    break
                bases.add(fixed_base)
            if bases:
                conds.append(FieldCondition(
                    key="base",
                    match=MatchAny(any=sorted(bases))))
                continue
        ikey = convert_meta_key(key)
        conds.append(FieldCondition(key=ikey, match=MatchAny(any=values)))
    if not conds:
        return None
    return Filter(must=conds)


def process_meta(
        meta_key: MetaKey,
        payload: Payload,
        defaults: dict[MetaKey, list[str] | str | int],
        ) -> list[str] | str | int:
    res = payload.get(convert_meta_key_data(meta_key, None))
    if res is None:
        res = defaults.get(meta_key)
        if res is None:
            raise KeyError(f"{meta_key=} not in {payload=}")
        return res
    if meta_key not in META_SCALAR:
        return res
    return sorted(
        res,
        key=lambda val: payload.get(convert_meta_key_data(meta_key, val), 0),
        reverse=True)


def get_meta_from_data_payload(
        payload: Payload,
        defaults: dict[MetaKey, list[str] | str | int],
        ) -> dict[MetaKey, list[str] | str | int]:
    return {
        meta_key: process_meta(meta_key, payload, defaults)
        for meta_key in META_KEYS
    }


def query_embed(
        db: QdrantClient,
        name: str,
        embed: list[float],
        *,
        offset: int | None,
        limit: int,
        hit_limit: int,
        score_threshold: float | None,
        filters: dict[MetaKey, list[str]] | None,
        ) -> list[ResultChunk]:
    # FIXME https://github.com/qdrant/qdrant/issues/3970 would be nice
    real_offset = 0 if offset is None else offset
    total_limit = real_offset + limit
    print(f"query {name} offset={real_offset} limit={total_limit}")
    vec_filter = get_filter(filters, for_vec=True, skip_fields=None)
    vec_name = get_db_name(name, is_vec=True)
    data_name = get_db_name(name, is_vec=False)
    hits = retry_err(
        lambda: db.search_groups(
            vec_name,
            query_vector=embed,
            group_by=REF_KEY,
            limit=total_limit,
            group_size=hit_limit,
            score_threshold=score_threshold,
            query_filter=vec_filter,
            with_lookup=WithLookup(collection=data_name, with_payload=True),
            timeout=300))

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
        base = data_payload["base"]
        doc_id = data_payload["doc_id"]
        url = data_payload["url"]
        title = data_payload.get("title")
        if title is None:
            title = url
        updated = data_payload["updated"]
        main_id = data_payload["main_id"]
        defaults: dict[MetaKey, list[str] | str | int] = {
            "date": updated,
        }
        meta = get_meta_from_data_payload(data_payload, defaults)
        return {
            "main_id": main_id,
            "score": score,
            "base": base,
            "doc_id": doc_id,
            "snippets": snippets,
            "url": url,
            "title": title,
            "updated": updated,
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
        filters: dict[MetaKey, list[str]] | None,
        order_by: MetaKey | tuple[MetaKey, str] | None,
        ) -> list[ResultChunk]:
    real_offset = 0 if offset is None else offset
    total_limit = real_offset + limit
    print(f"scroll {name} offset={real_offset} limit={total_limit}")
    data_name = get_db_name(name, is_vec=False)
    query_filter = get_filter(filters, for_vec=False, skip_fields=None)
    if order_by is None:
        order_by = "date"
    if isinstance(order_by, tuple):
        order_by_tup = order_by
    else:
        order_by_tup = cast(tuple, (order_by, None))
    order_key, order_variant = order_by_tup
    # FIXME emulate offset in order by
    hits, _ = retry_err(
        lambda: db.scroll(
            data_name,
            order_by=OrderBy(
                key=convert_meta_key_data(order_key, order_variant),
                direction=Direction.DESC),
            limit=total_limit,
            scroll_filter=query_filter,
            with_payload=True))

    def convert_hit(hit: Record) -> ResultChunk:
        data_payload = hit.payload
        assert data_payload is not None
        base = data_payload["base"]
        doc_id = data_payload["doc_id"]
        url = data_payload["url"]
        title = data_payload.get("title")
        if title is None:
            title = url
        updated = data_payload["updated"]
        main_id = data_payload["main_id"]
        defaults: dict[MetaKey, list[str] | str | int] = {
            "date": updated,
        }
        meta = get_meta_from_data_payload(data_payload, defaults)
        return {
            "main_id": main_id,
            "score": 1.0,
            "base": base,
            "doc_id": doc_id,
            "snippets": [],
            "url": url,
            "title": title,
            "updated": updated,
            "meta": meta,
        }

    return [
        convert_hit(hit)
        for hit in hits[real_offset:total_limit]
    ]
