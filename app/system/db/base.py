import numpy as np
import sqlalchemy as sa
from psycopg2.extensions import AsIs, register_adapter
from sqlalchemy.orm import registry
from sqlalchemy.orm.decl_api import DeclarativeMeta


COUNTRY_MAX_LEN = 5
DATE_STRING_LEN = 10
VEC_DB_NAME_LEN = 40


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
        server_default=sa.func.now())  # pylint: disable=not-callable
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
    lat: sa.Column[float] = sa.Column(
        sa.Double, nullable=False)  # type: ignore
    lng: sa.Column[float] = sa.Column(
        sa.Double, nullable=False)  # type: ignore
    formatted = sa.Column(sa.Text(), nullable=False)
    country = sa.Column(sa.String(COUNTRY_MAX_LEN), nullable=False)
    confidence: sa.Column[float] = sa.Column(
        sa.Double, nullable=False)  # type: ignore


class LocationUsers(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "location_users"

    userid: sa.Column[sa.Uuid] = sa.Column(
        sa.Uuid, nullable=False, unique=True, primary_key=True)  # type: ignore
    cache_miss = sa.Column(sa.Integer, nullable=False, default=0)
    cache_hit = sa.Column(sa.Integer, nullable=False, default=0)
    invalid = sa.Column(sa.Integer, nullable=False, default=0)
    ratelimit = sa.Column(sa.Integer, nullable=False, default=0)
    location_count = sa.Column(sa.Integer, nullable=False, default=0)
    location_length = sa.Column(sa.Integer, nullable=False, default=0)
    language_count = sa.Column(sa.Integer, nullable=False, default=0)
    language_length = sa.Column(sa.Integer, nullable=False, default=0)


class QueryLog(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "query_log"

    vecdb = sa.Column(
        sa.String(VEC_DB_NAME_LEN),
        primary_key=True,
        nullable=False)
    query = sa.Column(
        sa.Text(),
        primary_key=True,
        nullable=False)
    filters = sa.Column(
        sa.Text(),
        primary_key=True,
        nullable=False)
    access_date = sa.Column(
        sa.String(DATE_STRING_LEN),
        primary_key=True,
        nullable=False)
    access_count = sa.Column(
        sa.Integer,
        nullable=False,
        server_default=sa.text("1"))
