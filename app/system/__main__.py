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
import argparse

from app.misc.util import python_module
from app.system.config import get_config
from app.system.db.db import DBConnector
from app.system.deepdive.collection import create_deep_dive_tables
from app.system.location.pipeline import create_location_tables
from app.system.smind.log import create_query_log


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=f"python -m {python_module()}",
        description="Initialize subsystems.")
    parser.add_argument(
        "--init-db",
        default=False,
        action="store_true",
        help="create all tables")
    parser.add_argument(
        "--init-query",
        default=False,
        action="store_true",
        help="create all query tables")
    parser.add_argument(
        "--init-location",
        default=False,
        action="store_true",
        help="create all location tables")
    parser.add_argument(
        "--init-deep-dive",
        default=False,
        action="store_true",
        help="create all deep dive tables")
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    config = get_config()
    if args.init_query or args.init_db:
        create_query_log(DBConnector(config["db"]))
    if args.init_location or args.init_db:
        create_location_tables(DBConnector(config["db"]))
    if args.init_deep_dive or args.init_db:
        create_deep_dive_tables(DBConnector(config["db"]))


if __name__ == "__main__":
    run()
