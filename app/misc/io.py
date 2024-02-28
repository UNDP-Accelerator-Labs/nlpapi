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
STALE_FILE_RETRIES: list[float] = [0.1, 0.2, 0.5, 0.8, 1, 1.2, 1.5, 2, 3, 5]
TMP_POSTFIX = ".~tmp"


def when_ready(fun: Callable[[], None]) -> None:
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
    shutil.copy(from_file, to_file)


def normalize_folder(folder: str) -> str:
    res = os.path.abspath(folder)
    when_ready(lambda: os.makedirs(res, mode=0o777, exist_ok=True))
    if not os.path.isdir(res):
        raise ValueError(f"{folder} must be a folder")
    return res


def normalize_file(fname: str) -> str:
    res = os.path.abspath(fname)
    normalize_folder(os.path.dirname(res))
    return res


def get_mode(base: str, text: bool) -> str:
    return f"{base}{'' if text else 'b'}"


def is_empty_file(fin: IO[Any]) -> bool:
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
    if folder is not None and not os.path.exists(folder):
        a_folder: str = folder
        when_ready(lambda: os.makedirs(a_folder, mode=0o777, exist_ok=True))
    return folder


def get_tmp(basefile: str) -> str:
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
    return cast(IO[Any], open(  # pylint: disable=consider-using-with
        filename,
        get_mode("a", text),
        encoding=("utf-8" if text else None),
        **kwargs))


@contextlib.contextmanager
def open_write(filename: str, *, text: bool) -> Iterator[IO[Any]]:
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
    try:
        os.remove(fname)
    except FileNotFoundError:
        pass


def get_subfolders(path: str) -> list[str]:
    return sorted((fobj.name for fobj in os.scandir(path) if fobj.is_dir()))


def get_files(path: str, ext: str) -> list[str]:
    return sorted((
        fobj.name
        for fobj in os.scandir(path)
        if fobj.is_file() and fobj.name.endswith(ext)
    ))


def get_folder(path: str, ext: str) -> Iterable[tuple[str, bool]]:
    for fobj in sorted(os.scandir(path), key=lambda fobj: fobj.name):
        if fobj.is_dir():
            yield fobj.name, True
        elif fobj.is_file() and fobj.name.endswith(ext):
            yield fobj.name, False


def listdir(path: str) -> list[str]:
    return sorted(os.listdir(path))
