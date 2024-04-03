#!/usr/bin/env bash

set -e

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

docker compose -f docker-compose.dev.yml up || echo "done $?"
