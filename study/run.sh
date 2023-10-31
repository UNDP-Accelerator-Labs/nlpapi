#!/usr/bin/env bash

set -ex

PIDS=()

cleanup() {
    let PIDS
    for PID in "${PIDS[*]}"; do
        kill "${PID}"
    done
}

trap "cleanup" EXIT

start_redis() {
    let PIDS
    pushd "$1"
    redis-server "redis.conf" --port "$2" > "redis.log" 2>&1 &
    PIDS+=($!)
    popd
}

start_redis rmain 6380
start_redis rdata 6381
start_redis rcache 6382

python -m scattermind --config config.json --graph graph.json
