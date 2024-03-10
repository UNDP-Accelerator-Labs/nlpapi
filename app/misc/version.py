import subprocess
from typing import Literal

from app.misc.io import open_read
from app.misc.util import get_time_str


VERSION_NAME: str | None = None
VERSION_HASH: str | None = None
VERSION_DATE: str | None = None


def simple_call(cmd: list[str]) -> str | None:
    try:
        return subprocess.check_output(
            cmd, stderr=subprocess.STDOUT).decode("utf-8")
    except subprocess.CalledProcessError:
        return None


VersionResult = Literal["name", "hash", "date"]


def get_version(version_result: VersionResult) -> str:
    global VERSION_NAME  # pylint: disable=global-statement
    global VERSION_HASH  # pylint: disable=global-statement
    global VERSION_DATE  # pylint: disable=global-statement

    if VERSION_NAME is None or VERSION_HASH is None or VERSION_DATE is None:
        VERSION_NAME = simple_call(["make", "-s", "name"])
        if VERSION_NAME is None:
            with open_read("version.txt", text=True) as fin:
                VERSION_NAME = fin.readline().strip()
                VERSION_HASH = fin.readline().strip()
                VERSION_DATE = fin.readline().strip()
        else:
            VERSION_NAME = f"LOCAL {VERSION_NAME}".strip()
            VERSION_HASH = simple_call(["make", "-s", "commit"])
            if VERSION_HASH is None:
                VERSION_HASH = "ERROR"
            else:
                VERSION_HASH = VERSION_HASH.strip()
            VERSION_DATE = get_time_str()
    if version_result == "name":
        return VERSION_NAME
    if version_result == "hash":
        return VERSION_HASH
    if version_result == "date":
        return VERSION_DATE
    raise ValueError(f"invalid version result: {version_result}")
