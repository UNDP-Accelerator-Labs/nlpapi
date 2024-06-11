#!/usr/bin/env bash

set -ex

start_redis() {
    pushd "$1"
    redis-server "redis.conf" --port "$2" >> "redis.log" 2>&1 &
    popd
}

start_redis rmain 6381 &
start_redis rdata 6383 &
start_redis rcache 6382 &

DEVICE=auto
# DEVICE="${DEVICE:-cpu}"
# if command -v nvidia-smi &> /dev/null; then
#     DEVICE=auto
# fi

cd ..
if [ "${DEVICE}" = "auto" ]; then
    exec python -m scattermind --config study/config.json worker --graph study/graphs/
else
    exec python -m scattermind --config study/config.json --device "${DEVICE}" worker --graph study/graphs/
fi
