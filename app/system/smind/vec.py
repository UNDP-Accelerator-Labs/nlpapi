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
"""Vector database operations. All vector database client calls should go
here."""
import collections
import hashlib
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import (
    cast,
    get_args,
    Literal,
    NotRequired,
    TypeAlias,
    TypedDict,
    TypeVar,
)

import numpy as np
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
    MatchExcept,
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
    ScoredPoint,
    VectorParams,
    WithLookup,
)

from app.misc.util import (
    DocStatus,
    get_time_str,
    parse_time_str,
    retry_err,
    retry_err_config,
)
from app.system.config import Config


T = TypeVar('T')


QDRANT_UUID = uuid.UUID("5c349547-396f-47e1-b0fb-22ed665bc112")
"""UUID namespace for uuids created for vector database items."""
REF_KEY: Literal["main_uuid"] = "main_uuid"
"""The name of the database key storing the item UUID."""


META_CAT = "_"
"""Meta field concatenation symbol."""
META_PREFIX = f"meta{META_CAT}"
"""Prefix for meta fields."""


DBName: TypeAlias = Literal["main", "test", "rave_ce"]
"""Denotes the external name of a vector database."""
DBS: tuple[DBName] = get_args(DBName)
"""All possible external names for vector databases."""


DBQName: TypeAlias = str
"""Internal vector database name distinguishing snippets and documents.
This is not the same as a regular internal vector database name which just
indicates the corpus."""
InternalDataKey: TypeAlias = str
"""Internal vector database meta key for document data."""
InternalSnippetKey: TypeAlias = str
"""Internal vector database meta key for snippets."""


HashTup: TypeAlias = tuple[str, int]
"""Document hash. Combination of hash and number of snippets."""


MetaObject = TypedDict('MetaObject', {
    "date": NotRequired[str | None],
    "status": DocStatus,
    "doc_type": str,
    "language": NotRequired[dict[str, float]],
    "iso3": NotRequired[dict[str, float]],
})
"""Meta data structure."""
MetaObjectOpt = TypedDict('MetaObjectOpt', {
    "date": NotRequired[str],
    "status": DocStatus,
    "doc_type": str,
    "language": dict[str, float],
    "iso3": dict[str, float],
}, total=False)
"""Partial meta data structure."""
MetaKey = Literal["date", "status", "doc_type", "language", "iso3"]
"""Valid meta data keys."""
META_KEYS: set[MetaKey] = set(get_args(MetaKey))
"""Valid meta data keys."""
META_SCALAR: set[Literal["language", "iso3"]] = {"language", "iso3"}
"""Scalar meta data keys."""
META_SNIPPET_INDEX: dict[MetaKey, PayloadSchemaType] = {
    "date": "datetime",
    "status": "keyword",
    "doc_type": "keyword",
    "language": "keyword",
    "iso3": "keyword",
}
"""Schema of meta data fields."""


KNOWN_DOC_TYPES: dict[str, set[str]] = {
    "actionplan": {"action plan"},
    "experiment": {"experiment"},
    "solution": {"solution"},
}
"""Mapping from bases to human readable document types."""
DOC_TYPE_TO_BASE: dict[str, str] = {
    doc_type: base
    for base, doc_types in KNOWN_DOC_TYPES.items()
    for doc_type in doc_types
}
"""Mapping from human readable document types to bases."""


StatEmbed = TypedDict('StatEmbed', {
    "doc_count": int,
    "fields": dict[MetaKey, dict[str, int]],
})
"""Vector database document counts. "doc_count" is the total number of
documents and "fields" maps field types to field values to their frequency."""


VecDBStat = TypedDict('VecDBStat', {
    "ext_name": str | None,
    "name": str,
    "db_name": str,
    "status": str,
    "count": int,
})
"""Information about vector databases. `ext_name` is the external name, `name`
is the internal name, and `db_name` is the internal distinguishin between
document data and snippet storage. `count` is the number of items stored in
the database."""


VecDBConfig = TypedDict('VecDBConfig', {
    "host": str,
    "port": int,
    "grpc": int,
    "token": str | None,
})
"""Vector database connection configuration."""


DistanceFn = Literal[
    "cos",
    "dot",
    "man",
    "euc",
]
"""Possible embedding distance measures."""


EmbedMain = TypedDict('EmbedMain', {
    "doc_id": int,
    "base": str,
    "url": str,
    "title": str,
    "meta": MetaObject,
})
"""Embedding payload for document data."""


EmbedChunk = TypedDict('EmbedChunk', {
    "chunk_id": int,
    "embed": list[float],
    "snippet": str,
})
"""Embedding payload for snippet data."""


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
"""A document result for a semantic search query."""
QueryEmbed = TypedDict('QueryEmbed', {
    "hits": list[ResultChunk],
    "status": Literal["ok", "error"],
})
"""Query results for a semantic search query."""

DocResult = TypedDict('DocResult', {
    "main_id": str,
    "score": float,
    "doc_id": int,
    "base": str,
    "url": str,
    "title": str,
    "updated": str,
    "embed": list[float],
    "meta": dict[MetaKey, list[str] | str | int],
})
"""A document result for a document lookup."""


FILE_PROTOCOL = "file://"
"""Protocol section for file vector database storage. Useful for testing out
vector database behavior locally."""


def convert_meta_key_data(
        key: MetaKey, variant: str | None) -> InternalDataKey:
    """
    Convert a meta data key and value into the internal representation of meta
    keys. Scalar meta data fields store the value as key instead of as value.

    Args:
        key (MetaKey): The meta data key.
        variant (str | None): If the meta data field is scalar the value can
            be provided to create the extended key.

    Returns:
        InternalDataKey: The internal key to be used in the document data
            database.
    """
    if key not in META_KEYS:
        raise ValueError(f"{key} is not a valid meta key")
    if key in META_SCALAR and variant is not None:
        return f"{META_PREFIX}{key}{META_CAT}{variant}"
    return f"{META_PREFIX}{key}"


def convert_meta_key_snippet(key: MetaKey) -> InternalSnippetKey:
    """
    Convert a meta data key into the internal representation of meta keys.

    Args:
        key (MetaKey): The meta data key.

    Returns:
        InternalSnippetKey: The internal key to be used in the snippet
            database.
    """
    if key not in META_KEYS:
        raise ValueError(f"{key} is not a valid meta key")
    return f"{META_PREFIX}{key}"


def unconvert_meta_key_data(
        key: InternalDataKey) -> tuple[MetaKey, str | None] | None:
    """
    Convert an internal meta data key used in the document data database into
    a regular meta key.

    Args:
        key (InternalDataKey): The internal key.

    Returns:
        tuple[MetaKey, str | None] | None: The meta key and the optional
            variant for if the meta key is scalar. If the key is not a meta
            key None is returned.
    """
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
    """
    Convert an internal meta data key used in the snippet database into a
    regular meta key.

    Args:
        key (InternalSnippetKey): The internal key.

    Returns:
        MetaKey | None: The meta key or None if the key is not a meta key.
    """
    res = key.removeprefix(META_PREFIX)
    if res == key:
        return None
    if res not in META_KEYS:
        return None
    return cast(MetaKey, res)


def ensure_valid_name(name: str) -> str:
    """
    Checks whether a database name is valid.

    Args:
        name (str): The database name.

    Raises:
        ValueError: If the name is not valid.

    Returns:
        str: The name.
    """
    if "-" in name or ":" in name:
        raise ValueError(f"invalid name {name}")
    return name


def get_vec_client(config: Config) -> QdrantClient | None:
    """
    Create a vector database client for the given configuration.

    Args:
        config (Config): The configuration.

    Returns:
        QdrantClient | None: The client or None if no vector database is
            specified in the config.
    """
    vec_db = config["vector"]
    if vec_db is None:
        return None
    host = vec_db["host"]
    if host.startswith(FILE_PROTOCOL):
        print(f"loading db file: {host.removeprefix(FILE_PROTOCOL)}")
        db = QdrantClient(
            path=host.removeprefix(FILE_PROTOCOL),
            timeout=600)
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
            api_key=token,
            timeout=600)
    return db


def vec_flushall(db: QdrantClient) -> None:
    """
    Deletes all vector databases.

    Args:
        db (QdrantClient): The vector database client.
    """
    for collection in retry_err(lambda: db.get_collections().collections):
        retry_err(
            lambda name: db.delete_collection(name, timeout=600),
            collection.name)


def get_vec_stats(
        db: QdrantClient, name: str, *, is_vec: bool) -> VecDBStat | None:
    """
    Get information about a vector database.

    Args:
        db (QdrantClient): The vector database client.
        name (str): The vector database name.
        is_vec (bool): Whether to inspect the snippet database (True) or the
            document data database (False),

    Returns:
        VecDBStat | None: The stats or None if the information is unavailable.
    """
    try:
        db_name = get_db_name(name, is_vec=is_vec)
        if not retry_err(lambda: db.collection_exists(db_name)):
            return None
        status = retry_err(
            lambda: db.get_collection(db_name))
        count = retry_err(lambda: db.count(db_name))
        return {
            "ext_name": None,
            "name": name,
            "db_name": db_name,
            "status": status.status,
            "count": count.count,
        }
    except (UnexpectedResponse, ResponseHandlingException):
        return None


def get_db_name(name: str, *, is_vec: bool) -> DBQName:
    """
    Get the internal database name distinguishing the document data and snippet
    database.

    Args:
        name (str): The database name.
        is_vec (bool): Whether to return the snippet database (True) or the
            document data database (False),

    Returns:
        DBQName: The name.
    """
    return f"{name}_vec" if is_vec else f"{name}_data"


def build_db_name(
        name: str,
        *,
        distance_fn: DistanceFn,
        embed_size: int,
        db: QdrantClient,
        force_clear: bool,
        force_index: bool) -> str:
    """
    Ensures the database with the given name exists.

    Args:
        name (str): The vector database name.
        distance_fn (DistanceFn): The distance function to be used.
        embed_size (int): The length of embeddings.
        db (QdrantClient): The vector database client.
        force_clear (bool): Whether to delete the database first.
        force_index (bool): Whether to force indexing the database.

    Returns:
        str: The internal database name.
    """
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
        hnsw_config = HnswConfigDiff(
            m=64,
            ef_construct=512,
            full_scan_threshold=10000,
            on_disk=True)
        quant_config = ScalarQuantization(
            scalar=ScalarQuantizationConfig(type=ScalarType.INT8))
        config = VectorParams(
            size=embed_size,
            distance=distance,
            on_disk=True,
            hnsw_config=hnsw_config,
            quantization_config=quant_config)
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
            hnsw_config=hnsw_config,
            quantization_config=quant_config,
            on_disk_payload=True,
            # replication_factor=3,
            # shard_number=6,
            shard_number=2,
            timeout=600)

        data_name = get_db_name(name, is_vec=False)
        db.recreate_collection(
            data_name,
            vectors_config=config,
            optimizers_config=optimizers,
            hnsw_config=hnsw_config,
            quantization_config=quant_config,
            on_disk_payload=True,
            # replication_factor=3,
            # shard_number=6,
            shard_number=2,
            timeout=600)

    need_create = False
    if not force_clear and not force_index:
        vec_name_read = get_db_name(name, is_vec=True)
        data_name_read = get_db_name(name, is_vec=False)
        if retry_err_config(
                lambda: db.collection_exists(vec_name_read),
                60,  # max_retry
                5.0):  # sleep
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
        db_name: DBQName,
        field_name: str,
        field_schema: PayloadSchemaType,
        *,
        db_schema: dict[str, PayloadIndexInfo],
        force_recreate: bool) -> int:
    """
    Creates an index for the given field name.

    Args:
        db (QdrantClient): The vector database client.
        db_name (DBQName): The internal database name distinguishing document
            data and snippets.
        field_name (str): The internal field name. This might be a field and
            value for scalar fields.
        field_schema (PayloadSchemaType): The index schema type.
        db_schema (dict[str, PayloadIndexInfo]): Existing index schemas.
        force_recreate (bool): Forces creation of a new index from scratch.

    Returns:
        int: 1 if the index was created and 0 if it existed already.
    """
    if force_recreate:
        retry_err(
            lambda key: db.delete_payload_index(db_name, key), field_name)
    else:
        schema = db_schema.get(field_name)
        if schema is not None and schema.data_type == field_schema:
            return 0
    db.create_payload_index(db_name, field_name, field_schema, wait=True)
    return 1


def recreate_index(
        db: QdrantClient, name: str, *, force_recreate: bool) -> int:
    """
    Creates all missing indexes.

    Args:
        db (QdrantClient): The vetor database client.
        name (str): The database name.
        force_recreate (bool): Forces recreation of all indexes. This is only
            recommended if the database is still small or empty. For big
            databases creating a new index will almost certainly time out.

    Returns:
        int: The number of new indices created.
    """
    count = 0
    # * vec keys *
    vec_name = get_db_name(name, is_vec=True)
    vec_schema = db.get_collection(vec_name).payload_schema

    count += create_index(
        db,
        vec_name,
        "base",
        "keyword",
        db_schema=vec_schema,
        force_recreate=force_recreate)

    # * data keys *
    data_name = get_db_name(name, is_vec=False)
    data_schema = db.get_collection(vec_name).payload_schema

    count += create_index(
        db,
        data_name,
        "main_id",
        "keyword",
        db_schema=data_schema,
        force_recreate=force_recreate)
    count += create_index(
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
        count += create_index(
            db,
            vec_name,
            snippet_meta_key,
            index_type,
            db_schema=vec_schema,
            force_recreate=force_recreate)
        data_meta_key = convert_meta_key_data(meta_key, None)
        count += create_index(
            db,
            data_name,
            data_meta_key,
            index_type,
            db_schema=vec_schema,
            force_recreate=force_recreate)
    return count


def build_scalar_index(
        db: QdrantClient,
        name: str,
        *,
        full_stats: dict[MetaKey, dict[str, int] | dict[str, float]] | None,
        ) -> int:
    """
    Builds the index of a scalar type. Scalar types have one field and thus
    one index for each variant (i.e., possible value).

    Args:
        db (QdrantClient): The vector database client.
        name (str): The database name.
        full_stats (dict[MetaKey, dict[str, int] | dict[str, float]] | None):
            Full (non-indexed nor cached) statistics about the meta fields.
            If None, the stats are computed from scratch. It is important to
            not use pre-indexed or cached value here as that will not reveal
            any new variants that might exist in the database but haven't been
            indexed yet.

    Returns:
        int: Number of newly created indices.
    """
    count = 0
    if full_stats is None:
        count += recreate_index(db, name, force_recreate=False)
    data_name = get_db_name(name, is_vec=False)
    data_schema = db.get_collection(data_name).payload_schema
    for meta_key in META_SCALAR:
        if full_stats is None:
            # NOTE: no caching!
            stats: dict[str, int] | dict[str, float] = stat_embed(
                db, name, field=meta_key, filters=None)
        else:
            stats = full_stats.get(meta_key, {})
        for variant in stats.keys():
            data_meta_key = convert_meta_key_data(meta_key, variant)
            count += create_index(
                db,
                data_name,
                data_meta_key,
                "float",
                db_schema=data_schema,
                force_recreate=False)
    return count


def full_scroll(
        db: QdrantClient,
        name: str,
        *,
        scroll_filter: Filter | None,
        with_vectors: bool,
        with_payload: bool | Sequence[str]) -> list[Record]:
    """
    Performs a full scroll through the vector database. This operation can take
    a while since it has to look at every row in the database (except for
    using filters leveraging indices) so it is advised to cache the results.

    Args:
        db (QdrantClient): The vector database client.
        name (str): The database name.
        scroll_filter (Filter | None): The filter or None for no filter.
        with_vectors (bool): Whether to return the rows with their embeddings.
        with_payload (bool | Sequence[str]): Whether to return the rows with
            their meta data.

    Returns:
        list[Record]: The results of the scan.
    """
    offset = None
    cur_limit = 10
    res: list[Record] = []
    while True:
        cur, next_offset = db.scroll(
            name,
            scroll_filter=scroll_filter,
            offset=offset,
            limit=cur_limit,
            with_vectors=with_vectors,
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
    """
    Computes the hash of chunk snippets.

    Args:
        chunks (list[EmbedChunk]): The snippets.

    Returns:
        HashTup: The hash and the number of chunks.
    """
    blake = hashlib.blake2b(digest_size=32)
    blake.update(f"{len(chunks)}:".encode("utf-8"))
    for chunk in chunks:
        snippet = chunk["snippet"]
        blake.update(f"{len(snippet)}:".encode("utf-8"))
        blake.update(snippet.encode("utf-8"))
    return (blake.hexdigest(), len(chunks))


def compute_doc_embedding(
        embed_size: int, chunks: list[EmbedChunk]) -> list[float]:
    """
    Compute the document embedding by averaging the snippet embeddings.

    Args:
        embed_size (int): The dimensionality of the embeddings.
        chunks (list[EmbedChunk]): The actual chunk embeddings.

    Returns:
        list[float]: The document embedding.
    """
    # we can use the average. see here:
    # https://datascience.stackexchange.com/a/110506
    if not chunks:
        return list(np.zeros((embed_size,)))
    return list(np.array([chunk["embed"] for chunk in chunks]).mean(axis=0))


def get_main_id(data: EmbedMain) -> str:
    """
    Compute the main id from the meta data and row info.

    Args:
        data (EmbedMain): The meta data and row info.

    Returns:
        str: The main id.
    """
    return f"{data['base']}:{data['doc_id']}"


def get_main_uuid(data: EmbedMain) -> str:
    """
    Create a UUID that uniquely identifies a document.

    Args:
        data (EmbedMain): The meta data and row info.

    Returns:
        str: The UUID.
    """
    return f"{uuid.uuid5(QDRANT_UUID, get_main_id(data))}"


def to_data_payload(
        data: EmbedMain,
        chunk_hash: HashTup,
        ) -> dict[InternalDataKey, list[str] | str | float | int]:
    """
    Converts meta data and row information into a vector database document
    data payload.

    Args:
        data (EmbedMain): The meta data and row info.
        chunk_hash (HashTup): The hashes and quantity of the chunk snippets.

    Returns:
        dict[InternalDataKey, list[str] | str | float | int]: The payload.
    """
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
    """
    Converts meta data and row information into a vector database snippet
    payload.

    Args:
        data (EmbedMain): The meta data and row info.

    Returns:
        dict[InternalSnippetKey, list[str] | str | int]: The payload.
    """
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
        embed_size: int,
        chunks: list[EmbedChunk]) -> tuple[int, int]:
    """
    Adds an embedding to the vector database.

    Args:
        db (QdrantClient): The vector database client.
        name (str): The database name.
        data (EmbedMain): The meta data and row info.
        embed_size (int): The dimensionality of the embeddings.
        chunks (list[EmbedChunk]): The snippet chunks.

    Returns:
        tuple[int, int]: The previous snippet count and the new snippet count.
    """
    chunk_hash = compute_chunk_hash(chunks)
    doc_embed = compute_doc_embedding(embed_size, chunks)
    cur_hash, new_count = chunk_hash
    is_remove = new_count == 0
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
        with_vectors=False,
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
    if not is_remove:
        required_doc_types = KNOWN_DOC_TYPES.get(base)
        if (
                required_doc_types is not None
                and doc_type not in required_doc_types):
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

    if not is_remove:
        new_index_count = build_scalar_index(
            db,
            name,
            full_stats={
                meta_key: meta_obj.get(meta_key, {})
                for meta_key in META_SCALAR
            })
        if new_index_count > 0:
            print(f"created {new_index_count=}")
        retry_err(lambda: db.upsert(
            data_name,
            points=[
                PointStruct(
                    id=main_uuid,
                    vector=doc_embed,
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
    """
    Counts the total number of documents for a given filter.

    Args:
        db (QdrantClient): The vector database client.
        name (str): The database name.
        filters (dict[MetaKey, list[str]] | None): The filter or None for no
            filter.

    Returns:
        int: The number of documents.
    """
    query_filter = get_filter(
        filters, for_vec=False, skip_fields=None, exclude_main_id=None)
    data_name = get_db_name(name, is_vec=False)
    if query_filter is None:
        res = db.get_collection(data_name).points_count
        if res is not None:
            return res
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
    """
    Computes the number of documents of each variant of a given meta field
    after applying a filter.

    Args:
        db (QdrantClient): The vector database client.
        name (str): The vector database name.
        field (MetaKey): The meta field to inspect.
        filters (dict[MetaKey, list[str]] | None): The filters.

    Returns:
        dict[str, int]: The variants of the meta field and their document
            counts.
    """
    query_filter = get_filter(
        filters, for_vec=False, skip_fields={field}, exclude_main_id=None)
    data_name = get_db_name(name, is_vec=False)

    field_key = convert_meta_key_data(field, None)
    main_ids_data = full_scroll(
        db,
        data_name,
        scroll_filter=query_filter,
        with_vectors=False,
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
    """
    Create a meta data object from a data payload.

    Args:
        payload (Payload): The payload.

    Returns:
        MetaObjectOpt: The meta data object.
    """
    meta: MetaObjectOpt = {}
    for key, value in payload.items():
        meta_info = unconvert_meta_key_data(key)
        if meta_info is None:
            continue
        meta_key, meta_value = meta_info
        if meta_value is not None:
            inner: dict[str, float] | None = cast(dict, meta.get(meta_key))
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
        skip_fields: set[MetaKey] | None,
        exclude_main_id: str | None) -> Filter | None:
    """
    Convert a dictionary filter to the qdrant filter format.

    Args:
        filters (dict[MetaKey, list[str]] | None): The filter.
        for_vec (bool): Whether the filter is for snippets (True) or document
            data (False).
        skip_fields (set[MetaKey] | None): Meta keys to skip if set.
        exclude_main_id (str | None): If set, filters out the given main id.

    Returns:
        Filter | None: The filter or None if no filter was specified.
    """
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
        ikey = convert_meta_key(key)
        conds.append(FieldCondition(key=ikey, match=MatchAny(any=values)))
    if exclude_main_id is not None:
        conds.append(
            FieldCondition(
                key="main_id",
                match=MatchExcept(**{
                    "except": [exclude_main_id],
                })))
    if not conds:
        return None
    return Filter(must=conds)


def process_meta(
        meta_key: MetaKey,
        payload: Payload,
        defaults: dict[MetaKey, list[str] | str | int],
        ) -> list[str] | str | int:
    """
    Interprets the given meta field in the payload.

    Args:
        meta_key (MetaKey): The meta key.
        payload (Payload): The payload.
        defaults (dict[MetaKey, list[str] | str | int]): Meta field default
            values.

    Returns:
        list[str] | str | int: The meta field value.
    """
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
    """
    Gets all meta fields from the payload.

    Args:
        payload (Payload): The payload.
        defaults (dict[MetaKey, list[str] | str | int]): Meta field default
            values.

    Returns:
        dict[MetaKey, list[str] | str | int]: The meta field values.
    """
    return {
        meta_key: process_meta(meta_key, payload, defaults)
        for meta_key in META_KEYS
    }


def get_doc(db: QdrantClient, name: str, main_id: str) -> DocResult | None:
    """
    Get the full information of the specified document.

    Args:
        db (QdrantClient): The vector database client.
        name (str): The vector database name.
        main_id (str): The main id.

    Returns:
        DocResult | None: The document information or None if the main id
            doesn't exist in the database.
    """
    data_name = get_db_name(name, is_vec=False)
    filter_data = Filter(
        must=[
            FieldCondition(
                key="main_id",
                match=MatchValue(value=main_id)),
        ])
    res = full_scroll(
        db,
        data_name,
        scroll_filter=filter_data,
        with_vectors=True,
        with_payload=True)
    if len(res) <= 0:
        return None
    payload = res[0].payload
    assert payload is not None
    embed = res[0].vector
    assert embed is not None
    base = payload["base"]
    doc_id = payload["doc_id"]
    url = payload["url"]
    title = payload.get("title")
    if title is None:
        title = url
    updated = payload["updated"]
    main_id = payload["main_id"]
    defaults: dict[MetaKey, list[str] | str | int] = {
        "date": updated,
    }
    meta = get_meta_from_data_payload(payload, defaults)
    return {
        "main_id": main_id,
        "score": 1.0,
        "base": base,
        "doc_id": doc_id,
        "embed": list(embed),  # type: ignore
        "url": url,
        "title": title,
        "updated": updated,
        "meta": meta,
    }


def to_result(doc_result: DocResult) -> ResultChunk:
    """
    Convert a document result into a result chunk.

    Args:
        doc_result (DocResult): The document result.

    Returns:
        ResultChunk: The result chunk.
    """
    return {
        "main_id": doc_result["main_id"],
        "base": doc_result["base"],
        "doc_id": doc_result["doc_id"],
        "snippets": [],
        "meta": doc_result["meta"],
        "score": doc_result["score"],
        "title": doc_result["title"],
        "updated": doc_result["updated"],
        "url": doc_result["url"],
    }


def search_docs(
        db: QdrantClient,
        name: str,
        embed: list[float],
        *,
        offset: int | None,
        limit: int,
        score_threshold: float | None,
        filters: dict[MetaKey, list[str]] | None,
        exclude_main_id: str | None,
        with_vectors: bool,
        ) -> list[DocResult]:
    """
    Find the closest documents to the given embedding. This uses the document
    embedding (average of all snippet embeddings) instead of snippets.

    Args:
        db (QdrantClient): The vector database client.
        name (str): The vector database name.
        embed (list[float]): The embedding to search for.
        offset (int | None): The offset. 0 if None.
        limit (int): The number of documents to return.
        score_threshold (float | None): If set limits the results by filtering
            by score.
        filters (dict[MetaKey, list[str]] | None): The filters.
        exclude_main_id (str | None): If set does not return the given main id.
        with_vectors (bool): Whether to include in the response.

    Returns:
        list[DocResult]: The document results.
    """
    data_name = get_db_name(name, is_vec=False)
    real_offset = 0 if offset is None else offset
    query_filter = get_filter(
        filters,
        for_vec=False,
        skip_fields=None,
        exclude_main_id=exclude_main_id)
    docs = retry_err(
        lambda: db.search(
            data_name,
            query_vector=embed,
            offset=real_offset,
            limit=limit,
            query_filter=query_filter,
            score_threshold=score_threshold,
            with_vectors=with_vectors,
            with_payload=True,
            timeout=600))

    def convert_doc(doc: ScoredPoint) -> DocResult:
        payload = doc.payload
        assert payload is not None
        embed = doc.vector
        base = payload["base"]
        doc_id = payload["doc_id"]
        url = payload["url"]
        title = payload.get("title")
        if title is None:
            title = url
        updated = payload["updated"]
        main_id = payload["main_id"]
        defaults: dict[MetaKey, list[str] | str | int] = {
            "date": updated,
        }
        meta = get_meta_from_data_payload(payload, defaults)
        return {
            "main_id": main_id,
            "score": doc.score,
            "base": base,
            "doc_id": doc_id,
            "embed": list(embed) if embed else [],  # type: ignore
            "url": url,
            "title": title,
            "updated": updated,
            "meta": meta,
        }

    return [convert_doc(doc) for doc in docs]


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
    """
    Find the closest documents to the given embedding using the snippet
    embeddings.

    Args:
        db (QdrantClient): The vector database client.
        name (str): The vector database name.
        embed (list[float]): The embedding to search for.
        offset (int | None): The offset. 0 if None.
        limit (int): The number of documents to return.
        hit_limit (int): The number of snippets to return for each document
            hit.
        score_threshold (float | None): If set limits the results by filtering
            by score.
        filters (dict[MetaKey, list[str]] | None): The filters.

    Returns:
        list[ResultChunk]: The result chunks.
    """
    # FIXME https://github.com/qdrant/qdrant/issues/3970 would be nice
    real_offset = 0 if offset is None else offset
    total_limit = real_offset + limit
    print(f"query {name} offset={real_offset} limit={total_limit}")
    vec_filter = get_filter(
        filters, for_vec=True, skip_fields=None, exclude_main_id=None)
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
            timeout=600))

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
    """
    Return documents in the database.

    Args:
        db (QdrantClient): The vector database client.
        name (str): The vector database name.
        offset (int | None): The offset. 0 if None.
        limit (int): The number of documents to return.
        filters (dict[MetaKey, list[str]] | None): The filters.
        order_by (MetaKey | tuple[MetaKey, str] | None): Meta key or keys to
            order the results by.

    Returns:
        list[ResultChunk]: The result chunks.
    """
    real_offset = 0 if offset is None else offset
    total_limit = real_offset + limit
    print(f"scroll {name} offset={real_offset} limit={total_limit}")
    data_name = get_db_name(name, is_vec=False)
    query_filter = get_filter(
        filters, for_vec=False, skip_fields=None, exclude_main_id=None)
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
