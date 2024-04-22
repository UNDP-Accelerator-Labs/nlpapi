import time
from collections.abc import Callable
from typing import TypeVar

from redipy import Redis, RSM_MISSING


T = TypeVar('T')


def clear_cache(cache: Redis) -> None:
    cache.flushall()


def cached(
        cache: Redis,
        *,
        cache_type: str,
        db_name: str,
        cache_hash: str,
        compute_fn: Callable[[], T],
        pre_cache_fn: Callable[[T], str],
        post_fn: Callable[[str], T | None],
        timeout: float = 300.0,
        wait_sleep: float = 0.1,
        ) -> T:
    cache_key = f"{cache_type}:{db_name}:{cache_hash}"
    res = cache.get_value(cache_key)
    if res is not None:
        if not res:
            print(f"{cache_type.upper()} CACHE DEFERRED {cache_key}")
            start_time = time.monotonic()
            while (
                    res is not None
                    and not res
                    and time.monotonic() - start_time < timeout):
                if wait_sleep > 0.0:
                    time.sleep(wait_sleep)
                res = cache.get_value(cache_key)
        if res:
            response = post_fn(res)
            if response is not None:
                print(f"{cache_type.upper()} CACHE HIT {cache_key}")
                return response
    print(f"{cache_type.upper()} CACHE MISS {cache_key}")
    cache.set_value(cache_key, "", mode=RSM_MISSING)
    ret_val = compute_fn()
    ret_str = pre_cache_fn(ret_val)
    if not ret_str:
        raise ValueError(
            f"cache string must not be empty! {cache_type=} {cache_key=}")
    cache.set_value(cache_key, ret_str)
    return ret_val
