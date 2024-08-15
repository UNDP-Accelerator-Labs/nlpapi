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
"""Start the NLP API app server."""
import argparse
import os
import traceback

from dotenv import load_dotenv
from quick_server import setup_shutdown

from app.api.server import (
    fallback_server,
    get_version_strs,
    setup_server,
    start,
)
from app.misc.util import python_module


def parse_args() -> argparse.Namespace:
    """
    Parses command line arguments.

    Returns:
        argparse.Namespace: The arguments.
    """
    parser = argparse.ArgumentParser(
        prog=f"python -m {python_module()}",
        description="Run the API server")
    parser.add_argument(
        "--address",
        default=None,
        help="the address of the API server")
    parser.add_argument(
        "--port",
        default=None,
        type=int,
        help="the port of the API server")
    parser.add_argument(
        "--env",
        default=None,
        help="loads the given env file at startup")
    parser.add_argument(
        "--dedicated",
        default=False,
        action="store_true",
        help="whether the server runs in a deployment")
    return parser.parse_args()


def run() -> None:
    """Start the app server."""
    args = parse_args()
    env_file: str | None = args.env
    if env_file:
        if not os.path.exists(env_file):
            print(
                f"could not load env! {env_file} does not exist!\n"
                "this is expected in production!")
        else:
            print(f"loading env {env_file}")
            load_dotenv(env_file)
    versions = get_version_strs()
    print(f"python version: {versions['python_version_detail']}")
    print(f"app version: {versions['app_version']}")
    print(f"app commit: {versions['commit']}")
    print(f"deploy time: {versions['deploy_time']}")
    print(f"start time: {versions['start_time']}")
    setup_shutdown()
    try:
        server, prefix = setup_server(
            addr=args.address,
            port=args.port,
            deploy=args.dedicated,
            versions=versions)
    except Exception:  # pylint: disable=broad-exception-caught
        exc_strs = traceback.format_exc().splitlines()
        print("Error while creating server:")
        print("\n".join(exc_strs))
        server, prefix = fallback_server(
            addr=args.address,
            port=args.port,
            deploy=args.dedicated,
            versions=versions,
            exc_strs=exc_strs)
    start(server, prefix)


if __name__ == "__main__":
    run()
