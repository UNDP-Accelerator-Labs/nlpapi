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
    except RateLimitExceededError:
        return (None, "ratelimit")
