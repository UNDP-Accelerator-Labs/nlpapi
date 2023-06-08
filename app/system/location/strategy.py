import collections
from typing import Callable, get_args, Literal, TYPE_CHECKING


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

        def get_order() -> list[str]:
            country_count: collections.Counter[str] = collections.Counter()
            for query in queries:
                res, _ = results.get(query, (None, "invalid"))
                if res is None:
                    continue
                for geo in res:
                    country_count[geo["country"]] += 1
                    # break  # NOTE: uncomment to use topmost frequency only
            return [
                country
                for (country, _)
                in country_count.most_common()
            ]

        country_order = get_order()

        def get_response(query: str) -> 'GeoLocation':
            resps, status = results.get(query, (None, "invalid"))
            if resps is None:
                return (None, status)
            for country in country_order:
                for resp in resps:
                    if resp["country"] == country:
                        return (resp, status)
            return (None, status)

        return get_response


def get_strategy(strategy: Strategy) -> LocationStrategy:
    if strategy == "top":
        return TopStrategy()
    if strategy == "frequency":
        return FreqStrategy()
    raise ValueError(f"unknown strategy ({STRATEGIES}): {strategy}")
