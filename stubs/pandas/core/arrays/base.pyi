# Stubs for pandas.core.arrays.base (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.
# pylint: disable=unused-argument,redefined-outer-name,invalid-name
# pylint: disable=relative-beyond-top-level,arguments-differ
# pylint: disable=no-member,too-few-public-methods,keyword-arg-before-vararg
# pylint: disable=super-init-not-called,abstract-method,redefined-builtin

from typing import Any, Dict, Optional, Sequence, Tuple, Union

import numpy as np
from pandas._typing import ArrayLike
from pandas.core.dtypes.dtypes import ExtensionDtype
from pandas.core.dtypes.generic import ABCExtensionArray


_extension_array_shared_docs: Dict[str, str] = ...


class ExtensionArray:
    def __getitem__(self, item: Any) -> None:
        ...

    def __setitem__(self, key: Union[int, np.ndarray], value: Any) -> None:
        ...

    def __len__(self) -> int:
        ...

    def __iter__(self) -> None:
        ...

    @property
    def dtype(self) -> ExtensionDtype:
        ...

    @property
    def shape(self) -> Tuple[int, ...]:
        ...

    @property
    def ndim(self) -> int:
        ...

    @property
    def nbytes(self) -> int:
        ...

    def astype(self, dtype: Any, copy: bool = ...) -> Any:
        ...

    def isna(self) -> ArrayLike:
        ...

    def argsort(
            self, ascending: bool = ..., kind: str = ..., *args: Any,
            **kwargs: Any) -> Any:
        ...

    def fillna(
            self, value: Optional[Any] = ..., method: Optional[Any] = ...,
            limit: Optional[Any] = ...) -> Any:
        ...

    def dropna(self) -> Any:
        ...

    def shift(
            self, periods: int = ...,
            fill_value: object = ...) -> ABCExtensionArray:
        ...

    def unique(self) -> Any:
        ...

    def searchsorted(
            self, value: Any, side: str = ...,
            sorter: Optional[Any] = ...) -> Any:
        ...

    def factorize(
            self,
            na_sentinel: int = ...) -> Tuple[np.ndarray, ABCExtensionArray]:
        ...

    def repeat(self, repeats: Any, axis: Optional[Any] = ...) -> Any:
        ...

    def take(
            self, indices: Sequence[int], allow_fill: bool = ...,
            fill_value: Any = ...) -> ABCExtensionArray:
        ...

    def copy(self) -> ABCExtensionArray:
        ...

    def ravel(self, order: Any = ...) -> ABCExtensionArray:
        ...


class ExtensionOpsMixin:
    @classmethod
    def _add_arithmetic_ops(cls) -> Any:
        ...

    @classmethod
    def _add_comparison_ops(cls) -> Any:
        ...


class ExtensionScalarOpsMixin(ExtensionOpsMixin):
    @classmethod
    def _create_method(cls, op: Any, coerce_to_dtype: bool = True) -> Any:
        ...

    @classmethod
    def _create_arithmetic_method(cls, op: Any) -> Any:
        ...

    @classmethod
    def _create_comparison_method(cls, op: Any) -> Any:
        ...
