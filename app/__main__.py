import argparse
import traceback

from app.api.server import (
    fallback_server,
    get_version_strs,
    setup_server,
    start,
)
from app.misc.util import python_module


def parse_args() -> argparse.Namespace:
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
        "--dedicated",
        default=False,
        action="store_true",
        help="whether the server runs in a deployment")
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    versions = get_version_strs()
    print(f"python version: {versions['python_version_detail']}")
    print(f"app version: {versions['app_version']}")
    print(f"app commit: {versions['commit']}")
    print(f"deploy time: {versions['deploy_time']}")
    print(f"start time: {versions['start_time']}")
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
