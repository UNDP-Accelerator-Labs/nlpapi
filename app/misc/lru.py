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
import time
from collections.abc import Callable
from typing import Generic, TypeVar


KT = TypeVar('KT')
VT = TypeVar('VT')


MAX_RETRY = 10
RETRY_WAIT = 0.1


class LRU(Generic[KT, VT]):
    def __init__(
            self,
            max_items: int,
            soft_limit: int | None = None) -> None:
        self._values: dict[KT, VT] = {}
        self._times: dict[KT, float] = {}
        self._max_items = max_items
        self._soft_limit = (
            max(1, int(max_items * 0.9)) if soft_limit is None else soft_limit)
        assert self._max_items >= self._soft_limit

    def get(self, key: KT) -> VT | None:
        res = self._values.get(key)
        if res is not None:
            self._times[key] = time.monotonic()
        return res

    def set(self, key: KT, value: VT) -> None:
        self._values[key] = value
        self._times[key] = time.monotonic()
        self.gc()

    def clear_keys(self, prefix_match: Callable[[KT], bool]) -> None:
        for key in list(self._values.keys()):
            if prefix_match(key):
                self._values.pop(key, None)
                self._times.pop(key, None)

    def gc(self) -> None:
        retry = 0
        while len(self._values) > self._max_items:
            try:
                to_remove = sorted(
                    self._times.copy().items(),
                    key=lambda item: item[1])[:-self._soft_limit]
                for rm_item in to_remove:
                    key = rm_item[0]
                    self._values.pop(key, None)
                    self._times.pop(key, None)
            except RuntimeError:
                # dictionary changed size during iteration: try again
                if retry >= MAX_RETRY:
                    raise
                retry += 1
                if RETRY_WAIT > 0:
                    time.sleep(RETRY_WAIT)
