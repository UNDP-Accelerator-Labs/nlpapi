import collections
from uuid import UUID

from app.misc.context import get_context
from app.system.db.base import LocationCache, LocationEntries, LocationUsers
from app.system.db.db import DBConnector
from app.system.location.cache import read_geo_cache, write_geo_cache
from app.system.location.forwardgeo import geo_result
from app.system.location.response import (
    EntityInfo,
    GeoOutput,
    GeoQuery,
    GeoResult,
    GeoStatus,
    STATUS_MAP,
    STATUS_ORDER,
    StatusCount,
)
from app.system.location.spacy import get_locations
from app.system.location.strategy import get_strategy
from app.system.spacy import create_length_counter, get_spacy


def extract_locations(
        db: DBConnector, geo_query: GeoQuery, user: UUID) -> GeoOutput:
    strategy = get_strategy(geo_query["strategy"])
    rt_context = geo_query["return_context"]
    rt_input = geo_query["return_input"]
    input_text = geo_query["input"]
    lnc, lnr = create_length_counter()

    with get_spacy(geo_query["language"]) as nlp:
        entities = [
            (entity.strip(), start, stop)
            for (entity, start, stop)
            in get_locations(nlp, input_text, lnc)
        ]

    query_list = [entity for entity, _, _ in entities]
    queries = set(query_list)
    cache_res = read_geo_cache(db, queries)
    compute_res: dict[str, GeoResult] = {}
    for query, cres in cache_res.items():
        if cres[0] is not None:
            continue
        compute_res[query] = geo_result(query)
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
            location_length=total_length,
        )
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
    db.create_tables([LocationCache, LocationEntries, LocationUsers])
