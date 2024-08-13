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
"""Forward geolocation lookup."""
import time
from datetime import datetime, timedelta
from typing import cast, TypedDict

from opencage.geocoder import (  # type: ignore
    OpenCageGeocode,
    RateLimitExceededError,
)

from app.system.config import get_config
from app.system.location.response import GeoResponse, GeoResult


GEOCODER: OpenCageGeocode | None = None
"""The OpenCage api."""


OpenCageGeometry = TypedDict('OpenCageGeometry', {
    "lat": float,
    "lng": float,
})
"""OpenCage location."""


OpenCageComponents = TypedDict('OpenCageComponents', {
    "ISO_3166-1_alpha-3": str,
    "country_code": str,
})
"""OpenCage country information."""


OpenCageResult = TypedDict('OpenCageResult', {
    "components": OpenCageComponents,
    "formatted": str,
    "geometry": OpenCageGeometry,
})
"""OpenCage result."""


OpenCageFormat = TypedDict('OpenCageFormat', {
    "results": list[OpenCageResult],
})
"""OpenCage result list."""


def get_geo() -> OpenCageGeocode:
    """
    Get the OpenCage api.

    Returns:
        OpenCageGeocode: The api object.
    """
    global GEOCODER  # pylint: disable=global-statement

    if GEOCODER is None:
        config = get_config()
        GEOCODER = OpenCageGeocode(config["opencage"])
    return GEOCODER


EXCEEDED_FOR_TODAY: datetime | None = None
"""Date of exceeding the quota. None if the quota is fine."""


def geo_result(query: str) -> GeoResult:
    """
    Query the OpenCage database.

    Args:
        query (str): The query.

    Returns:
        GeoResult: The geolocation result.
    """
    # pylint: disable=global-statement
    global EXCEEDED_FOR_TODAY

    eft = EXCEEDED_FOR_TODAY
    if eft is not None:
        cur_time = datetime.now(eft.tzinfo)
        if cur_time < eft:
            return (None, "ratelimit")
        EXCEEDED_FOR_TODAY = None

    tries = 10
    while tries > 0:
        tries -= 1
        try:
            query = query.strip()
            results: list[OpenCageResult] = cast(
                list, get_geo().geocode(query))
            if results and len(results):
                res: list[GeoResponse] = []
                for ix, result in enumerate(results):
                    comp = result["components"]
                    country: str = cast(str, comp.get(
                        "ISO_3166-1_alpha-3",
                        comp.get("county_code", "NUL")))
                    res.append({
                        "lat": float(result["geometry"]["lat"]),
                        "lng": float(result["geometry"]["lng"]),
                        "formatted": result["formatted"],
                        "country": country,
                        "relevance": 1.0 / (ix + 1.0),
                    })
                return (res, "ok")
            return (None, "invalid")
        except RateLimitExceededError as ree:
            sleep_time = 1.0
            reset_time: datetime | None = getattr(ree, "reset_time", None)
            if reset_time is not None:
                now_time = datetime.now(reset_time.tzinfo)
                okay_time = now_time + timedelta(seconds=10)
                sleep_time = (reset_time - now_time).total_seconds()
                if reset_time > okay_time:
                    EXCEEDED_FOR_TODAY = reset_time
                    print(
                        "WARNING: forward geocoding ratelimit reached for the "
                        f"day. will become available again in {sleep_time}s "
                        f"at {EXCEEDED_FOR_TODAY.isoformat()}")
                    break
            time.sleep(sleep_time)
    return (None, "ratelimit")


def as_opencage_format(results: list[GeoResponse]) -> OpenCageFormat:
    """
    Convert a geolocation result into the OpenCage format.

    Args:
        results (list[GeoResponse]): The geolocation result.

    Returns:
        OpenCageFormat: The OpenCage result.
    """
    return {
        "results": [
            {
                "components": {
                    "country_code": result["country"],
                    "ISO_3166-1_alpha-3": result["country"],
                },
                "formatted": result["formatted"],
                "geometry": {
                    "lat": result["lat"],
                    "lng": result["lng"],
                },
            }
            for result in sorted(
                results, key=lambda v: v["relevance"], reverse=True)
        ],
    }
