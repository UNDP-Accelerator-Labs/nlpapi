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
"""Caching location results."""
import collections

import sqlalchemy as sa

from app.system.db.base import LocationCache, LocationEntries
from app.system.db.db import DBConnector
from app.system.location.response import GeoResponse, GeoResult


def read_geo_cache(db: DBConnector, queries: set[str]) -> dict[str, GeoResult]:
    """
    Reads previously cached results for the given queries.

    Args:
        db (DBConnector): The database connector.
        queries (set[str]): The queries.

    Returns:
        dict[str, GeoResult]: Mapping the queries to their cached results. If
            a query was not cached its key won't appear in the dictionary.
    """
    qins = sorted(query.strip() for query in queries)
    res: dict[str, GeoResult] = {}
    id_map: dict[int, str] = {}
    query_ids: set[int] = set()
    skip: set[int] = set()
    resps: collections.defaultdict[int, dict[int, GeoResponse]] = \
        collections.defaultdict(dict)
    with db.get_session() as session:
        stmt = sa.update(LocationCache)
        stmt = stmt.where(LocationCache.query.in_(qins))
        stmt = stmt.returning(
            LocationCache.query, LocationCache.id, LocationCache.no_cache)
        stmt = stmt.values(
            access_last=sa.func.now(),  # pylint: disable=not-callable
            access_count=LocationCache.access_count + 1)
        for row in session.execute(stmt):
            row_id = int(row.id)
            id_map[row_id] = row.query.strip()
            if row.no_cache:
                skip.add(row_id)
            else:
                query_ids.add(row_id)
        qids = sorted(query_ids)
        estmt = sa.select(
            LocationEntries.location_id,
            LocationEntries.pos,
            LocationEntries.lat,
            LocationEntries.lng,
            LocationEntries.formatted,
            LocationEntries.country,
            LocationEntries.confidence)
        estmt = estmt.where(LocationEntries.location_id.in_(qids))
        for row in session.execute(estmt):
            row_id = int(row.location_id)
            pos = int(row.pos)
            resps[row_id][pos] = {
                "lat": float(row.lat),
                "lng": float(row.lng),
                "formatted": f"{row.formatted}",
                "country": f"{row.country}",
                "relevance": 1.0 / (float(row.pos) + 1.0),
            }
    for skip_id in skip:
        res[id_map[skip_id]] = (None, "cache_never")
    for (resp_id, resp) in resps.items():
        resp_arr = [
            elem
            for (_, elem)
            in sorted(resp.items(), key=lambda item: item[0])
        ]
        res[id_map[resp_id]] = (resp_arr, "cache_hit")
    for qin in qins:
        if qin not in res:
            res[qin] = (None, "cache_miss")
    return res


def write_geo_cache(db: DBConnector, results: dict[str, GeoResult]) -> None:
    """
    Writes query results to the cache.

    Args:
        db (DBConnector): The database connector.
        results (dict[str, GeoResult]): The results.
    """
    with db.get_session() as session:
        for res_query, result in results.items():
            if result[0] is None:
                continue
            if result[1] in ("cache_never", "cache_hit"):
                continue
            if result[1] != "ok":
                continue
            res_arr = result[0]
            cstmt = db.upsert(LocationCache).values(
                query=res_query,
                no_cache=False)
            cstmt = cstmt.returning(LocationCache.id)
            lid = session.execute(cstmt).scalar()
            if lid is None:
                raise ValueError(f"error while inserting: {res_query}")
            for (pos, res) in enumerate(res_arr):
                country = res["country"]
                if len(country) > 4:
                    country = f"{country[:4]}?"
                stmt = db.upsert(LocationEntries).values(
                    location_id=lid,
                    pos=pos,
                    lat=res["lat"],
                    lng=res["lng"],
                    formatted=res["formatted"],
                    country=country,
                    confidence=res["relevance"])  # NOTE: not really needed
                stmt = stmt.on_conflict_do_nothing()
                session.execute(stmt)
