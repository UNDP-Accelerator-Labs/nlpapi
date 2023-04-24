# Stubs for pandas.core.indexes.range (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.
# pylint: disable=unused-argument,redefined-outer-name,invalid-name
# pylint: disable=relative-beyond-top-level,arguments-differ
# pylint: disable=no-member,too-few-public-methods,keyword-arg-before-vararg
# pylint: disable=super-init-not-called,abstract-method,redefined-builtin
# pylint: disable=unused-import,useless-import-alias,signature-differs
# pylint: disable=blacklisted-name,c-extension-no-member,too-many-ancestors

from typing import Any, Optional, Union

import numpy as np
from pandas.core.indexes.numeric import Int64Index


class RangeIndex(Int64Index):
    def __new__(
            cls, start: Optional[Any] = ..., stop: Optional[Any] = ...,
            step: Optional[Any] = ..., dtype: Optional[Any] = ...,
            copy: bool = ..., name: Optional[Any] = ...,
            fastpath: Optional[Any] = ...) -> Any:
        ...

    @classmethod
    def from_range(
            cls, data: Any, name: Optional[Any] = ...,
            dtype: Optional[Any] = ...) -> Any:
        ...

    def __reduce__(self) -> Any:
        ...

    def start(self) -> Any:
        ...

    def stop(self) -> Any:
        ...

    def step(self) -> Any:
        ...

    @property
    def nbytes(self) -> Any:
        ...

    def memory_usage(self, deep: bool = ...) -> Any:
        ...

    def dtype(self) -> Any:
        ...

    @property
    def is_monotonic_increasing(self) -> Any:
        ...

    @property
    def is_monotonic_decreasing(self) -> Any:
        ...

    def __contains__(self, key: Union[int, np.integer]) -> bool:
        ...

    def get_loc(
            self, key: Any, method: Optional[Any] = ...,
            tolerance: Optional[Any] = ...) -> Any:
        ...

    def tolist(self) -> Any:
        ...

    def copy(
            self, name: Optional[Any] = ..., deep: bool = ...,
            dtype: Optional[Any] = ..., **kwargs: Any) -> Any:
        ...

    def min(
            self, axis: Optional[Any] = ..., skipna: bool = ..., *args: Any,
            **kwargs: Any) -> Any:
        ...

    def max(
            self, axis: Optional[Any] = ..., skipna: bool = ..., *args: Any,
            **kwargs: Any) -> Any:
        ...

    def argsort(self, *args: Any, **kwargs: Any) -> Any:
        ...

    def equals(self, other: Any) -> Any:
        ...

    def __len__(self) -> Any:
        ...

    @property
    def size(self) -> Any:
        ...

    def __getitem__(self, key: Any) -> Any:
        ...

    def __floordiv__(self, other: Any) -> Any:
        ...

    def all(self) -> bool:
        ...

    def any(self) -> bool:
        ...
