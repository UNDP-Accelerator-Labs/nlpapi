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
"""I/O helper functions that handle a slow disk (or network disk) gracefully.
"""
import contextlib
import errno
import io
import os
import shutil
import tempfile
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from typing import Any, cast, IO, Literal, overload


MAIN_LOCK = threading.RLock()
"""Lock for coordinating the wait on start when the (network) disk is not
ready yet. Network disks can take a bit to get ready after a container is
started."""
STALE_FILE_RETRIES: list[float] = [0.1, 0.2, 0.5, 0.8, 1, 1.2, 1.5, 2, 3, 5]
"""Wait times for retrying reads on stale files."""
TMP_POSTFIX = ".~tmp"
"""Postfix for temporary files."""


def when_ready(fun: Callable[[], None]) -> None:
    """
    Executes an I/O operation, retrying if the disk is not ready. After 120
    retries (~2min) the function gives up and lets the error go through.

    Args:
        fun (Callable[[], None]): The I/O operation.
    """
    with MAIN_LOCK:
        counter = 0
        while True:
            try:
                fun()
                return
            except OSError as ose:
                if counter < 120 and ose.errno in (errno.EAGAIN, errno.EBUSY):
                    time.sleep(1.0)
                    counter += 1
                    continue
                raise ose


def fastrename(src: str, dst: str) -> None:
    """
    Moves a file or folder. Source and destination cannot be the same.

    Args:
        src (str): The source file or folder.
        dst (str): The destination file or folder.
    """
    src = os.path.abspath(src)
    dst = os.path.abspath(dst)
    if src == dst:
        raise ValueError(f"{src} == {dst}")
    if not os.path.exists(src):
        raise FileNotFoundError(f"{src} does not exist!")
    try:
        when_ready(lambda: os.rename(src, dst))
        if not src.endswith(TMP_POSTFIX):
            print(f"move {src} to {dst}")
    except OSError:
        for file_name in listdir(src):
            try:
                shutil.move(os.path.join(src, file_name), dst)
            except shutil.Error as err:
                dest_file = os.path.join(dst, file_name)
                err_msg = f"{err}".lower()
                if "destination path" in err_msg and \
                        "already exists" in err_msg:
                    raise err
                remove_file(dest_file)
                shutil.move(os.path.join(src, file_name), dst)


def copy_file(from_file: str, to_file: str) -> None:
    """
    Copies a file to a new destination.

    Args:
        from_file (str): The source file.
        to_file (str): The destination file.
    """
    shutil.copy(from_file, to_file)


def normalize_folder(folder: str) -> str:
    """
    Makes the path absolute and ensures that the folder exists.

    Args:
        folder (str): The folder.

    Returns:
        str: The absolute path.
    """
    res = os.path.abspath(folder)
    when_ready(lambda: os.makedirs(res, mode=0o777, exist_ok=True))
    if not os.path.isdir(res):
        raise ValueError(f"{folder} must be a folder")
    return res


def normalize_file(fname: str) -> str:
    """
    Makes the path absolute and ensures that the parent folder exists.

    Args:
        fname (str): The file.

    Returns:
        str: The absolute path.
    """
    res = os.path.abspath(fname)
    normalize_folder(os.path.dirname(res))
    return res


def get_mode(base: str, text: bool) -> str:
    """
    Creates a mode string for the `open` function.

    Args:
        base (str): The base mode string.
        text (bool): Whether it is a text file.

    Returns:
        str: The mode string.
    """
    return f"{base}{'' if text else 'b'}"


def is_empty_file(fin: IO[Any]) -> bool:
    """
    Cheecks whether the given file is empty.

    Args:
        fin (IO[Any]): The file handle.

    Returns:
        bool: True, if the file is empty.
    """
    pos = fin.seek(0, io.SEEK_CUR)
    size = fin.seek(0, io.SEEK_END) - pos
    fin.seek(pos, io.SEEK_SET)
    return size <= 0


@overload
def ensure_folder(folder: str) -> str:
    ...


@overload
def ensure_folder(folder: None) -> None:
    ...


def ensure_folder(folder: str | None) -> str | None:
    """
    Ensures that the given folder exists.

    Args:
        folder (str | None): The folder name or None.

    Returns:
        str | None: The folder name or None.
    """
    if folder is not None and not os.path.exists(folder):
        a_folder: str = folder
        when_ready(lambda: os.makedirs(a_folder, mode=0o777, exist_ok=True))
    return folder


def get_tmp(basefile: str) -> str:
    """
    Determines the folder where temporary files can be stored depending on a
    given base file.

    Args:
        basefile (str): The base file.

    Returns:
        str: The folder where temporary files can be stored.
    """
    return ensure_folder(os.path.dirname(basefile))


@overload
def open_read(filename: str, *, text: Literal[True]) -> IO[str]:
    ...


@overload
def open_read(filename: str, *, text: Literal[False]) -> IO[bytes]:
    ...


# FIXME: make downstream users with use fixed text literals
@overload
def open_read(filename: str, *, text: bool) -> IO[Any]:
    ...


def open_read(filename: str, *, text: bool) -> IO[Any]:
    """
    Opens a file for reading.

    Args:
        filename (str): The file name.
        text (bool): Whether the file should be opened in text mode.

    Returns:
        IO[Any]: The file handle.
    """

    def actual_read() -> IO[Any]:
        return cast(IO[Any], open(  # pylint: disable=consider-using-with
            filename,
            get_mode("r", text),
            encoding=("utf-8" if text else None)))

    ix = 0
    res = None
    while True:
        try:
            # FIXME: yield instead of return
            res = actual_read()
            if is_empty_file(res):
                if ix >= len(STALE_FILE_RETRIES):
                    return res
                res.close()
                time.sleep(STALE_FILE_RETRIES[ix])
                ix += 1
                continue
            return res
        except OSError as os_err:
            if res is not None:
                res.close()
            if ix >= len(STALE_FILE_RETRIES) or os_err.errno != errno.ESTALE:
                raise os_err
            time.sleep(STALE_FILE_RETRIES[ix])
            ix += 1


@overload
def open_append(
        filename: str,
        *,
        text: Literal[True],
        **kwargs: Any) -> IO[str]:
    ...


@overload
def open_append(
        filename: str,
        *,
        text: Literal[False],
        **kwargs: Any) -> IO[bytes]:
    ...


# FIXME: make downstream users with use fixed text literals
@overload
def open_append(
        filename: str,
        *,
        text: bool,
        **kwargs: Any) -> IO[Any]:
    ...


def open_append(
        filename: str,
        *,
        text: bool,
        **kwargs: Any) -> IO[Any]:
    """
    Opens a file for appending.

    Args:
        filename (str): The file name.
        text (bool): Whether the file should be opened in text mode.
        **kwargs (Any): Additional arguments provided to the underlying open
            call.

    Returns:
        IO[Any]: The file handle.
    """
    return cast(IO[Any], open(  # pylint: disable=consider-using-with
        filename,
        get_mode("a", text),
        encoding=("utf-8" if text else None),
        **kwargs))


@contextlib.contextmanager
def open_write(filename: str, *, text: bool) -> Iterator[IO[Any]]:
    """
    Opens a file for writing. After writing to the file handle the content of
    the original file is replaced in an atomic operation. Readers of the file
    will never see the truncated state or partial writes.

    Args:
        filename (str): The file name.
        text (bool): Whether the file should be opened in text mode.

    Yields:
        IO[Any]: The file handle.
    """
    filename = normalize_file(filename)

    mode = get_mode("w", text)
    tname = None
    tfd = None
    sfile: IO[Any] | None = None
    writeback = False
    try:
        tfd, tname = tempfile.mkstemp(
            dir=get_tmp(filename),
            suffix=TMP_POSTFIX)
        sfile = cast(IO[Any], io.FileIO(tfd, mode, closefd=True))
        if text:
            sfile = cast(IO[Any], io.TextIOWrapper(
                sfile, encoding="utf-8", line_buffering=True))
        yield sfile
        sfile.flush()
        os.fsync(tfd)
        writeback = True
    finally:
        if sfile is not None:
            sfile.close()  # closes the temporary file descriptor
        elif tfd is not None:
            os.close(tfd)  # closes the actual temporary file descriptor
        if tname is not None:
            if writeback:
                fastrename(tname, filename)
            else:
                remove_file(tname)


@contextlib.contextmanager
def named_write(filename: str) -> Iterator[str]:
    """
    Provides a safe file name for writing. After writing to the provided file
    the content is moved over to the original file overwriting it in an atomic
    operation. Readers of the original file will never see partial writes.

    Args:
        filename (str): The original file name.

    Yields:
        str: The file name to use instead.
    """
    filename = normalize_file(filename)

    tname = None
    writeback = False
    try:
        tfd, tname = tempfile.mkstemp(
            dir=get_tmp(filename),
            suffix=TMP_POSTFIX)
        os.close(tfd)
        yield tname
        writeback = True
    finally:
        if tname is not None:
            if writeback:
                fastrename(tname, filename)
            else:
                remove_file(tname)


def remove_file(fname: str) -> None:
    """
    Removes a file even if it doesn't exist.

    Args:
        fname (str): The file name.
    """
    try:
        os.remove(fname)
    except FileNotFoundError:
        pass


def get_subfolders(path: str) -> list[str]:
    """
    Returns all subfolders of the given path. The function only returns direct
    children.

    Args:
        path (str): The path.

    Returns:
        list[str]: The subfolders.
    """
    return sorted((fobj.name for fobj in os.scandir(path) if fobj.is_dir()))


def get_files(path: str, ext: str) -> list[str]:
    """
    Returns all files in a given path. Only direct children are returned.

    Args:
        path (str): The path.
        ext (str): The extension to filter the results by.

    Returns:
        list[str]: The list of files in the folder.
    """
    return sorted((
        fobj.name
        for fobj in os.scandir(path)
        if fobj.is_file() and fobj.name.endswith(ext)
    ))


def get_folder(path: str, ext: str) -> Iterable[tuple[str, bool]]:
    """
    Returns all children of the given path.

    Args:
        path (str): The path.
        ext (str): The extension to filter by.

    Yields:
        tuple[str, bool]: The object name and whether it is a folder.
    """
    for fobj in sorted(os.scandir(path), key=lambda fobj: fobj.name):
        if fobj.is_dir():
            yield fobj.name, True
        elif fobj.is_file() and fobj.name.endswith(ext):
            yield fobj.name, False


def listdir(path: str) -> list[str]:
    """
    Lists a directory.

    Args:
        path (str): The path.

    Returns:
        list[str]: All direct children of the path.
    """
    return sorted(os.listdir(path))
