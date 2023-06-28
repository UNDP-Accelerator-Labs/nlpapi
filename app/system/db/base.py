import numpy as np
import sqlalchemy as sa
from psycopg2.extensions import AsIs, register_adapter
from sqlalchemy.orm import registry
from sqlalchemy.orm.decl_api import DeclarativeMeta

from app.misc.util import file_hash_size


SOURCE_NAME_MAX_LEN = 40
CORPUS_NAME_MAX_LEN = 40
MODELS_NAME_MAX_LEN = 40
MODELS_BASE_MAX_LEN = 40
REFERENCE_MAX_LEN = 40
COUNTRY_MAX_LEN = 5


def adapt_numpy_float64(numpy_float64: np.float64) -> AsIs:
    return AsIs(numpy_float64)


def adapt_numpy_int64(numpy_int64: np.int64) -> AsIs:
    return AsIs(numpy_int64)


register_adapter(np.float64, adapt_numpy_float64)
register_adapter(np.int64, adapt_numpy_int64)


mapper_registry = registry()


class Base(
        metaclass=DeclarativeMeta):  # pylint: disable=too-few-public-methods
    __abstract__ = True
    __table__: sa.Table

    registry = mapper_registry
    metadata = mapper_registry.metadata

    __init__ = mapper_registry.constructor


LOCATION_CACHE_ID_SEQ: sa.Sequence = sa.Sequence(
    "location_cache_id_seq", start=1, increment=1)


class LocationCache(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "location_cache"

    query = sa.Column(
        sa.Text(),
        primary_key=True,
        nullable=False,
        unique=True)
    id = sa.Column(
        sa.Integer,
        LOCATION_CACHE_ID_SEQ,
        nullable=False,
        unique=True,
        server_default=LOCATION_CACHE_ID_SEQ.next_value())
    access_last = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now())
    access_count = sa.Column(
        sa.Integer,
        nullable=False,
        server_default=sa.text("1"))
    no_cache = sa.Column(sa.Boolean, nullable=False)


class LocationEntries(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "location_entries"

    location_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            LocationCache.id,
            onupdate="CASCADE",
            ondelete="CASCADE"),
        nullable=False,
        primary_key=True)
    pos = sa.Column(sa.Integer, nullable=False, primary_key=True)
    lat: sa.Column[float] = sa.Column(  # type: ignore
        sa.Double, nullable=False)
    lng: sa.Column[float] = sa.Column(  # type: ignore
        sa.Double, nullable=False)
    formatted = sa.Column(sa.Text(), nullable=False)
    country = sa.Column(sa.String(COUNTRY_MAX_LEN), nullable=False)
    confidence: sa.Column[float] = sa.Column(  # type: ignore
        sa.Double, nullable=False)


class LocationUsers(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "location_users"

    userid: sa.Column[sa.Uuid] = sa.Column(  # type: ignore
        sa.Uuid, nullable=False, unique=True, primary_key=True)
    cache_miss = sa.Column(sa.Integer, nullable=False, default=0)
    cache_hit = sa.Column(sa.Integer, nullable=False, default=0)
    invalid = sa.Column(sa.Integer, nullable=False, default=0)
    ratelimit = sa.Column(sa.Integer, nullable=False, default=0)
    location_count = sa.Column(sa.Integer, nullable=False, default=0)
    location_length = sa.Column(sa.Integer, nullable=False, default=0)
    language_count = sa.Column(sa.Integer, nullable=False, default=0)
    language_length = sa.Column(sa.Integer, nullable=False, default=0)


class ModelsTable(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "models"

    id = sa.Column(
        sa.Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
        unique=True)
    name = sa.Column(
        sa.String(MODELS_NAME_MAX_LEN),
        primary_key=True,
        nullable=False,
        unique=True)
    model_hash = sa.Column(
        sa.String(file_hash_size()),
        nullable=False,
        unique=True)
    base = sa.Column(sa.String(MODELS_BASE_MAX_LEN))

    idx_model_hash = sa.Index("model_hash")


class SourceTable(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "source"

    id = sa.Column(
        sa.Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
        unique=True)
    name = sa.Column(
        sa.String(SOURCE_NAME_MAX_LEN),
        primary_key=True,
        nullable=False,
        unique=True)


class CorpusTable(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "corpus"

    id = sa.Column(
        sa.Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
        unique=True)
    name = sa.Column(
        sa.String(CORPUS_NAME_MAX_LEN),
        primary_key=True,
        nullable=False,
        unique=True)
    model_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            ModelsTable.id, onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False)
    version = sa.Column(
        sa.Integer,
        nullable=False)
    active = sa.Column(
        sa.Boolean,
        nullable=False)


class CorpusSourcesTable(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "corpus_sources"

    corpus_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            CorpusTable.id, onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True,
        nullable=False)
    source_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            SourceTable.id, onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True,
        nullable=False)


class DocsTable(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "docs"

    id = sa.Column(
        sa.Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
        unique=True)
    source_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            SourceTable.id, onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False)
    searchable = sa.Column(sa.Text, nullable=False)
    reference = sa.Column(sa.String(REFERENCE_MAX_LEN), nullable=False)


EMBED_ORDER_SEQ: sa.Sequence = sa.Sequence(
    "embed_order_seq", start=1, increment=1)


class EmbedTable(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "embed"

    model_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            ModelsTable.id,
            onupdate="CASCADE",
            ondelete="CASCADE"),
        primary_key=True)
    doc_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            DocsTable.id, onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True)
    embed_order = sa.Column(
        sa.Integer,
        EMBED_ORDER_SEQ,
        nullable=False,
        unique=True,
        server_default=EMBED_ORDER_SEQ.next_value())
    embedding = sa.Column(
        sa.LargeBinary,
        nullable=False)

    idx_embed_order = sa.Index("model_id", "embed_order")


class FeedbackTable(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "feedback"

    model_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            ModelsTable.id,
            onupdate="CASCADE",
            ondelete="CASCADE"),
        primary_key=True)
    doc_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            DocsTable.id, onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True)
    prompt = sa.Column(sa.Text, nullable=False, primary_key=True)
    approve = sa.Column(sa.Integer, nullable=False, default=0)
    dislike = sa.Column(sa.Integer, nullable=False, default=0)
    neutral = sa.Column(sa.Integer, nullable=False, default=0)
