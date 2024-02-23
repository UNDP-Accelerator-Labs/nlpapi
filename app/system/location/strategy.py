import collections
from collections.abc import Callable
from typing import get_args, Literal, TYPE_CHECKING


if TYPE_CHECKING:
    from app.system.location.response import GeoLocation, GeoResult


Strategy = Literal["top", "frequency"]
STRATEGIES = get_args(Strategy)


StrategyCallback = Callable[[str], 'GeoLocation']


class LocationStrategy:  # pylint: disable=too-few-public-methods
    @staticmethod
    def get_callback(
            queries: list[str],
            results: dict[str, 'GeoResult']) -> StrategyCallback:
        raise NotImplementedError()


class TopStrategy(LocationStrategy):  # pylint: disable=too-few-public-methods
    @staticmethod
    def get_callback(
            queries: list[str],
            results: dict[str, 'GeoResult']) -> StrategyCallback:

        def get_response(query: str) -> 'GeoLocation':
            resps, status = results.get(query, (None, "invalid"))
            return (resps[0] if resps else None, status)

        return get_response


class FreqStrategy(LocationStrategy):  # pylint: disable=too-few-public-methods
    @staticmethod
    def get_callback(
            queries: list[str],
            results: dict[str, 'GeoResult']) -> StrategyCallback:

        def get_order() -> dict[str, float]:
            country_count: collections.defaultdict[str, float] = \
                collections.defaultdict(lambda: 0.0)
            for query in queries:
                res, _ = results.get(query, (None, "invalid"))
                if res is None:
                    continue
                for (pos, geo) in enumerate(res):
                    cur_confidence = geo["confidence"] / (pos + 1.0)
                    country_count[geo["country"]] += cur_confidence
            return country_count

        country_order = get_order()

        def get_response(query: str) -> 'GeoLocation':
            resps, status = results.get(query, (None, "invalid"))
            if resps is None:
                return (None, status)
            max_confidence_ratio = None
            best_resp = None
            for (pos, resp) in enumerate(resps):
                country_confidence = country_order.get(resp["country"], 0.0)
                confidence_ratio = (
                    resp["confidence"]
                    / (pos + 1.0)
                    / (1.0 + country_confidence))
                if (max_confidence_ratio is None
                        or confidence_ratio > max_confidence_ratio):
                    max_confidence_ratio = confidence_ratio
                    best_resp = resp
            return (best_resp, status)

        return get_response


def get_strategy(strategy: Strategy) -> LocationStrategy:
    if strategy == "top":
        return TopStrategy()
    if strategy == "frequency":
        return FreqStrategy()
    raise ValueError(f"unknown strategy ({STRATEGIES}): {strategy}")
