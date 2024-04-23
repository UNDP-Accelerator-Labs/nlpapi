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


OpenCageGeometry = TypedDict('OpenCageGeometry', {
    "lat": float,
    "lng": float,
})


OpenCageComponents = TypedDict('OpenCageComponents', {
    "ISO_3166-1_alpha-3": str,
    "country_code": str,
})


OpenCageResult = TypedDict('OpenCageResult', {
    "components": OpenCageComponents,
    "formatted": str,
    "geometry": OpenCageGeometry,
})


OpenCageFormat = TypedDict('OpenCageFormat', {
    "results": list[OpenCageResult],
})


def get_geo() -> OpenCageGeocode:
    global GEOCODER  # pylint: disable=global-statement

    if GEOCODER is None:
        config = get_config()
        GEOCODER = OpenCageGeocode(config["opencage"])
    return GEOCODER


EXCEEDED_FOR_TODAY: datetime | None = None


def geo_result(query: str) -> GeoResult:
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
