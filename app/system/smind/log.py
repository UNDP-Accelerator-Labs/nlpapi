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
"""Logs semantic search queries."""
import random
from datetime import datetime

import sqlalchemy as sa
from scattermind.system.util import get_day_str

from app.misc.util import json_compact_str
from app.system.db.base import QueryLog
from app.system.db.db import DBConnector
from app.system.smind.vec import MetaKey


def log_query(
        db: DBConnector,
        *,
        db_name: str,
        text: str,
        filters: dict[MetaKey, list[str]] | None) -> None:
    """
    Logs a semantic search query.

    Args:
        db (DBConnector): The database connector.
        db_name (str): The name of the vector database.
        text (str): The query string.
        filters (dict[MetaKey, list[str]] | None): Any filters applied to the
            query. If None the empty filter is logged.
    """
    if filters is None:
        filters_obj: dict[MetaKey, list[str]] = {}
    else:
        filters_obj = {
            key: value
            for (key, value) in filters.items()
            if value
        }
    filters_str = json_compact_str(filters_obj)
    date_str = datetime.today().strftime(r"%Y-%m-%d")
    with db.get_session() as session:
        stmt = db.upsert(QueryLog).values(
            vecdb=db_name,
            query=text,
            filters=filters_str,
            access_date=date_str)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                QueryLog.vecdb,
                QueryLog.query,
                QueryLog.filters,
                QueryLog.access_date,
            ],
            set_={
                QueryLog.access_count: QueryLog.access_count + 1,
            })
        session.execute(stmt)


def create_query_log(db: DBConnector) -> None:
    """
    Create all logging tables.

    Args:
        db (DBConnector): The database connector.
    """
    db.create_tables([QueryLog])


QUERY_LOG_CACHE: list[str] | None = None
"""Cache of log entries for sampling."""
QUERY_LOG_DATE: str | None = None
"""Date of log sampling."""


def sample_query_log(
        db: DBConnector,
        *,
        db_name: str) -> str:
    """
    Samples a random query from the log.

    Args:
        db (DBConnector): The database connector.
        db_name (str): The vector database name.

    Returns:
        str: A random search query.
    """
    global QUERY_LOG_CACHE  # pylint: disable=global-statement
    global QUERY_LOG_DATE  # pylint: disable=global-statement

    date_str = get_day_str()
    if QUERY_LOG_CACHE is None or QUERY_LOG_DATE != date_str:
        with db.get_session() as session:
            qus = sa.select(QueryLog.query).where(QueryLog.vecdb == db_name)
            qus = qus.distinct()
            stmt = sa.select(qus.c.query)
            stmt = stmt.order_by(
                sa.func.random()).limit(1000)  # pylint: disable=not-callable
            log_cache = [
                row[0]
                for row in session.execute(stmt)
            ]
        QUERY_LOG_CACHE = log_cache
        QUERY_LOG_DATE = date_str
    if not QUERY_LOG_CACHE:
        return "test"
    return QUERY_LOG_CACHE[random.randrange(len(QUERY_LOG_CACHE))]
