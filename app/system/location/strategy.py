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
"""Strategy to determine the main location of a document."""
import collections
from collections.abc import Callable
from typing import get_args, Literal, TYPE_CHECKING


if TYPE_CHECKING:
    from app.system.location.response import GeoLocation, GeoResult


Strategy = Literal["top", "frequency"]
"""Available document location strategies."""
STRATEGIES = get_args(Strategy)
"""Available document location strategies."""


StrategyCallback = Callable[[str], 'GeoLocation']
"""Function to get location for a given query."""


class LocationStrategy:  # pylint: disable=too-few-public-methods
    """The location strategy interface."""
    @staticmethod
    def get_callback(
            queries: list[str],
            results: dict[str, 'GeoResult']) -> StrategyCallback:
        """
        Creates the strategy callback to retrieve locations from a given query.

        Args:
            queries (list[str]): The list of queries.
            results (dict[str, GeoResult]): The results of the queries.

        Returns:
            StrategyCallback: The function to read out the results.
        """
        raise NotImplementedError()


class TopStrategy(LocationStrategy):  # pylint: disable=too-few-public-methods
    """The top strategy takes the most likely country of a given query."""
    @staticmethod
    def get_callback(
            queries: list[str],
            results: dict[str, 'GeoResult']) -> StrategyCallback:

        def get_response(query: str) -> 'GeoLocation':
            resps, status = results.get(query, (None, "invalid"))
            return (resps[0] if resps else None, status)

        return get_response


class FreqStrategy(LocationStrategy):  # pylint: disable=too-few-public-methods
    """The frequency strategy takes the most frequent country of the entire
    result."""
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
                for geo in res:
                    country_count[geo["country"]] += geo["relevance"]
            return country_count

        country_order = get_order()

        def get_response(query: str) -> 'GeoLocation':
            resps, status = results.get(query, (None, "invalid"))
            if resps is None:
                return (None, status)
            max_confidence_ratio = None
            best_resp = None
            for resp in resps:
                country_confidence = country_order.get(resp["country"], 0.0)
                confidence_ratio = (
                    resp["relevance"]
                    / (1.0 + country_confidence))
                if (max_confidence_ratio is None
                        or confidence_ratio > max_confidence_ratio):
                    max_confidence_ratio = confidence_ratio
                    best_resp = resp
            return (best_resp, status)

        return get_response


def get_strategy(strategy: Strategy) -> LocationStrategy:
    """
    Load a location strategy.

    Args:
        strategy (Strategy): The strategy to load.

    Raises:
        ValueError: If the strategy is invalid.

    Returns:
        LocationStrategy: The strategy.
    """
    if strategy == "top":
        return TopStrategy()
    if strategy == "frequency":
        return FreqStrategy()
    raise ValueError(f"unknown strategy ({STRATEGIES}): {strategy}")
