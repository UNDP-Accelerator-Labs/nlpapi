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
"""Keep the vector database alive and in cache by periodically querying a
random search term."""
import threading
import time
from typing import Protocol

from qdrant_client import QdrantClient

from app.system.db.db import DBConnector
from app.system.smind.api import GraphProfile
from app.system.smind.log import sample_query_log
from app.system.smind.vec import MetaKey, QueryEmbed


class VecSearch(Protocol):  # pylint: disable=too-few-public-methods
    """Function for performing a semantic search."""
    def __call__(
            self,
            db: DBConnector,
            vec_db: QdrantClient,
            input_str: str,
            *,
            articles: str,
            articles_graph: GraphProfile,
            filters: dict[MetaKey, list[str]] | None,
            order_by: MetaKey | tuple[MetaKey, str] | None,
            offset: int | None,
            limit: int,
            hit_limit: int,
            score_threshold: float | None,
            short_snippets: bool,
            no_log: bool) -> QueryEmbed:
        """
        Searches for the given string in the vector database. If the search
        query is empty the latest documents are returned instead. If the search
        query starts with `=` followed by a main id (e.g., `=solution:1234`)
        a nearest neighbor search to the given document is performed. Snippets
        are only generated for regular searches.

        Args:
            db (DBConnector): The database connector.
            vec_db (QdrantClient): The vector database client.
            input_str (str): The search query.
            articles (str): The vector database name.
            articles_graph (GraphProfile): The embedding model.
            filters (dict[MetaKey, list[str]] | None): Query filters. A mapping
                of meta data fields to a list of included values. The date
                field, if given, expects a list of exactly two values, the
                start and end date (both inclusive). If None defaults to
                the empty filter.
            order_by (MetaKey | tuple[MetaKey, str] | None): Which way to order
                non-search results.
            offset (int | None): The offset of the returned results. If None
                defaults to 0.
            limit (int): The maximum number of returned results.
            hit_limit (int): The maximum number of hit snippets generated per
                result.
            score_threshold (float | None): Allows to limit the number of
                results further by cutting off at a given score threshold.
                If None defaults to not limiting by score.
            short_snippets (bool): Whether hit snippets should be further
                refined to give more precise and relevant snippets.
            no_log (bool): If True, no log entry is created for the query.

        Returns:
            QueryEmbed: Vector database search results.
        """


MAIN_DB: DBConnector | None = None
"""The database connector for the keepalive query."""
MAIN_VEC_DB: QdrantClient | None = None
"""The vector database client for the keepalive query."""
MAIN_ARTICLES: str | None = None
"""The vector database name for the keepalive query."""
MAIN_GRAPH: GraphProfile | None = None
"""The embedding model for the keepalive query."""
MAIN_FN: VecSearch | None = None
"""The search function for the keepalive query."""
LAST_QUERY: float = 0.0
"""Time of any latest query."""
KEEP_ALIVE_LOCK: 'threading.RLock | None' = None  # FIXME: type fixed in p3.13
"""Lock for the keepalive query."""
KEEP_ALIVE_TH: threading.Thread | None = None
"""Thread performing the the keepalive query."""
KEEP_ALIVE_FREQ: float = 60.0  # 1min
"""The frequency of the keepalive query in seconds."""


def set_main_articles(
        db: DBConnector,
        vec_db: QdrantClient,
        *,
        articles: str,
        articles_graph: GraphProfile,
        vec_search_fn: VecSearch) -> None:
    """
    Initializes the keep alive query.

    Args:
        db (DBConnector): The database connector.
        vec_db (QdrantClient): The vector database client.
        articles (str): The vector database name.
        articles_graph (GraphProfile): The embedding model.
        vec_search_fn (VecSearch): The search function.

    Raises:
        ValueError: If the function is called more than once.
    """
    global MAIN_DB  # pylint: disable=global-statement
    global MAIN_VEC_DB  # pylint: disable=global-statement
    global MAIN_ARTICLES  # pylint: disable=global-statement
    global MAIN_GRAPH  # pylint: disable=global-statement
    global MAIN_FN  # pylint: disable=global-statement
    global KEEP_ALIVE_LOCK  # pylint: disable=global-statement

    if MAIN_ARTICLES is not None or KEEP_ALIVE_LOCK is not None:
        raise ValueError(
            f"{set_main_articles.__name__} can only be called once!")

    MAIN_DB = db
    MAIN_VEC_DB = vec_db
    MAIN_ARTICLES = articles
    MAIN_GRAPH = articles_graph
    MAIN_FN = vec_search_fn
    KEEP_ALIVE_LOCK = threading.RLock()
    update_last_query(long_time=False, update_time=False)


def update_last_query(*, long_time: bool, update_time: bool = True) -> None:
    """
    Updates when any query is run. This pushes out the next keep alive query.
    Starts the keep alive query if no thread is running.

    Args:
        long_time (bool): Push the next keep alive query out for an additional
            600 seconds.
        update_time (bool, optional): Whether to update the query time.
            If set to False, this function only ensures that the keep alive
            thread is running. Defaults to True.

    Raises:
        ValueError: If the keep alive query has not been properly set up yet.
    """
    global LAST_QUERY  # pylint: disable=global-statement
    global KEEP_ALIVE_TH  # pylint: disable=global-statement

    if update_time:
        delay = 600.0 if long_time else 0.0
        LAST_QUERY = max(LAST_QUERY, time.monotonic() + delay)
    if KEEP_ALIVE_TH is not None and KEEP_ALIVE_TH.is_alive():
        return
    m_db = MAIN_DB
    m_vec_db = MAIN_VEC_DB
    m_lock = KEEP_ALIVE_LOCK
    m_articles = MAIN_ARTICLES
    m_articles_graph = MAIN_GRAPH
    m_vec_search_fn = MAIN_FN
    assert m_vec_search_fn is not None
    vec_search_fn = m_vec_search_fn
    if (
            m_db is None
            or m_vec_db is None
            or m_lock is None
            or m_articles is None
            or m_articles_graph is None):
        raise ValueError(f"must call {set_main_articles.__name__} first!")
    db = m_db
    vec_db = m_vec_db
    lock = m_lock
    articles = m_articles
    articles_graph = m_articles_graph

    def run() -> None:
        freq = KEEP_ALIVE_FREQ
        while th is KEEP_ALIVE_TH:
            last_query = time.monotonic() - LAST_QUERY
            if last_query >= freq:
                input_str = sample_query_log(db, db_name=articles)
                res = vec_search_fn(
                    db,
                    vec_db,
                    input_str,
                    articles=articles,
                    articles_graph=articles_graph,
                    filters=None,
                    order_by=None,
                    offset=None,
                    limit=10,
                    hit_limit=1,
                    score_threshold=None,
                    short_snippets=True,
                    no_log=True)
                if res["status"] != "ok":
                    print(
                        f"WARNING: keepalive query {input_str} was not okay! "
                        f"{res}")
                    time.sleep(freq)
            else:
                sleep = freq - last_query
                if sleep > 0.0:
                    time.sleep(sleep)

    with lock:
        if KEEP_ALIVE_TH is not None and KEEP_ALIVE_TH.is_alive():
            return
        th = threading.Thread(target=run, daemon=True)
        KEEP_ALIVE_TH = th
        th.start()
