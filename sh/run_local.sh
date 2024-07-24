#!/usr/bin/env bash
#
# NLP-API provides useful Natural Language Processing capabilities as API.
# Copyright (C) 2024 UNDP Accelerator Labs, Josua Krause
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
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

DEVICE="${DEVICE:-auto}"

start_smind() {
    ${PYTHON} -u -m scattermind \
        --env "${ENV_FILE}" \
        --config local/smind-config.json \
        --device "${DEVICE}" \
        worker \
        --graph local/graphs/ \
        --max-task-retries 2 \
        >> "userdata/smind-${DATE}.log" 2>&1 &
}

start_api() {
    NO_QDRANT='true' \
    HAS_LLAMA='true' \
    SMIND_CFG='local/smind-config.json' \
    GRAPH_PATH='local/graphs/' \
    CONFIG_PATH='-' \
        ${PYTHON} -u -m app \
            --env "${ENV_FILE}" \
            --dedicated \
            >> "userdata/app-${DATE}.log" 2>&1 &
}

start_smind
start_api

sleep 5

exec make run-ts
