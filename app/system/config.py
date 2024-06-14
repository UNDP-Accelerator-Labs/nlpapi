import json
import os
from typing import cast, TYPE_CHECKING, TypedDict

from app.misc.env import envload_bool, envload_int, envload_path, envload_str
from app.misc.io import open_read, open_write


if TYPE_CHECKING:
    from app.system.db.db import DBConfig
    from app.system.smind.vec import VecDBConfig


Config = TypedDict('Config', {
    "db": 'DBConfig',
    "platform": 'DBConfig',
    "blogs": 'DBConfig',
    "opencage": str,
    "appsecret": str,
    "vector": 'VecDBConfig | None',
    "smind": str,
    "graphs": str,
    "write_token": str,
    "tanuki": str,
})


CONFIG: Config | None = None
CONFIG_PATH: str | None = None


def get_config_path() -> str:
    global CONFIG_PATH  # pylint: disable=global-statement

    if CONFIG_PATH is None:
        CONFIG_PATH = envload_path("CONFIG_PATH", default="config.json")
    return CONFIG_PATH


def config_template() -> Config:
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
        "platform": default_conn.copy(),
        "blogs": default_conn.copy(),
        "opencage": "INVALID",
        "appsecret": "INVALID",
        "vector": default_vec.copy(),
        "smind": "smind-config.json",
        "graphs": "graphs/",
        "write_token": "INVALID",
        "tanuki": "INVALID",
    }


def create_config_and_err(config_path: str) -> None:
    with open_write(config_path, text=True) as fout:
        print(
            json.dumps(config_template(), indent=4, sort_keys=True),
            file=fout)
    raise ValueError(
        "config file missing. "
        f"new file was created at '{config_path}'. "
        "please correct values in file and run again")


def get_config() -> Config:
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
            "platform": {
                "dbname": envload_str("LOGIN_DB_NAME"),
                "dialect": envload_str(
                    "LOGIN_DB_DIALECT", default="postgresql"),
                "host": envload_str("LOGIN_DB_HOST"),
                "port": envload_int("LOGIN_DB_PORT", default=5432),
                "user": envload_str("LOGIN_DB_USERNAME"),
                "passwd": envload_str("LOGIN_DB_PASSWORD"),
                "schema": envload_str(
                    "LOGIN_DB_SCHEMA_PLATFORM", default="public"),
            },
            "blogs": {
                "dbname": envload_str("BLOGS_DB_NAME"),
                "dialect": envload_str(
                    "BLOGS_DB_DIALECT", default="postgresql"),
                "host": envload_str("BLOGS_DB_HOST"),
                "port": envload_int("BLOGS_DB_PORT", default=5432),
                "user": envload_str("BLOGS_DB_USERNAME"),
                "passwd": envload_str("BLOGS_DB_PASSWORD"),
                "schema": envload_str("BLOGS_DB_SCHEMA", default="public"),
            },
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
    return CONFIG
