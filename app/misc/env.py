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
"""Handling environment variables."""
import os
from typing import Literal

from scattermind.system.util import to_bool


EnvPath = Literal[
    "CONFIG_PATH",
    "GRAPH_PATH",
    "SMIND_CFG",
    "UI_PATH",
]
"""Environment variables representing a file path or folder."""
EnvStr = Literal[
    "APP_SECRET",
    "BLOGS_DB_DIALECT",
    "BLOGS_DB_HOST",
    "BLOGS_DB_NAMES",
    "BLOGS_DB_PASSWORD",
    "BLOGS_DB_SCHEMA",
    "BLOGS_DB_USERNAME",
    "FORCE_USER",
    "HOST",
    "LOGIN_DB_DIALECT",
    "LOGIN_DB_HOST",
    "LOGIN_DB_NAME_PLATFORMS",
    "LOGIN_DB_NAME",
    "LOGIN_DB_PASSWORD",
    "LOGIN_DB_SCHEMA_PLATFORM",
    "LOGIN_DB_SCHEMA",
    "LOGIN_DB_USERNAME",
    "OPENCAGE_API",
    "QDRANT__SERVICE__API_KEY",
    "QDRANT__TELEMETRY_DISABLED",
    "QDRANT_HOST",
    "TANUKI",
    "WRITE_TOKEN",
]
"""Environment variables representing a string."""
EnvInt = Literal[
    "BLOGS_DB_PORT",
    "LOGIN_DB_PORT",
    "PORT",
    "QDRANT_GRPC_PORT",
    "QDRANT_REST_PORT",
]
"""Environment variables representing an integer."""
EnvBool = Literal[
    "NO_QDRANT",
    "HAS_LLAMA",
]
"""Environment variables representing a boolean value (true, false, 0, 1)."""


def _envload(key: str, default: str | None) -> str:
    res = os.environ.get(key)
    if res is not None:
        return res
    if default is not None:
        return default
    raise ValueError(f"env {key} must be set!")


def envload_str(key: EnvStr, *, default: str | None = None) -> str:
    """
    Loads a string environment variable.

    Args:
        key (EnvStr): The variable name.
        default (str | None, optional): The default value. If None, the
            environment variable is mandatory. Defaults to None.

    Returns:
        str: The value.
    """
    return _envload(key, default)


def envload_path(key: EnvPath, *, default: str | None = None) -> str:
    """
    Loads a path or folder environment variable.

    Args:
        key (EnvPath): The variable name.
        default (str | None, optional): The default value. If None, the
            environment variable is mandatory. Defaults to None.

    Returns:
        str: The value.
    """
    return _envload(key, default)


def envload_int(key: EnvInt, *, default: int | None = None) -> int:
    """
    Loads an integer environment variable.

    Args:
        key (EnvInt): The variable name.
        default (int | None, optional): The default value. If None, the
            environment variable is mandatory. Defaults to None.

    Returns:
        int: The value.
    """
    return int(_envload(key, f"{default}"))


def envload_bool(key: EnvBool, *, default: bool | None = None) -> bool:
    """
    Loads a boolean environment variable (0, 1, true, false).

    Args:
        key (EnvBool): The variable name.
        default (bool | None, optional): The default value. If None, the
            environment variable is mandatory. Defaults to None.

    Returns:
        bool: The value.
    """
    return to_bool(_envload(key, f"{default}"))
