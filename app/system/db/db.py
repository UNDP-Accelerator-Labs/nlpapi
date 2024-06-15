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
import contextlib
import inspect
import sys
import threading
import urllib
from collections.abc import Iterator
from typing import Any, TYPE_CHECKING, TypedDict

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session


if TYPE_CHECKING:
    from app.system.db.base import Base


VERBOSE = False


DBConfig = TypedDict('DBConfig', {
    "dialect": str,
    "host": str,
    "port": int,
    "user": str,
    "passwd": str,
    "dbname": str,
    "schema": str,
})


EngineKey = tuple[str, str, int, str, str, str]


def get_engine_key(config: DBConfig) -> EngineKey:
    return (
        config["dialect"],
        config["host"],
        config["port"],
        config["user"],
        config["dbname"],
        config["schema"],
    )


LOCK = threading.RLock()
ENGINES: dict[EngineKey, sa.engine.Engine] = {}


def get_engine(config: DBConfig) -> sa.engine.Engine:
    key = get_engine_key(config)
    res = ENGINES.get(key)
    if res is not None:
        return res
    with LOCK:
        res = ENGINES.get(key)
        if res is not None:
            return res
        dialect = config["dialect"]
        if dialect != "postgresql":
            print(
                "dialects other than 'postgresql' are not supported. "
                "continue at your own risk", file=sys.stderr)
        user = urllib.parse.quote_plus(config["user"])
        passwd = urllib.parse.quote_plus(config["passwd"])
        host = config["host"]
        port = config["port"]
        dbname = config["dbname"]
        res = sa.create_engine(
            f"{dialect}://{user}:{passwd}@{host}:{port}/{dbname}",
            echo=VERBOSE)
        res = res.execution_options(
            schema_translate_map={None: config["schema"]})
        ENGINES[key] = res
    return res


class DBConnector:
    def __init__(self, config: DBConfig) -> None:
        self._engine = get_engine(config)
        self._namespaces: dict[str, int] = {}
        self._modules: dict[str, int] = {}
        self._schema = config["schema"]

    def table_exists(self, table: type['Base']) -> bool:
        return sa.inspect(self._engine).has_table(
            table.__table__.name, schema=self._schema)

    def create_tables(self, tables: list[type['Base']]) -> None:
        from app.system.db.base import Base

        Base.metadata.create_all(
            self._engine,
            tables=[table.__table__ for table in tables],
            checkfirst=True)

    @staticmethod
    def all_tables() -> list[type['Base']]:
        from app.system.db.base import Base

        return [
            clz
            for _, clz in
            inspect.getmembers(sys.modules["system.db.base"], inspect.isclass)
            if clz is not Base and issubclass(clz, Base)
        ]

    def is_init(self) -> bool:
        return all((self.table_exists(clz) for clz in self.all_tables()))

    def init_db(self) -> None:
        if self.is_init():
            return
        self.create_tables(self.all_tables())

    def get_engine(self) -> sa.engine.Engine:
        return self._engine

    @contextlib.contextmanager
    def get_connection(self) -> Iterator[sa.engine.Connection]:
        with self._engine.connect() as conn:
            yield conn

    @contextlib.contextmanager
    def get_session(self, autocommit: bool = True) -> Iterator[Session]:
        success = False
        with Session(self._engine) as session:
            try:
                yield session
                success = True
            finally:
                if autocommit:
                    if success:
                        session.commit()
                    else:
                        session.rollback()

    def upsert(self, table: type['Base']) -> Any:
        return pg_insert(table)
