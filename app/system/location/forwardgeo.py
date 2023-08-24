import time
from datetime import datetime, timedelta

from opencage.geocoder import (  # type: ignore
    OpenCageGeocode,
    RateLimitExceededError,
)

from app.system.config import get_config
from app.system.location.response import GeoResponse, GeoResult


GEOCODER: OpenCageGeocode | None = None


def get_geo() -> OpenCageGeocode:
    global GEOCODER

    if GEOCODER is None:
        config = get_config()
        GEOCODER = OpenCageGeocode(config["opencage"])
    return GEOCODER


def geo_result(query: str) -> GeoResult:
    tries = 10
    while tries > 0:
        tries -= 1
        try:
            query = query.strip()
            results = get_geo().geocode(query)
            if results and len(results):
                res: list[GeoResponse] = []
                for result in results:
                    comp = result["components"]
                    country = comp.get(
                        "ISO_3166-1_alpha-3",
                        comp.get("county_code", "NUL"))
                    res.append({
                        "lat": float(result["geometry"]["lat"]),
                        "lng": float(result["geometry"]["lng"]),
                        "formatted": result["formatted"],
                        "country": country,
                        "confidence": 1.0 / float(result["confidence"]),
                    })
                return (res, "ok")
            return (None, "invalid")
        except RateLimitExceededError as ree:
            sleep_time = 1.0
            reset_time: datetime | None = getattr(ree, "reset_time", None)
            if reset_time is not None:
                now_time = datetime.now(reset_time.tzinfo)
                okay_time = now_time + timedelta(seconds=10)
                if reset_time > okay_time:
                    break
                sleep_time = (reset_time - now_time).total_seconds()
            time.sleep(sleep_time)
    return (None, "ratelimit")
