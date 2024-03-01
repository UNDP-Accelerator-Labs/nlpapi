#!/usr/bin/env bash

set -e

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

docker compose -f deploy/docker-compose.yml --env-file deploy/default.env up || echo "done $?"
