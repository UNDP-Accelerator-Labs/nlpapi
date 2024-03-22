#!/usr/bin/env bash

set -e

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

docker compose -f docker-compose.dev.yml --env-file deploy/default.env up || echo "done $?"
