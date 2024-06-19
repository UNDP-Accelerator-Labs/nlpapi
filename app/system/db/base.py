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
import numpy as np
import sqlalchemy as sa
from psycopg2.extensions import AsIs, register_adapter
from sqlalchemy.orm import registry
from sqlalchemy.orm.decl_api import DeclarativeMeta


COUNTRY_MAX_LEN = 5
DATE_STRING_LEN = 10
VEC_DB_NAME_LEN = 40
MAIN_ID_LEN = 40


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


class DeepDiveCollection(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "deep_dive_collection"

    id = sa.Column(
        sa.Integer, unique=True, primary_key=True, autoincrement=True)
    user: sa.Column[sa.Uuid] = sa.Column(
        sa.Uuid, nullable=False, primary_key=True)  # type: ignore
    name = sa.Column(sa.Text(), nullable=False, primary_key=True)
    verify_key = sa.Column(sa.Text(), nullable=False)
    deep_dive_key = sa.Column(sa.Text(), nullable=False)


DEEP_DIVE_ELEMENT_ID_SEQ: sa.Sequence = sa.Sequence(
    "deep_dive_element_id_seq", start=1, increment=1)


class DeepDiveElement(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "deep_dive_element"

    main_id = sa.Column(sa.String(MAIN_ID_LEN), primary_key=True)
    deep_dive_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            DeepDiveCollection.id,
            onupdate="CASCADE",
            ondelete="CASCADE"),
        nullable=False,
        primary_key=True)
    id = sa.Column(
        sa.Integer,
        DEEP_DIVE_ELEMENT_ID_SEQ,
        nullable=False,
        unique=True,
        server_default=DEEP_DIVE_ELEMENT_ID_SEQ.next_value())
    url = sa.Column(sa.Text(), nullable=True)
    title = sa.Column(sa.Text(), nullable=True)
    verify_reason = sa.Column(sa.Text(), nullable=True)
    is_valid = sa.Column(sa.Boolean, nullable=True)
    deep_dive_result = sa.Column(sa.JSON, nullable=True)
    error = sa.Column(sa.Text(), nullable=True)


# platform tables

class SessionTable(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "session"

    sid = sa.Column(sa.Text(), nullable=False, primary_key=True)
    sess = sa.Column(sa.JSON, nullable=False)
    expire = sa.Column(sa.DateTime(timezone=False), nullable=False)


class PadTable(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "pads"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    title = sa.Column(sa.String(99))
    # sections jsonb,
    full_text = sa.Column(sa.Text())
    status = sa.Column(sa.Integer, default=0)
    date = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now())  # pylint: disable=not-callable
    # template integer,
    # CONSTRAINT pads_template_fkey FOREIGN KEY (template)
    #     REFERENCES public.templates (id) MATCH SIMPLE
    #     ON UPDATE NO ACTION
    #     ON DELETE NO ACTION
    updated_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now())  # pylint: disable=not-callable
    # source integer,
    # CONSTRAINT pads_source_fkey FOREIGN KEY (source)
    #     REFERENCES public.pads (id) MATCH SIMPLE
    #     ON UPDATE CASCADE
    #     ON DELETE CASCADE,
    owner = sa.Column(sa.UUID)
    # version ltree,


# blogs

class ArticlesTable(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "articles"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    url = sa.Column(sa.Text(), unique=True)
    language = sa.Column(sa.Text())
    title = sa.Column(sa.Text())
    posted_date = sa.Column(sa.Date())
    posted_date_str = sa.Column(sa.String(50))
    article_type = sa.Column(sa.Text())
    created_at = sa.Column(
        sa.DateTime(timezone=False),
        server_default=sa.func.now())  # pylint: disable=not-callable
    updated_at = sa.Column(
        sa.DateTime(timezone=False),
        server_default=sa.func.now())  # pylint: disable=not-callable
    deleted_at = sa.Column(sa.DateTime(timezone=False), nullable=True)
    deleted = sa.Column(sa.Boolean, default=False)
    has_lab = sa.Column(sa.Boolean)
    iso3_nlp = sa.Column(sa.String(3))
    lat = sa.Column(sa.Double)
    lng = sa.Column(sa.Double)
    privilege = sa.Column(sa.Integer, default=1)
    rights = sa.Column(sa.Integer, default=1)
    # tags text[] COLLATE pg_catalog."default",
    parsed_date = sa.Column(sa.DateTime(timezone=False), nullable=True)
    relevance = sa.Column(sa.Integer, default=0)
    iso3 = sa.Column(sa.String(3))


class ArticleContentTable(Base):  # pylint: disable=too-few-public-methods
    __tablename__ = "article_content"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    article_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            ArticlesTable.id,
            onupdate="NO ACTION",
            ondelete="CASCADE"),
        nullable=False,
        unique=True)
    content = sa.Column(sa.Text())
    created_at = sa.Column(
        sa.DateTime(timezone=False),
        server_default=sa.func.now())  # pylint: disable=not-callable
    updated_at = sa.Column(
        sa.DateTime(timezone=False),
        server_default=sa.func.now())  # pylint: disable=not-callable
