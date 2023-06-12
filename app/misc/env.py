import os
from typing import Literal


EnvPath = Literal[
    "CONFIG_PATH",
]
EnvStr = Literal[
    "API_SERVER_HOST",
    "APP_SECRET",
    "LOGIN_DB_DIALECT",
    "LOGIN_DB_HOST",
    "LOGIN_DB_NAME",
    "LOGIN_DB_PASSWORD",
    "LOGIN_DB_SCHEMA",
    "LOGIN_DB_USERNAME",
    "OPENCAGE_API",
]
EnvInt = Literal[
    "API_SERVER_PORT",
    "LOGIN_DB_PORT",
]


def _envload(key: str, default: str | None) -> str:
    res = os.environ.get(key)
    if res is not None:
        return res
    if default is not None:
        return default
    raise ValueError(f"env {key} must be set!")


def envload_str(key: EnvStr, *, default: str | None = None) -> str:
    return _envload(key, default)


def envload_path(key: EnvPath, *, default: str | None = None) -> str:
    return _envload(key, default)


def envload_int(key: EnvInt, *, default: int | None = None) -> int:
    return int(_envload(key, f"{default}"))
