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
