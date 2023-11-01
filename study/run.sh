#!/usr/bin/env bash

set -ex

start_redis() {
    pushd "$1"
    redis-server "redis.conf" --port "$2" >> "redis.log" 2>&1 &
    popd
}

start_redis rmain 6380 &
start_redis rdata 6381 &
start_redis rcache 6382 &

python -m scattermind --config config.json worker --graph graph.json
