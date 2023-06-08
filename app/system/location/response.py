from typing import Literal, TypedDict

from app.system.location.spacy import Language
from app.system.location.strategy import Strategy


GeoStatus = Literal[
    "cache_hit",
    "cache_miss",
    "cache_never",
    "invalid",
    "ok",
    "ratelimit",
]


STATUS_ORDER: list[GeoStatus] = [
    "ratelimit",
    "invalid",
    "cache_miss",
    "cache_never",
    "cache_hit",
    "ok",
]


GeoResponse = TypedDict('GeoResponse', {
    "lat": float,
    "lng": float,
    "formatted": str,
    "country": str,
    "confidence": float,
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
    "entites": list[EntityInfo],
})


GeoQuery = TypedDict('GeoQuery', {
    "input": str,
    "return_input": bool,
    "return_context": bool,
    "strategy": Strategy,
    "language": Language,
})
