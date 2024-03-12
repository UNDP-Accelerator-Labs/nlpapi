#!/bin/sh

set -e

echo "starting redis on port ${PORT}"
echo "redis.version"
cat "redis.version"
echo "redis.conf"
cat "redis.conf"
redis-server "redis.conf" --port "${PORT}"
echo "redis terminated with exit code $?"
