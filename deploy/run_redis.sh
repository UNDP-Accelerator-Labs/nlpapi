#!/bin/sh

set -e

echo "starting redis on port ${PORT}"
echo "/app/redis.version"
cat "/app/redis.version"
echo "/app/redis.conf"
cat "/app/redis.conf"
redis-server "/app/redis.conf" --port "${PORT}"
echo "redis terminated with exit code $?"
