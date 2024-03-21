from typing import Literal, TypedDict

from app.system.location.strategy import Strategy
from app.system.spacy import LanguageStr


DEFAULT_MAX_REQUESTS = 20


GeoStatus = Literal[
    "cache_hit",
    "cache_miss",
    "cache_never",
    "invalid",
    "ok",
    "ratelimit",
    "requestlimit",
]


STATUS_ORDER: list[GeoStatus] = [
    "ratelimit",
    "invalid",
    "ok",
    "cache_miss",
    "cache_never",
    "cache_hit",
    "requestlimit",
]


DbStatus = Literal[
    "cache_hit",
    "cache_miss",
    "invalid",
    "ratelimit",
]


StatusCount = TypedDict('StatusCount', {
    "cache_miss": int,
    "cache_hit": int,
    "invalid": int,
    "ratelimit": int,
})


STATUS_MAP: dict[GeoStatus, DbStatus] = {
    "ratelimit": "ratelimit",
    "invalid": "invalid",
    "cache_miss": "cache_miss",
    "cache_never": "cache_miss",
    "cache_hit": "cache_hit",
    "ok": "cache_miss",
}


GeoResponse = TypedDict('GeoResponse', {
    "lat": float,
    "lng": float,
    "formatted": str,
    "country": str,
    "relevance": float,
})


GeoResult = tuple[list[GeoResponse] | None, GeoStatus]
GeoLocation = tuple[GeoResponse | None, GeoStatus]


EntityInfo = TypedDict('EntityInfo', {
    "query": str,
    "spans": list[tuple[int, int]],
    "contexts": list[str] | None,
    "location": GeoResponse | None,
    "count": int,
    "status": GeoStatus,
})


GeoOutput = TypedDict('GeoOutput', {
    "status": GeoStatus,
    "country": str,
    "input": str | None,
    "entities": list[EntityInfo],
})


GeoQuery = TypedDict('GeoQuery', {
    "input": str,
    "return_input": bool,
    "return_context": bool,
    "strategy": Strategy,
    "language": LanguageStr,
    "max_requests": int | None,
})
