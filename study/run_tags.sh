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

cd ..
python -m scattermind --config study/config.json worker --graph study/graphs/