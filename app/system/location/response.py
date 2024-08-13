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
"""Response types for the location api."""
from typing import Literal, TypedDict

from app.system.location.strategy import Strategy


DEFAULT_MAX_REQUESTS: int | None = None
"""Maximum number of requests for a given query or None if no maximum is set.
"""


LanguageStr = Literal["en", "xx"]
"""Available languages for NER. `xx` is multilingual."""


GeoStatus = Literal[
    "cache_hit",
    "cache_miss",
    "cache_never",
    "invalid",
    "ok",
    "ratelimit",
    "requestlimit",
]
"""Status of location results."""


STATUS_ORDER: list[GeoStatus] = [
    "ratelimit",
    "invalid",
    "ok",
    "cache_miss",
    "cache_never",
    "cache_hit",
    "requestlimit",
]
"""Priority of location result statuses."""


DbStatus = Literal[
    "cache_hit",
    "cache_miss",
    "invalid",
    "ratelimit",
]
"""Database status for location results."""


StatusCount = TypedDict('StatusCount', {
    "cache_miss": int,
    "cache_hit": int,
    "invalid": int,
    "ratelimit": int,
})
"""Location result status that get counted towards the user's usage."""


STATUS_MAP: dict[GeoStatus, DbStatus] = {
    "ratelimit": "ratelimit",
    "invalid": "invalid",
    "cache_miss": "cache_miss",
    "cache_never": "cache_miss",
    "cache_hit": "cache_hit",
    "ok": "cache_miss",
}
"""Mapping geolocation result status to database equivalent."""


GeoResponse = TypedDict('GeoResponse', {
    "lat": float,
    "lng": float,
    "formatted": str,
    "country": str,
    "relevance": float,
})
"""Location response."""


GeoResult = tuple[list[GeoResponse] | None, GeoStatus]
"""Result of location responses and status."""
GeoLocation = tuple[GeoResponse | None, GeoStatus]
"""Result of location response and status."""


EntityInfo = TypedDict('EntityInfo', {
    "query": str,
    "spans": list[tuple[int, int]],
    "contexts": list[str] | None,
    "location": GeoResponse | None,
    "count": int,
    "status": GeoStatus,
})
"""A location hit."""


GeoOutput = TypedDict('GeoOutput', {
    "status": GeoStatus,
    "country": str,
    "input": str | None,
    "entities": list[EntityInfo],
})
"""Geolocation result."""


GeoQuery = TypedDict('GeoQuery', {
    "input": str,
    "return_input": bool,
    "return_context": bool,
    "strategy": Strategy,
    "language": LanguageStr,
    "max_requests": int | None,
})
"""Specification of a geolocation query."""
