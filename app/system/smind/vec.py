import collections
import re
import time
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any, cast, Literal, TypeAlias, TypedDict, TypeVar

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

from app.misc.util import get_time_str, parse_time_str
from app.system.config import Config


T = TypeVar('T')


QDRANT_UUID = uuid.UUID("5c349547-396f-47e1-b0fb-22ed665bc112")
REF_KEY: Literal["main_uuid"] = "main_uuid"
DUMMY_VEC: list[float] = [1.0]


KEY_REGEX = re.compile(r"[a-z_0-9]+")
META_PREFIX = "meta_"
FORBIDDEN_META = ["base", "main_id"]

ExternalKey: TypeAlias = str
InternalKey: TypeAlias = str

FIELDS_PREFIX = "fields"
VEC_SEARCHABLE: list[ExternalKey] = ["base", "status"]


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
    "title": str,
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
    "title": str,
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


def maybe_convert_meta_key(key: ExternalKey) -> InternalKey:
    if key in FORBIDDEN_META:
        return key
    return convert_meta_key(key)


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


def get_db_name(name: str, *, is_vec: bool) -> str:
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
            vec_name,
            vectors_config=config,
            optimizers_config=optimizers,
            on_disk_payload=True,
            timeout=600)

        data_name = get_db_name(name, is_vec=False)
        db.recreate_collection(
            data_name,
            vectors_config=VectorParams(size=1, distance=distance),
            on_disk_payload=True,
            timeout=600)

    def recreate_index() -> None:
        vec_name = get_db_name(name, is_vec=True)

        for key_name in VEC_SEARCHABLE:
            vec_key = maybe_convert_meta_key(key_name)
            retry_err(
                lambda key: db.delete_payload_index(vec_name, key), vec_key)
            db.create_payload_index(vec_name, vec_key, "keyword", wait=False)

        data_name = get_db_name(name, is_vec=False)

        retry_err(lambda: db.delete_payload_index(data_name, "main_id"))
        db.create_payload_index(data_name, "main_id", "keyword", wait=False)

        retry_err(lambda: db.delete_payload_index(data_name, "base"))
        db.create_payload_index(data_name, "base", "keyword", wait=False)

        date_key = convert_meta_key("date")
        retry_err(lambda: db.delete_payload_index(data_name, date_key))
        db.create_payload_index(data_name, date_key, "datetime", wait=False)

        status_key = convert_meta_key("status")
        retry_err(lambda: db.delete_payload_index(data_name, status_key))
        db.create_payload_index(data_name, status_key, "keyword", wait=False)

        language_key = convert_meta_key("language")
        retry_err(lambda: db.delete_payload_index(data_name, language_key))
        db.create_payload_index(data_name, language_key, "keyword", wait=False)

        iso3_key = convert_meta_key("iso3")
        retry_err(lambda: db.delete_payload_index(data_name, iso3_key))
        db.create_payload_index(data_name, iso3_key, "keyword", wait=False)

        doc_type_key = convert_meta_key("doc_type")
        retry_err(lambda: db.delete_payload_index(data_name, doc_type_key))
        db.create_payload_index(data_name, doc_type_key, "keyword", wait=False)

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
        recreate_index()
    return name


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
    base = data["base"]
    main_id = f"{base}:{data['doc_id']}"
    main_uuid = f"{uuid.uuid5(QDRANT_UUID, main_id)}"

    meta_obj = data["meta"]
    data_name = get_db_name(name, is_vec=False)
    filter_data = Filter(
        must=[
            FieldCondition(key="main_id", match=MatchValue(value=main_id)),
        ])
    prev_data = full_scroll(
        db, data_name, scroll_filter=filter_data, with_payload=True)
    meta_keys: set[ExternalKey] = set(meta_obj.keys())
    prev_meta: dict[ExternalKey, list[str] | str] = {}
    if len(prev_data) > 0:
        prev_payload = prev_data[0].payload
        assert prev_payload is not None
        prev_meta = fill_meta(prev_payload)
        meta_keys.update(prev_meta.keys())

    if "date" not in prev_meta and "date" not in meta_obj:
        meta_obj["date"] = get_time_str()
        meta_keys.add("date")

    main_payload: dict[InternalKey, list[str] | str | int] = {
        "main_id": main_id,
        "doc_id": data["doc_id"],
        "base": base,
        "url": data["url"],
        "title": data["title"],
    }
    for key, value in meta_obj.items():
        meta_key = convert_meta_key(key)
        main_payload[meta_key] = value

    db.upsert(
        data_name,
        points=[
            PointStruct(
                id=main_uuid,
                vector=DUMMY_VEC,
                payload=main_payload),
        ],
        wait=False)
    if update_meta_only:
        return (0, 0)
    vec_name = get_db_name(name, is_vec=True)
    filter_docs = Filter(
        must=[
            FieldCondition(key=REF_KEY, match=MatchValue(value=main_uuid)),
        ])
    count_res = db.count(vec_name, count_filter=filter_docs, exact=True)
    prev_count = count_res.count
    if prev_count > new_count or new_count == 0:
        db.delete(vec_name, points_selector=FilterSelector(filter=filter_docs))
        if new_count == 0:
            db.delete(
                data_name, points_selector=FilterSelector(filter=filter_docs))

    if not chunks:
        return (prev_count, new_count)

    vec_searchable: list[InternalKey] = [
        maybe_convert_meta_key(key_name)
        for key_name in VEC_SEARCHABLE
    ]
    vec_payload_template: dict[InternalKey, list[str] | str | int] = {
        vec_name: main_payload[vec_name]
        for vec_name in vec_searchable
        if vec_name in main_payload
    }

    def convert_chunk(chunk: EmbedChunk) -> PointStruct:
        point_id = f"{main_id}:{chunk['chunk_id']}"
        point_uuid = f"{uuid.uuid5(QDRANT_UUID, point_id)}"
        point_payload: dict[InternalKey, list[str] | str | int] = {
            REF_KEY: main_uuid,
            "vector_id": point_id,
            "snippet": chunk["snippet"],
            **vec_payload_template,
        }
        print(f"insert {point_id} ({len(chunk['embed'])})")
        return PointStruct(
            id=point_uuid,
            vector=chunk["embed"],
            payload=point_payload)

    db.upsert(
        vec_name,
        points=[convert_chunk(chunk) for chunk in chunks],
        wait=False)
    return (prev_count, new_count)


def stat_total(
        db: QdrantClient,
        name: str,
        *,
        filters: dict[ExternalKey, list[str]] | None) -> int:
    query_filter = get_filter(filters, for_vec=False, skip_fields=None)
    data_name = get_db_name(name, is_vec=False)
    count_res = db.count(data_name, count_filter=query_filter, exact=True)
    return count_res.count


def stat_embed(
        db: QdrantClient,
        name: str,
        *,
        field: ExternalKey,
        filters: dict[ExternalKey, list[str]] | None,
        ) -> dict[str, int]:
    query_filter = get_filter(filters, for_vec=False, skip_fields={field})
    data_name = get_db_name(name, is_vec=False)

    field_key = convert_meta_key(field)
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
            dt = parse_time_str(f"{val}")
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


def fill_meta(payload: Payload) -> dict[ExternalKey, list[str] | str]:
    meta = {}
    for key, value in payload.items():
        meta_key = unconvert_meta_key(key)
        if meta_key is None:
            continue
        meta[meta_key] = value
    return meta


def get_filter(
        filters: dict[ExternalKey, list[str]] | None,
        *,
        for_vec: bool,
        skip_fields: set[ExternalKey] | None) -> Filter | None:
    if filters is None:
        return None
    conds: list[Condition] = []
    for key, values in filters.items():
        if skip_fields is not None and key in skip_fields:
            continue
        if not values:
            continue
        if for_vec and key not in VEC_SEARCHABLE:
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
        key = maybe_convert_meta_key(key)
        conds.append(FieldCondition(key=key, match=MatchAny(any=values)))
    if not conds:
        return None
    return Filter(must=conds)


def create_filter_fn(
        filters: dict[ExternalKey, list[str]] | None,
        ) -> Callable[[ResultChunk], bool]:
    if filters is None:
        return lambda _: True
    filters_conv: dict[ExternalKey, set[str]] = {
        key: set(values)
        for key, values in filters.items()
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
        filters: dict[ExternalKey, list[str]] | None,
        snippet_post_processing: Callable[[list[str]], list[str]],
        ) -> list[ResultChunk]:
    real_offset = 0 if offset is None else offset
    total_limit = real_offset + limit
    filter_fn = create_filter_fn(filters)
    vec_filter = get_filter(filters, for_vec=True, skip_fields=None)
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
            vec_filter=vec_filter,
            snippet_post_processing=snippet_post_processing)
        if len(candidates) < cur_limit:
            reached_end = True
        for cand in candidates:
            if not filter_fn(cand):
                continue
            cur_res.append(cand)
        cur_offset += cur_limit
        cur_limit = int(max(1, min(100, cur_limit * 1.2)))
        # cur_limit = int(max(1, min(100, cur_limit * 2)))
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
        vec_filter: Filter | None,
        snippet_post_processing: Callable[[list[str]], list[str]],
        ) -> list[ResultChunk]:
    real_offset = 0 if offset is None else offset
    total_limit = real_offset + limit
    print(f"query {name} offset={real_offset} limit={total_limit}")
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
        snippets = snippet_post_processing(snippets)
        assert score is not None
        lookup = group.lookup
        assert lookup is not None
        data_payload = lookup.payload
        assert data_payload is not None
        meta = fill_meta(data_payload)
        base = data_payload["base"]
        doc_id = data_payload["doc_id"]
        url = data_payload["url"]
        title = data_payload.get("title", url)
        main_id = data_payload["main_id"]
        return {
            "main_id": main_id,
            "score": score,
            "base": base,
            "doc_id": doc_id,
            "snippets": snippets,
            "url": url,
            "title": title,
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
    query_filter = get_filter(filters, for_vec=False, skip_fields=None)
    hits, _ = retry_err(
        lambda: db.scroll(
            data_name,
            order_by=OrderBy(
                key=convert_meta_key("date"),
                direction=Direction.DESC),
            limit=total_limit,
            scroll_filter=query_filter,
            with_payload=True))

    def convert_hit(hit: Record) -> ResultChunk:
        data_payload = hit.payload
        assert data_payload is not None
        meta = fill_meta(data_payload)
        base = data_payload["base"]
        doc_id = data_payload["doc_id"]
        url = data_payload["url"]
        title = data_payload.get("title", url)
        main_id = data_payload["main_id"]
        return {
            "main_id": main_id,
            "score": 1.0,
            "base": base,
            "doc_id": doc_id,
            "snippets": [],
            "url": url,
            "title": title,
            "meta": meta,
        }

    return [
        convert_hit(hit)
        for hit in hits[real_offset:total_limit]
    ]
