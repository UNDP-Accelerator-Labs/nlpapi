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
"""Database connector."""
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
"""Whether to be verbose about database operations."""


DBConfig = TypedDict('DBConfig', {
    "dialect": str,
    "host": str,
    "port": int,
    "user": str,
    "passwd": str,
    "dbname": str,
    "schema": str,
})
"""A database connection configuration."""


EngineKey = tuple[str, str, int, str, str, str]
"""A database connection configuration as tuple."""


def get_engine_key(config: DBConfig) -> EngineKey:
    """
    Converts a database config to an engine key.

    Args:
        config (DBConfig): The config.

    Returns:
        EngineKey: The config tuple.
    """
    return (
        config["dialect"],
        config["host"],
        config["port"],
        config["user"],
        config["dbname"],
        config["schema"],
    )


LOCK = threading.RLock()
"""Lock for database engines."""
ENGINES: dict[EngineKey, sa.engine.Engine] = {}
"""The active database engines."""


def get_engine(config: DBConfig) -> sa.engine.Engine:
    """
    Gets a database engine from a configuration. Engines are cached.

    Args:
        config (DBConfig): The database config.

    Returns:
        sa.engine.Engine: The engine.
    """
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
        user = urllib.parse.quote(config["user"])
        passwd = urllib.parse.quote(config["passwd"])
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
    """Class for creating database connections and other database
    functionality."""
    def __init__(self, config: DBConfig) -> None:
        """
        Create a database connector for a given configuration.

        Args:
            config (DBConfig): The database configuration.
        """
        self._engine = get_engine(config)
        self._namespaces: dict[str, int] = {}
        self._modules: dict[str, int] = {}
        self._schema = config["schema"]

    def table_exists(self, table: type['Base']) -> bool:
        """
        Whether the given table exists in the database.

        Args:
            table (type[Base]): The table.

        Returns:
            bool: True, if the table exists.
        """
        return sa.inspect(self._engine).has_table(
            table.__table__.name, schema=self._schema)

    def create_tables(self, tables: list[type['Base']]) -> None:
        """
        Creates the given tables.

        Args:
            tables (list[type[Base]]): The list of tables to create.
        """
        from app.system.db.base import Base

        print(f"creating {tables=}")
        Base.metadata.create_all(
            self._engine,
            tables=[table.__table__ for table in tables],
            checkfirst=True)

    @staticmethod
    def all_tables() -> list[type['Base']]:
        """
        Lists all registered tables.

        Returns:
            list[type[Base]]: All tables. Note, that tables might belong to
                different databases.
        """
        from app.system.db.base import Base

        return [
            clz
            for _, clz in
            inspect.getmembers(sys.modules["system.db.base"], inspect.isclass)
            if clz is not Base and issubclass(clz, Base)
        ]

    def is_init(self) -> bool:
        """
        Checks whether all tables exist. Don't use this function as the tables
        are spread across multiple databases.

        Returns:
            bool: False (since not all tables can exist in the same database).
        """
        return all((self.table_exists(clz) for clz in self.all_tables()))

    def init_db(self) -> None:
        """
        Initializes all tables. Don't use this function as it will create
        tables that don't belong to the current database.
        """
        if self.is_init():
            return
        self.create_tables(self.all_tables())

    def get_engine(self) -> sa.engine.Engine:
        """
        Gets the underlying engine for this connector.

        Returns:
            sa.engine.Engine: The engine.
        """
        return self._engine

    @contextlib.contextmanager
    def get_connection(self) -> Iterator[sa.engine.Connection]:
        """
        Get a database connection. This is not a session. There are no
        consistency guarantees for executing multiple queries.

        Yields:
            sa.engine.Connection: The connection.
        """
        with self._engine.connect() as conn:
            yield conn

    @contextlib.contextmanager
    def get_session(self, autocommit: bool = True) -> Iterator[Session]:
        """
        Gets a database session.

        Args:
            autocommit (bool, optional): Whether to automatically commit the
                session at the end. Defaults to True.

        Yields:
            Session: The session.
        """
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
        """
        Create an upsert statement.

        Args:
            table (type[Base]): The table to upsert.

        Returns:
            Any: The statement.
        """
        return pg_insert(table)
