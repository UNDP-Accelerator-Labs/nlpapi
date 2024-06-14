#!/usr/bin/env bash

set -ex

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

ENV_FILE="${ENV_FILE:-userdata/local.env}"

PYTHON="${PYTHON:-python}"
DATE=$(date "+%Y-%m-%d")

if [ ! -f "${ENV_FILE}" ]; then
    mkdir -p "$(dirname -- ${ENV_FILE})"
    cp "env.sample" "${ENV_FILE}"
    WRITE_TOKEN=$(make -s uuid)
    TANUKI=$(make -s uuid)
    echo "WRITE_TOKEN=${WRITE_TOKEN}" >> "${ENV_FILE}"
    echo "TANUKI=${TANUKI}" >> "${ENV_FILE}"
    echo "created env file at ${ENV_FILE} please fill in all values and run again"
    exit 1
fi

start_redis() {
    redis-server "local/redis/$1.conf" --port "$2" \
        >> "userdata/$1/redis-${DATE}.log" 2>&1 &
}

start_redis rmain 6380
start_redis rbody 6381
start_redis rdata 6382
start_redis rcache 6383

DEVICE=auto

start_smind() {
    ${PYTHON} -m scattermind \
        --config local/smind-config.json \
        --device "${DEVICE}" \
        worker \
        --graph local/graphs/ \
        >> "userdata/smind-${DATE}.log" 2>&1 &
}

start_api() {
    NO_QDRANT='true' \
    HAS_LLAMA='true' \
    SMIND_CFG='local/smind-config.json' \
    GRAPH_PATH='local/graphs/' \
    CONFIG_PATH='-' \
        ${PYTHON} -m app --dedicated \
            >> "userdata/app-${DATE}.log" 2>&1 &
}

start_smind
start_api

exec make run-ts
