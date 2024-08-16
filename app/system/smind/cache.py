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
"""Caching of embedding model results."""
from collections.abc import Callable
from typing import TypeVar

from redipy import Redis


T = TypeVar('T')


def clear_cache(cache: Redis, *, db_name: str | None) -> None:
    """
    Clears the cache for a specific vector database.

    Args:
        cache (Redis): The redis cache database.
        db_name (str | None): The vector database name or None to flush all
            caches.
    """
    if db_name is None:
        cache.flushall()
    else:
        for key in cache.keys(match=f"{db_name}:*", block=True):
            cache.delete(key)


def cached(
        cache: Redis,
        *,
        cache_type: str,
        db_name: str,
        cache_hash: str,
        compute_fn: Callable[[], T],
        pre_cache_fn: Callable[[T], str],
        post_fn: Callable[[str], T | None],
        timeout: float = 300.0,  # pylint: disable=unused-argument
        wait_sleep: float = 0.1,  # pylint: disable=unused-argument
        ) -> T:
    """
    Process a caching value. If the value is available in the cache it is
    returned, otherwise the value is computed and put into the cache.

    Args:
        cache (Redis): The redis cache database. Must have a LRU or similar key
            expiration policy.
        cache_type (str): The cache type identifier. The value must be
            consistent for a given type of computation.
        db_name (str): The vector database name.
        cache_hash (str): The hash of the task to compute.
        compute_fn (Callable[[], T]): Computes the task.
        pre_cache_fn (Callable[[T], str]): Converts the task output into a
            string that can be stored in redis. The string must never be empty.
        post_fn (Callable[[str], T | None]): Converts a string stored in redis
            to the correct output type.
        timeout (float, optional): Unused timeout in seconds.
            Defaults to 300.0.
        wait_sleep (float, optional): Unused sleep time in seconds. Defaults
            to 0.1.

    Raises:
        ValueError: If the string to be stored in redis is empty.

    Returns:
        T: The result of the task.
    """
    cache_key = f"{db_name}:{cache_type}:{cache_hash}"
    res = cache.get_value(cache_key)
    if res is not None:
        if not res:
            pass
            # FIXME: implement properly
            # print(f"{cache_type.upper()} CACHE DEFERRED {cache_key}")
            # start_time = time.monotonic()
            # while (
            #         res is not None
            #         and not res
            #         and time.monotonic() - start_time < timeout):
            #     if wait_sleep > 0.0:
            #         time.sleep(wait_sleep)
            #     res = cache.get_value(cache_key)
        if res:
            response = post_fn(res)
            if response is not None:
                print(f"{cache_type.upper()} CACHE HIT {cache_key}")
                return response
    print(f"{cache_type.upper()} CACHE MISS {cache_key}")
    # cache.set_value(cache_key, "", mode=RSM_MISSING)
    ret_val = compute_fn()
    ret_str = pre_cache_fn(ret_val)
    if not ret_str:
        raise ValueError(
            f"cache string must not be empty! {cache_type=} {cache_key=}")
    cache.set_value(cache_key, ret_str)
    return ret_val
