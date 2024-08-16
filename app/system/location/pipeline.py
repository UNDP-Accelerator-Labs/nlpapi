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
"""Pipeline for extracting locations from a given text."""
import collections
from uuid import UUID

from app.misc.context import get_context
from app.system.db.base import LocationCache, LocationEntries, LocationUsers
from app.system.db.db import DBConnector
from app.system.location.cache import read_geo_cache, write_geo_cache
from app.system.location.forwardgeo import (
    as_opencage_format,
    geo_result,
    OpenCageFormat,
    OpenCageResult,
)
from app.system.location.response import (
    EntityInfo,
    GeoOutput,
    GeoQuery,
    GeoResult,
    GeoStatus,
    LanguageStr,
    STATUS_MAP,
    STATUS_ORDER,
    StatusCount,
)
from app.system.location.spacy import get_locations
from app.system.location.strategy import get_strategy
from app.system.smind.api import GraphProfile
from app.system.stats import create_length_counter


NO_COUNT_REQUESTS: set[GeoStatus] = {"requestlimit"}
"""Set of statuses that won't result in a count towards the user usage."""


def extract_opencage(db: DBConnector, text: str, user: UUID) -> OpenCageFormat:
    """
    Extracts locations using OpenCage.

    Args:
        db (DBConnector): The database connector.
        text (str): The text.
        user (UUID): The user uuid.

    Returns:
        OpenCageFormat: The geolocation results in OpenCage format.
    """
    query = text.strip()
    cache_res = read_geo_cache(db, {query})
    results: list[OpenCageResult] = []
    status_count: StatusCount = {
        "cache_hit": 0,
        "cache_miss": 0,
        "invalid": 0,
        "ratelimit": 0,
    }
    for key, cres in cache_res.items():
        resp, status = cres
        if resp is not None:
            results.extend(as_opencage_format(resp)["results"])
            if status not in NO_COUNT_REQUESTS:
                status_count[STATUS_MAP[status]] += 1
            continue
        geo_res = geo_result(key)
        write_geo_cache(db, {key: geo_res})
        geo_response, geo_status = geo_res
        if geo_status not in NO_COUNT_REQUESTS:
            status_count[STATUS_MAP[geo_status]] += 1
        if geo_response is not None:
            results.extend(as_opencage_format(geo_response)["results"])
    with db.get_session() as session:
        total_length = len(query)
        stmt = db.upsert(LocationUsers).values(
            userid=user,
            cache_miss=status_count["cache_miss"],
            cache_hit=status_count["cache_hit"],
            invalid=status_count["invalid"],
            ratelimit=status_count["ratelimit"],
            location_count=1,
            location_length=total_length)
        stmt = stmt.on_conflict_do_update(
            index_elements=[LocationUsers.userid],
            set_={
                LocationUsers.cache_miss:
                    LocationUsers.cache_miss + status_count["cache_miss"],
                LocationUsers.cache_hit:
                    LocationUsers.cache_hit + status_count["cache_hit"],
                LocationUsers.invalid:
                    LocationUsers.invalid + status_count["invalid"],
                LocationUsers.ratelimit:
                    LocationUsers.ratelimit + status_count["ratelimit"],
                LocationUsers.location_count:
                    LocationUsers.location_count + 1,
                LocationUsers.location_length:
                    LocationUsers.location_length + total_length,
            })
        session.execute(stmt)
    return {
        "results": results,
    }


def extract_locations(
        db: DBConnector,
        graph_profiles: dict[LanguageStr, GraphProfile],
        geo_query: GeoQuery,
        user: UUID) -> GeoOutput:
    """
    Extracts locations from the given text.

    Args:
        db (DBConnector): The database connector.
        graph_profiles (dict[LanguageStr, GraphProfile]): NER models for
            different languages.
        geo_query (GeoQuery): The query to perform.
        user (UUID): The user uuid.

    Returns:
        GeoOutput: The geolocation result.
    """
    strategy = get_strategy(geo_query["strategy"])
    rt_context = geo_query["return_context"]
    max_requests = geo_query["max_requests"]
    rt_input = geo_query["return_input"]
    input_text = geo_query["input"]
    lnc, lnr = create_length_counter()

    graph_profile = graph_profiles[geo_query["language"]]
    entities = [
        (entity.strip(), start, stop)
        for (entity, start, stop)
        in get_locations(graph_profile, input_text, lnc)
    ]

    query_list = [entity for entity, _, _ in entities]
    queries = set(query_list)
    cache_res = read_geo_cache(db, queries)
    compute_res: dict[str, GeoResult] = {}
    requests = 0
    for query, cres in cache_res.items():
        if cres[0] is not None:
            continue
        if max_requests is None or requests < max_requests:
            requests += 1
            compute_res[query] = geo_result(query)
        else:
            compute_res[query] = (None, "requestlimit")
    write_geo_cache(db, compute_res)
    get_resp = strategy.get_callback(query_list, {
        query: compute_res.get(query, cache_res[query])
        for query in queries
    })

    country_count: collections.Counter[str] = collections.Counter()
    worst_status: GeoStatus = STATUS_ORDER[-1]
    worst_ix = STATUS_ORDER.index(worst_status)
    status_count: StatusCount = {
        "cache_hit": 0,
        "cache_miss": 0,
        "invalid": 0,
        "ratelimit": 0,
    }
    entity_map: dict[str, EntityInfo] = {}
    for entity in entities:
        query, start, stop = entity
        # if query != input_text[start:stop]:
        #     raise ValueError(
        #         f"oops: '{query}' {start} {stop} '{input_text[start:stop]}'")
        info = entity_map.get(query, None)
        if info is None:
            loc, status = get_resp(query)
            if loc is not None and loc["country"] == "NUL":
                print(f"WARNING: location '{query}' returned NUL country!")
            if status not in NO_COUNT_REQUESTS:
                status_count[STATUS_MAP[status]] += 1
            status_ix = STATUS_ORDER.index(status)
            if status_ix < worst_ix:
                worst_ix = status_ix
                worst_status = status
            info = {
                "query": query,
                "spans": [],
                "contexts": [] if rt_context else None,
                "location": loc,
                "count": 0,
                "status": status,
            }
            entity_map[query] = info
        info["count"] += 1
        info["spans"].append((start, stop))
        if info["contexts"] is not None:
            info["contexts"].append(get_context(input_text, start, stop))
        if info["location"] is not None:
            country_count[info["location"]["country"]] += 1

    likely_country = country_count.most_common(1)
    final_entries = sorted(
        entity_map.values(),
        key=lambda entity: entity["count"],
        reverse=True)
    with db.get_session() as session:
        total_length = lnr()
        stmt = db.upsert(LocationUsers).values(
            userid=user,
            cache_miss=status_count["cache_miss"],
            cache_hit=status_count["cache_hit"],
            invalid=status_count["invalid"],
            ratelimit=status_count["ratelimit"],
            location_count=1,
            location_length=total_length)
        stmt = stmt.on_conflict_do_update(
            index_elements=[LocationUsers.userid],
            set_={
                LocationUsers.cache_miss:
                    LocationUsers.cache_miss + status_count["cache_miss"],
                LocationUsers.cache_hit:
                    LocationUsers.cache_hit + status_count["cache_hit"],
                LocationUsers.invalid:
                    LocationUsers.invalid + status_count["invalid"],
                LocationUsers.ratelimit:
                    LocationUsers.ratelimit + status_count["ratelimit"],
                LocationUsers.location_count:
                    LocationUsers.location_count + 1,
                LocationUsers.location_length:
                    LocationUsers.location_length + total_length,
            })
        session.execute(stmt)
    return {
        "status": worst_status,
        "country": likely_country[0][0] if likely_country else "NUL",
        "input": input_text if rt_input else None,
        "entities": final_entries,
    }


def create_location_tables(db: DBConnector) -> None:
    """
    Creates all tables for the location api.

    Args:
        db (DBConnector): The database connector.
    """
    db.create_tables([LocationCache, LocationEntries, LocationUsers])
