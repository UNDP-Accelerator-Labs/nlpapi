import subprocess

from app.misc.io import open_read


VERSION_NAME: str | None = None
VERSION_HASH: str | None = None


def simple_call(cmd: list[str]) -> str | None:
    try:
        return subprocess.check_output(
            cmd, stderr=subprocess.STDOUT).decode("utf-8")
    except subprocess.CalledProcessError:
        return None


def get_version(return_hash: bool) -> str:
    global VERSION_NAME  # pylint: disable=global-statement
    global VERSION_HASH  # pylint: disable=global-statement

    if VERSION_NAME is None or VERSION_HASH is None:
        VERSION_NAME = simple_call(["make", "-s", "name"])
        if VERSION_NAME is None:
            with open_read("version.txt", text=True) as fin:
                VERSION_NAME = fin.readline().strip()
                VERSION_HASH = fin.readline().strip()
        else:
            VERSION_NAME = f"LOCAL {VERSION_NAME}".strip()
            VERSION_HASH = simple_call(["make", "-s", "commit"])
            if VERSION_HASH is None:
                VERSION_HASH = "ERROR"
            else:
                VERSION_HASH = VERSION_HASH.strip()
    return VERSION_HASH if return_hash else VERSION_NAME
