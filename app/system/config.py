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
"""The app configuration."""
import json
import os
from typing import cast, NoReturn, TYPE_CHECKING, TypedDict

from app.misc.env import envload_bool, envload_int, envload_path, envload_str
from app.misc.io import open_read, open_write


if TYPE_CHECKING:
    from app.system.db.db import DBConfig
    from app.system.smind.vec import VecDBConfig


Config = TypedDict('Config', {
    "db": 'DBConfig',
    "platforms": dict[str, 'DBConfig'],
    "blogs": dict[str, 'DBConfig'],
    "opencage": str,
    "appsecret": str,
    "vector": 'VecDBConfig | None',
    "smind": str,
    "graphs": str,
    "write_token": str,
    "tanuki": str,
})
"""The config object."""


CONFIG: Config | None = None
"""The cached config object."""
CONFIG_PATH: str | None = None
"""The cached config path."""


def get_config_path() -> str:
    """
    Reads the config path from the environment.

    Returns:
        str: The path.
    """
    global CONFIG_PATH  # pylint: disable=global-statement

    if CONFIG_PATH is None:
        CONFIG_PATH = envload_path("CONFIG_PATH", default="config.json")
    return CONFIG_PATH


def config_template() -> Config:
    """
    Create a config template.

    Returns:
        Config: The config template.
    """
    default_conn: 'DBConfig' = {
        "dialect": "postgresql",
        "host": "localhost",
        "port": 5432,
        "dbname": "INVALID",
        "schema": "public",
        "user": "INVALID",
        "passwd": "INVALID",
    }
    default_vec: 'VecDBConfig' = {
        "host": "qdrant-1",
        "port": 6333,
        "grpc": 6334,
        "token": "",
    }
    return {
        "db": default_conn.copy(),
        "platforms": {
            "login": default_conn.copy(),
            "sm": default_conn.copy(),
            "exp": default_conn.copy(),
            "ap": default_conn.copy(),
        },
        "blogs": {
            "blog": default_conn.copy(),
        },
        "opencage": "INVALID",
        "appsecret": "INVALID",
        "vector": default_vec.copy(),
        "smind": "smind-config.json",
        "graphs": "graphs/",
        "write_token": "INVALID",
        "tanuki": "INVALID",
    }


def create_config_and_err(config_path: str) -> NoReturn:
    """
    Creates a config template, writes it to the path and then errors out.

    Args:
        config_path (str): _description_

    Raises:
        ValueError: _description_
    """
    with open_write(config_path, text=True) as fout:
        print(
            json.dumps(config_template(), indent=4, sort_keys=True),
            file=fout)
    raise ValueError(
        "config file missing. "
        f"new file was created at '{config_path}'. "
        "please correct values in file and run again")


def get_config() -> Config:
    """
    Load the config.

    Returns:
        Config: The config object.
    """
    global CONFIG  # pylint: disable=global-statement

    if CONFIG is not None:
        return CONFIG
    config_path = get_config_path()
    if config_path == "-":
        print("loading config from env")
        vector: 'VecDBConfig | None' = None
        if not envload_bool("NO_QDRANT", default=False):
            vector = {
                "host": envload_str("QDRANT_HOST"),
                "port": envload_int("QDRANT_REST_PORT", default=6333),
                "grpc": envload_int("QDRANT_GRPC_PORT", default=6334),
                "token": envload_str("QDRANT__SERVICE__API_KEY", default=""),
            }
        platforms: dict[str, 'DBConfig'] = {}
        pdbs = envload_str("LOGIN_DB_NAME_PLATFORMS", default="").split(",")
        for db_str in pdbs:
            db_str = db_str.strip()
            if not db_str:
                continue
            short_name, db_name = db_str.split(":")
            platforms[short_name] = {
                "dbname": db_name,
                "dialect": envload_str(
                    "LOGIN_DB_DIALECT", default="postgresql"),
                "host": envload_str("LOGIN_DB_HOST"),
                "port": envload_int("LOGIN_DB_PORT", default=5432),
                "user": envload_str("LOGIN_DB_USERNAME"),
                "passwd": envload_str("LOGIN_DB_PASSWORD"),
                "schema": envload_str(
                    "LOGIN_DB_SCHEMA_PLATFORM", default="public"),
            }
        blogs: dict[str, 'DBConfig'] = {}
        bdbs = envload_str("BLOGS_DB_NAMES", default="").split(",")
        for db_str in bdbs:
            db_str = db_str.strip()
            if not db_str:
                continue
            short_name, db_name = db_str.split(":")
            blogs[short_name] = {
                "dbname": db_name,
                "dialect": envload_str(
                    "BLOGS_DB_DIALECT", default="postgresql"),
                "host": envload_str("BLOGS_DB_HOST"),
                "port": envload_int("BLOGS_DB_PORT", default=5432),
                "user": envload_str("BLOGS_DB_USERNAME"),
                "passwd": envload_str("BLOGS_DB_PASSWORD"),
                "schema": envload_str(
                    "BLOGS_DB_SCHEMA", default="public"),
            }
        CONFIG = {
            "db": {
                "dbname": envload_str("LOGIN_DB_NAME"),
                "dialect": envload_str(
                    "LOGIN_DB_DIALECT", default="postgresql"),
                "host": envload_str("LOGIN_DB_HOST"),
                "port": envload_int("LOGIN_DB_PORT", default=5432),
                "user": envload_str("LOGIN_DB_USERNAME"),
                "passwd": envload_str("LOGIN_DB_PASSWORD"),
                "schema": envload_str("LOGIN_DB_SCHEMA", default="nlpapi"),
            },
            "platforms": platforms,
            "blogs": blogs,
            "opencage": envload_str("OPENCAGE_API"),
            "appsecret": envload_str("APP_SECRET"),
            "vector": vector,
            "smind": envload_path("SMIND_CFG"),
            "graphs": envload_path("GRAPH_PATH"),
            "write_token": envload_str("WRITE_TOKEN"),
            "tanuki": envload_str("TANUKI"),  # the nuke key
        }
    else:
        print(f"loading config file: {config_path}")
        if not os.path.exists(config_path):
            create_config_and_err(config_path)
        with open_read(config_path, text=True) as fin:
            config = cast(Config, json.load(fin))
            if not config:
                create_config_and_err(config_path)
            CONFIG = config
    if CONFIG["write_token"] == "INVALID":
        raise ValueError("write_token must be set!")
    if CONFIG["tanuki"] == "INVALID":
        raise ValueError("tanuki must be set!")
    # with open_write("userdata/config.json", text=True) as fout:
    #     print(
    #         json.dumps(CONFIG, indent=4, sort_keys=True),
    #         file=fout)
    return CONFIG
