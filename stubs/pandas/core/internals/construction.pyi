# Stubs for pandas.core.internals.construction (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.
# pylint: disable=unused-argument,redefined-outer-name,invalid-name
# pylint: disable=relative-beyond-top-level,arguments-differ
# pylint: disable=no-member,too-few-public-methods,keyword-arg-before-vararg
# pylint: disable=super-init-not-called,abstract-method,redefined-builtin
# pylint: disable=unused-import,useless-import-alias,signature-differs
# pylint: disable=blacklisted-name

from typing import Any, Optional


def arrays_to_mgr(
        arrays: Any, arr_names: Any, index: Any, columns: Any,
        dtype: Optional[Any] = ...) -> Any:
    ...


def masked_rec_array_to_mgr(
        data: Any, index: Any, columns: Any, dtype: Any, copy: Any) -> Any:
    ...


def init_ndarray(
        values: Any, index: Any, columns: Any, dtype: Optional[Any] = ...,
        copy: bool = ...) -> Any:
    ...


def init_dict(
        data: Any, index: Any, columns: Any,
        dtype: Optional[Any] = ...) -> Any:
    ...


def prep_ndarray(values: Any, copy: bool = ...) -> Any:
    ...


def extract_index(data: Any) -> Any:
    ...


def reorder_arrays(arrays: Any, arr_columns: Any, columns: Any) -> Any:
    ...


def get_names_from_index(data: Any) -> Any:
    ...


def to_arrays(
        data: Any, columns: Any, coerce_float: bool = ...,
        dtype: Optional[Any] = ...) -> Any:
    ...


def sanitize_index(data: Any, index: Any, copy: bool = ...) -> Any:
    ...


def sanitize_array(
        data: Any, index: Any, dtype: Optional[Any] = ...,
        copy: bool = ..., raise_cast_failure: bool = ...) -> Any:
    ...
