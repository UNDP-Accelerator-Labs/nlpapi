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
"""General utility functions."""
import contextlib
import hashlib
import inspect
import json
import os
import re
import string
import threading
import time
import uuid
from collections.abc import Callable, Iterable, Iterator
from datetime import datetime, timezone
from typing import (
    Any,
    get_args,
    IO,
    Literal,
    NoReturn,
    ParamSpec,
    TypeAlias,
    TypeVar,
)

import numpy as np
import pandas as pd
import redis
import sqlalchemy as sa
import torch
from qdrant_client.http.exceptions import ResponseHandlingException

from app.misc.io import open_read


ET = TypeVar('ET')
CT = TypeVar('CT')
RT = TypeVar('RT')
AT = TypeVar('AT')
VT = TypeVar('VT')
DT = TypeVar('DT', bound=pd.DataFrame | pd.Series)


NL = "\n"


TEST_SALT_LOCK = threading.RLock()
"""Lock for salt generation of unit tests."""
TEST_SALT: dict[str, str] = {}
"""Cache for unit test salts."""


DocStatus: TypeAlias = Literal["public", "preview"]
"""The status of a document. `public` means anybody can access the document and
`preview` means only logged in users can access the document."""
DOC_STATUS: tuple[DocStatus] = get_args(DocStatus)
"""The status of a document. `public` means anybody can access the document and
`preview` means only logged in users can access the document."""


CHUNK_SIZE = 600
"""Chunk size for vector database embeddings."""
SMALL_CHUNK_SIZE = 150
"""Chunk size for small hit snippets."""
TITLE_CHUNK_SIZE = 60
"""Chunk size for titles."""
CHUNK_PADDING = 20
"""General padding of embedding chunks."""
DEFAULT_HIT_LIMIT = 1
"""Default hit limit. At the moment only the top hit is returned by default."""


def is_test() -> bool:
    """
    Whether the program is run in a test environment.

    Returns:
        bool: Whether we are executing a unit test.
    """
    test_id = os.getenv("PYTEST_CURRENT_TEST")
    return test_id is not None


def get_test_salt() -> str | None:
    """
    Get the salt for the current unit test.

    Returns:
        str | None: The salt or None if we are not currently running a unit
            test.
    """
    test_id = os.getenv("PYTEST_CURRENT_TEST")
    if test_id is None:
        return None
    res = TEST_SALT.get(test_id)
    if res is None:
        with TEST_SALT_LOCK:
            res = TEST_SALT.get(test_id)
            if res is None:
                res = f"salt:{uuid.uuid4().hex}"
                TEST_SALT[test_id] = res
    return res


def get_text_hash(text: str) -> str:
    """
    Get the hash of the given text. The length of the hash in characters is
    provided by `text_hash_size`.

    Args:
        text (str): The text.

    Returns:
        str: The hash.
    """
    blake = hashlib.blake2b(digest_size=32)
    blake.update(text.encode("utf-8"))
    return blake.hexdigest()


def text_hash_size() -> int:
    """
    The size of the hash produced by `get_text_hash`.

    Returns:
        int: The number of characters in the hash.
    """
    return 64


def get_short_hash(text: str) -> str:
    """
    Computes a short hash for the given text. The length of the hash in
    characters is provided by `short_hash_size`.

    Args:
        text (str): The text.

    Returns:
        str: The hash.
    """
    blake = hashlib.blake2b(digest_size=4)
    blake.update(text.encode("utf-8"))
    return blake.hexdigest()


def short_hash_size() -> int:
    """
    The size of the short hash produced by `get_short_hash`.

    Returns:
        int: The number of characters in the hash.
    """
    return 8


BUFF_SIZE = 65536  # 64KiB
"""Buffer size of file operations. Namely hashing."""


def get_file_hash(fname: str) -> str:
    """
    Computes the hash of the given file. The length of the hash in characters
    is provided by `file_hash_size`.

    Args:
        fname (str): The file name.

    Returns:
        str: The hash of the file's contents.
    """
    blake = hashlib.blake2b(digest_size=32)
    with open_read(fname, text=False) as fin:
        while True:
            buff = fin.read(BUFF_SIZE)
            if not buff:
                break
            blake.update(buff)
    return blake.hexdigest()


def file_hash_size() -> int:
    """
    The size of the hash produced by `get_file_hash`.

    Returns:
        int: The number of characters in the hash.
    """
    return 64


def is_hex(text: str) -> bool:
    """
    Whether a given text denotes a hex number.

    Args:
        text (str): The text.

    Returns:
        bool: True, if it is a hex number.
    """
    hex_digits = set(string.hexdigits)
    return all(char in hex_digits for char in text)


def as_df(series: pd.Series) -> pd.DataFrame:
    """
    Convert a series into a dataframe.

    Args:
        series (pd.Series): The series.

    Returns:
        pd.DataFrame: The one row dataframe.
    """
    return series.to_frame().T


def fillnonnum(df: DT, val: float) -> DT:
    """
    Fill in all non-numerical values (Inf or NaN) with the given number.

    Args:
        df (DT): The dataframe.
        val (float): The value to fill in.

    Returns:
        DT: The new dataframe.
    """
    return df.replace([-np.inf, np.inf], np.nan).fillna(val)  # type: ignore


def only(arr: list[RT]) -> RT:
    """
    Returns the only value of the given array.

    Args:
        arr (list[RT]): The array.

    Raises:
        ValueError: If the array length is not exactly 1.

    Returns:
        RT: The only value in the array.
    """
    if len(arr) != 1:
        raise ValueError(f"array must have exactly one element: {arr}")
    return arr[0]


# time units for logging request durations
ELAPSED_UNITS: list[tuple[int, str]] = [
    (1, "s"),
    (60, "m"),
    (60*60, "h"),
    (60*60*24, "d"),
]
"""Units for pretty time delta formatting."""


def elapsed_time_string(elapsed: float) -> str:
    """
    Convert elapsed time into a readable string.

    Args:
        elapsed (float): The elapsed time in seconds.

    Returns:
        str: A human readable string.
    """
    cur = ""
    for (conv, unit) in ELAPSED_UNITS:
        if elapsed / conv >= 1 or not cur:
            cur = f"{elapsed / conv:8.3f}{unit}"
        else:
            break
    return cur


def to_bool(value: bool | float | int | str) -> bool:
    """
    Interprets the given value as boolean.

    Args:
        value (bool | float | int | str): The value.

    Raises:
        ValueError: If the value cannot be converted to a boolean.

    Returns:
        bool: The boolean value.
    """
    value = f"{value}".lower()
    if value in ("true", "yes", "y"):
        return True
    if value in ("false", "no", "n"):
        return False
    try:
        return bool(int(float(value)))
    except ValueError:
        pass
    raise ValueError(f"{value} cannot be interpreted as bool")


def to_list(value: Any) -> list[Any]:
    """
    Ensures that the provided value is a list.

    Args:
        value (Any): The value.

    Raises:
        ValueError: If it is not a list.

    Returns:
        list[Any]: The value properly typed as list.
    """
    if not isinstance(value, list):
        raise ValueError(f"{value} is not a list")
    return value


def maybe_list(value: Any) -> list[Any] | None:
    """
    Ensures that the provided value is a list or None.

    Args:
        value (Any): The value.

    Returns:
        list[Any] | None: The value properly typed as list or None.
    """
    if value is None:
        return None
    return to_list(value)


def is_int(value: Any) -> bool:
    """
    Determines whether the given value is / can be converted to an integer.

    Args:
        value (Any): The value.

    Returns:
        bool: Whether the value can be converted to an integer.
    """
    try:
        int(value)
        return True
    except ValueError:
        return False


def is_float(value: Any) -> bool:
    """
    Determines whether the given value is / can be converted to a float.

    Args:
        value (Any): The value.

    Returns:
        bool: Whether the value can be converted to a float.
    """
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def maybe_float(value: Any) -> float | None:
    """
    Converts the value to float or leaves it as None.

    Args:
        value (Any): The value.

    Returns:
        float | None: The float value if it was non-None otherwise None.
    """
    if value is None:
        return None
    return float(value)


def maybe_int(value: Any) -> int | None:
    """
    Converts the value to an integer or leaves it as None.

    Args:
        value (Any): The value.

    Returns:
        int | None: The integer value if it was non-None otherwise None.
    """
    if value is None:
        return None
    return int(value)


def is_json(value: str) -> bool:
    """
    Checks whether a string is a JSON.

    Args:
        value (str): The string.

    Returns:
        bool: True, if the string can be interpreted as JSON.
    """
    try:
        json.loads(value)
    except json.JSONDecodeError:
        return False
    return True


def get_json_error_str(err: json.JSONDecodeError) -> str:
    """
    Computes the error location inside the JSON document and provides a human
    readable output.

    Args:
        err (json.JSONDecodeError): The JSON error.

    Returns:
        str: Human readable error description.
    """
    ctx = 2
    max_length = 80
    lineno = err.lineno - 1
    colno = err.colno - 1
    all_lines = []

    def add_line(ix: int, line: str) -> None:
        if ix < lineno - ctx:
            return
        if ix > lineno + ctx:
            return
        all_lines.append(line)

    def add_insert(insertline: int | None) -> int | None:
        if insertline is None:
            return None
        if insertline <= max_length:
            all_lines.append(f"{' ' * insertline}^")
            return None
        return insertline - max_length

    for ix, line in enumerate(err.doc.splitlines()):
        insertline = None
        if ix == lineno:
            insertline = colno
        while len(line) > max_length:
            add_line(ix, line[:max_length])
            line = line[max_length:]
            insertline = add_insert(insertline)
        add_line(ix, line)
        add_insert(insertline)

    line_str = "\n".join(all_lines)
    return f"JSON parse error ({err.lineno}:{err.colno}):\n{line_str}"


def report_json_error(err: json.JSONDecodeError) -> NoReturn:
    """
    Reports a JSON error.

    Args:
        err (json.JSONDecodeError): The original JSON error.

    Raises:
        ValueError: The well formatted JSON error.
    """
    raise ValueError(get_json_error_str(err)) from err


def json_maybe_read(data: str) -> Any | None:
    """
    Read a JSON or return None.

    Args:
        data (str): Text that might contain a JSON.

    Returns:
        Any | None: Either the JSON or None.
    """
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return None


def json_load(fin: IO[str]) -> Any:
    """
    Loads a JSON from a file handle.

    Args:
        fin (IO[str]): The file handle.

    Returns:
        Any: The JSON.
    """
    try:
        return json.load(fin)
    except json.JSONDecodeError as e:
        report_json_error(e)


def json_dump(obj: Any, fout: IO[str]) -> None:
    """
    Write a JSON to a file.

    Args:
        obj (Any): The JSON.
        fout (IO[str]): The file handle.
    """
    print(json_pretty(obj), file=fout)


def json_pretty(obj: Any) -> str:
    """
    JSON format the input in a legible format.

    Args:
        obj (Any): The JSON object.

    Returns:
        str: The readable JSON string.
    """
    return json.dumps(obj, sort_keys=True, indent=2)


def json_compact_str(obj: Any) -> str:
    """
    JSON format the input in a compact format.

    Args:
        obj (Any): The JSON object.

    Returns:
        str: The compact JSON string.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        indent=None,
        separators=(',', ':'))


def json_read_str(data: str) -> Any:
    """
    Read a JSON from a string.

    Args:
        data (str): The string.

    Returns:
        Any: The JSON object.
    """
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        report_json_error(e)


def json_read(data: bytes) -> Any:
    """
    Read a JSON from bytes.

    Args:
        data (bytes): The bytes.

    Returns:
        Any: The JSON object.
    """
    try:
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as e:
        report_json_error(e)


def read_jsonl(fin: IO[str]) -> Iterable[Any]:
    """
    Read a JSONL formatted file. Each line in the file is one full JSON.

    Args:
        fin (IO[str]): The file handle.

    Yields:
        Any: JSON object.
    """
    for line in fin:
        line = line.rstrip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as e:
            report_json_error(e)


UNIX_EPOCH = pd.Timestamp("1970-01-01", tz="UTC")
"""The unix epoch reference timestamp."""


def from_timestamp(timestamp: float) -> pd.Timestamp:
    """
    Get a timestamp object from a unix timestamp.

    Args:
        timestamp (float): The unix timestamp.

    Returns:
        pd.Timestamp: The timestamp object.
    """
    return pd.to_datetime(timestamp, unit="s", utc=True)


def to_timestamp(ts: pd.Timestamp) -> float:
    """
    Convert a timestamp object into a unix timestamp.

    Args:
        ts (pd.Timestamp): The timestamp object.

    Returns:
        float: The unix timestamp.
    """
    return (ts - UNIX_EPOCH) / pd.Timedelta("1s")


def now_ts() -> pd.Timestamp:
    """
    Returns the current timestamp object.

    Returns:
        pd.Timestamp: The current time as timestamp object.
    """
    return pd.Timestamp("now", tz="UTC")


def now() -> datetime:
    """
    Computes the current time with UTC timezone.

    Returns:
        datetime: A timezone aware instance of now.
    """
    return datetime.now(timezone.utc).astimezone()


def parse_time_str(time_str: str) -> datetime:
    """
    Parses an ISO formatted string representing a timestamp.

    Args:
        time_str (str): The string.

    Returns:
        datetime: The timestamp.
    """
    return datetime.fromisoformat(time_str)


def fmt_time(when: datetime) -> str:
    """
    Formats a timestamp as ISO formatted string.

    Args:
        when (datetime): The timestamp.

    Returns:
        str: The formatted string.
    """
    return when.isoformat()


def get_time_str() -> str:
    """
    Get the current time as ISO formatted string.

    Returns:
        str: The current time in ISO format.
    """
    return fmt_time(now())


def get_function_info(*, clazz: type) -> tuple[str, int, str]:
    """
    Finds a calling method of the given class type and provides its stack
    information.

    Args:
        clazz (type): The class type.

    Returns:
        tuple[str, int, str]: The filename, line number, and function name.
    """
    stack = inspect.stack()

    def get_method(cur_clazz: type) -> tuple[str, int, str] | None:
        class_filename = inspect.getfile(cur_clazz)
        for level in stack:
            if os.path.samefile(level.filename, class_filename):
                return level.filename, level.lineno, level.function
        return None

    queue = [clazz]
    while queue:
        cur = queue.pop(0)
        res = get_method(cur)
        if res is not None:
            return res
        queue.extend(cur.__bases__)
    frame = stack[1]
    return frame.filename, frame.lineno, frame.function


def get_relative_function_info(
        depth: int) -> tuple[str, int, str, dict[str, Any]]:
    """
    Returns the stack information `depth` levels down.

    Args:
        depth (int): The depth of the stack to inspect.

    Returns:
        tuple[str, int, str, dict[str, Any]]: The filename, line number,
            function name, and local variables.
    """
    depth += 1
    stack = inspect.stack()
    if depth >= len(stack):
        return "unknown", -1, "unknown", {}
    frame = stack[depth]
    return frame.filename, frame.lineno, frame.function, frame.frame.f_locals


def identity(obj: RT) -> RT:
    """
    Returns the object itself.

    Args:
        obj (RT): The object.

    Returns:
        RT: The object.
    """
    return obj


def sigmoid(x: Any) -> Any:
    """
    Computes the logistic function.

    Args:
        x (Any): The input.

    Returns:
        Any: The output.
    """
    return np.exp(-np.logaddexp(0, -x))


NUMBER_PATTERN = re.compile(r"\d+")
"""Regex to look for numbers."""


def extract_list(
        arr: Iterable[str],
        prefix: str | None = None,
        postfix: str | None = None) -> Iterable[tuple[str, str]]:
    """
    Find strings with certain prefixes and postfixes in the given iterator.

    Args:
        arr (Iterable[str]): The input.
        prefix (str | None, optional): Optional prefix to filter by. Defaults
            to None.
        postfix (str | None, optional): Optional postfix to filter by. Defaults
            to None.

    Yields:
        tuple[str, str]: The full text of the hit and the part between the
            prefix and postfix.
    """
    if not arr:
        yield from []
        return

    for elem in arr:
        text = elem
        if prefix is not None:
            if not text.startswith(prefix):
                continue
            text = text[len(prefix):]
        if postfix is not None:
            if not text.endswith(postfix):
                continue
            text = text[:-len(postfix)]
        yield (elem, text)


def extract_number(
        arr: Iterable[str],
        prefix: str | None = None,
        postfix: str | None = None) -> Iterable[tuple[str, int]]:
    """
    Find numbers in strings.

    Args:
        arr (Iterable[str]): The iterator of strings.
        prefix (str | None, optional): The prefix to filter by. Defaults to
            None.
        postfix (str | None, optional): The postfix to filter by. Defaults to
            None.

    Yields:
        tuple[str, int]: The full text of the hit and the number between the
            prefix and postfix.
    """

    def get_num(text: str) -> int | None:
        match = re.search(NUMBER_PATTERN, text)
        if match is None:
            return None
        try:
            return int(match.group())
        except ValueError:
            return None

    for elem, text in extract_list(arr, prefix=prefix, postfix=postfix):
        num = get_num(text)
        if num is None:
            continue
        yield elem, num


def highest_number(
        arr: Iterable[str],
        prefix: str | None = None,
        postfix: str | None = None) -> tuple[str, int] | None:
    """
    Extracts the highest number in the given iterator.

    Args:
        arr (Iterable[str]): The strings.
        prefix (str | None, optional): The prefix to filter by. Defaults to
            None.
        postfix (str | None, optional): The postfix to filter by. Defaults to
            None.

    Returns:
        tuple[str, int] | None: The full text of the hit and the number between
            the prefix and the postfix. None if no valid row was found.
    """
    res = None
    res_num = 0
    for elem, num in extract_number(arr, prefix=prefix, postfix=postfix):
        if res is None or num > res_num:
            res = elem
            res_num = num
    return None if res is None else (res, res_num)


def retain_some(
        arr: Iterable[VT],
        count: int,
        *,
        key: Callable[[VT], Any],
        reverse: bool = False,
        keep_last: bool = True) -> tuple[list[VT], list[VT]]:
    """
    Filter an iterator to keep a certain number of elements.

    Args:
        arr (Iterable[VT]): The iterator.
        count (int): How many items to keep.
        key (Callable[[VT], Any]): Key generator to sort by.
        reverse (bool, optional): If True, the sort order is reversed. Defaults
            to False.
        keep_last (bool, optional): Guarantee to retain at least the last
            element. Defaults to True.

    Returns:
        tuple[list[VT], list[VT]]: The list of retained elements and elements
            to be deleted.
    """
    res: list[VT] = []
    to_delete: list[VT] = []
    if keep_last:
        for elem in arr:
            if len(res) <= count:
                res.append(elem)
                continue
            res.sort(key=key, reverse=reverse)
            to_delete.extend(res[:-count])
            res = res[-count:]
            res.append(elem)
    else:
        for elem in arr:
            res.append(elem)
            if len(res) < count:
                continue
            res.sort(key=key, reverse=reverse)
            to_delete.extend(res[:-count])
            res = res[-count:]
    res.sort(key=key, reverse=reverse)
    return res, to_delete


def safe_ravel(x: torch.Tensor) -> torch.Tensor:
    """
    Ensures that the input tensor is raveled properly.

    Args:
        x (torch.Tensor): The input tensor.

    Raises:
        ValueError: If the input tensore could not be interpreted as one
            dimensional.

    Returns:
        torch.Tensor: A one dimensional tensor.
    """
    if len(x.shape) == 1:
        return x
    shape = torch.Tensor(list(x.shape)).int()
    if torch.max(shape).item() != torch.prod(shape).item():
        raise ValueError(f"not safe to ravel shape {shape.tolist()}")
    return x.ravel()


def python_module() -> str:
    """
    Determines the module of the calling function.

    Raises:
        ValueError: If the module cannot be found.

    Returns:
        str: The module in dot notation (e.g., `path.to.my.module`)
    """
    stack = inspect.stack()
    module = inspect.getmodule(stack[1][0])
    if module is None:
        raise ValueError("module not found")
    res = module.__name__
    if res != "__main__":
        return res
    package = module.__package__
    if package is None:
        package = ""
    mfname = module.__file__
    if mfname is None:
        return package
    fname = os.path.basename(mfname)
    fname = fname.removesuffix(".py")
    if fname in ("__init__", "__main__"):
        return package
    return f"{package}.{fname}"


def parent_python_module(p_module: str) -> str:
    """
    Compute the parent module from a module name.

    Args:
        p_module (str): Module name in dot notation
            (e.g., `path.to.my.module`).

    Returns:
        str: The parent module (e.g., `path.to.my`).
    """
    dot_ix = p_module.rfind(".")
    if dot_ix < 0:
        return ""
    return p_module[:dot_ix]


def check_pid_exists(pid: int) -> bool:
    """
    Check whether a process with the given pid exists.

    Args:
        pid (int): The pid.

    Returns:
        bool: True, if a process exists.
    """
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def ideal_thread_count() -> int:
    """
    Determines the ideal thread count for the current processor.

    Returns:
        int: The number of threads to use.
    """
    res = os.cpu_count()
    if res is None:
        return 4
    return res


def escape(text: str, subs: dict[str, str]) -> str:
    """
    Escapes a text with the given substitutions.

    Args:
        text (str): The text.
        subs (dict[str, str]): The substitutions. Example:
            ```
            text=r"\\ \n \t"
            subs={"\n": "n", "\t": "b"}
            ==>r"\\\\ \\n \\b"
            ```

    Returns:
        str: The escaped text.
    """
    text = text.replace("\\", "\\\\")
    for key, repl in subs.items():
        text = text.replace(key, f"\\{repl}")
    return text


def unescape(text: str, subs: dict[str, str]) -> str:
    """
    Unescapes a text with the given substitutions.

    Args:
        text (str): The text.
        subs (dict[str, str]): The reverse substitution. Example:
            ```
            text=r"\\\\ \\n \\b"
            subs={"n": "\n", "b": "\t"}
            ===>r"\\ \n \t"
            ```

    Returns:
        str: The unescaped text.
    """
    res: list[str] = []
    in_escape = False
    for c in text:
        if in_escape:
            in_escape = False
            if c == "\\":
                res.append("\\")
                continue
            done = False
            for key, repl in subs.items():
                if c == key:
                    res.append(repl)
                    done = True
                    break
            if done:
                continue
        if c == "\\":
            in_escape = True
            continue
        res.append(c)
    return "".join(res)


def nbest(
        array: list[ET],
        key: Callable[[ET], float],
        *,
        count: int,
        is_bigger_better: bool) -> list[ET]:
    """
    Computes the `count` best elements in the list.

    Args:
        array (list[ET]): The element.
        key (Callable[[ET], float]): The comparison key.
        count (int): The number of results to return.
        is_bigger_better (bool): Whether bigger numbers are better.

    Returns:
        list[ET]: Up to `count` results.
    """
    arr = np.array([
        key(elem) if is_bigger_better else -key(elem)
        for elem in array
    ], dtype=np.float64)
    ind = np.argpartition(arr, -count)[-count:]
    return [
        array[ix]
        for ix in ind[np.argsort(arr[ind])[::-1]]
    ]


@contextlib.contextmanager
def progress(
        *,
        desc: str,
        total: int,
        show: bool) -> Iterator[Callable[[int], None]]:
    """
    Update a progress bar upon calling a progress function.

    Args:
        desc (str): The description.
        total (int): The total number of steps.
        show (bool): Whether to show the progress bar.

    Yields:
        Callable[[int], None]: Updates the progress steps by the
            provided number.
    """
    if not show:
        yield lambda _: None
        return
    # FIXME: add stubs
    from tqdm.auto import tqdm  # type: ignore

    with tqdm(desc=desc, total=total) as pbar:
        yield pbar.update


EXCEPTIONS: tuple[type[BaseException]] = (  # type: ignore
    ResponseHandlingException,
    sa.exc.OperationalError,
    ConnectionRefusedError,
    redis.exceptions.ConnectionError,
)
"""Connection issue type exceptions."""


P = ParamSpec("P")


def retry_err(
        fn: Callable[P, RT],
        *fn_args: P.args,
        **fn_kwargs: P.kwargs) -> RT:
    """
    Retry the given function call multiple times on connection errors.

    Args:
        fn (Callable[P, RT]): The function call.
        *fn_args (P.args): The positional arguments to the function.
        **fn_kwargs (P.kwargs): The keyword arguments to the function.

    Returns:
        RT: The return value of the called function.
    """
    return retry_err_config(fn, 3, 3.0, *fn_args, **fn_kwargs)


def retry_err_config(
        fn: Callable[P, RT],
        max_retry: int,
        sleep: float,
        *fn_args: P.args,
        **fn_kwargs: P.kwargs) -> RT:
    """
    Retry the given function call multiple times on connection errors.

    Args:
        fn (Callable[P, RT]): The function call.
        max_retry (int): Maximum number of retries.
        sleep (float): Time to sleep in seconds between retries.
        *fn_args (P.args): The positional arguments to the function.
        **fn_kwargs (P.kwargs): The keyword arguments to the function.

    Returns:
        RT: The return value of the called function.
    """
    error = 0
    while True:
        try:
            return fn(*fn_args, **fn_kwargs)
        except EXCEPTIONS:
            error += 1
            if error > max_retry:
                raise
            if sleep > 0.0:
                time.sleep(sleep)
