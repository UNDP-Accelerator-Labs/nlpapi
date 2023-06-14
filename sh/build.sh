#!/usr/bin/env bash

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

DOCKER_CONFIG=docker.config.json
LOCAL_CONFIG=config.json
NO_CONFIG=noconfig.json

IMAGE_NAME="smartsearch:$(make -s name)"
CONFIG_PATH="${CONFIG_PATH:-${DOCKER_CONFIG}}"
PORT="${PORT:-80}"

echo "using config: ${CONFIG_PATH}"
if [ "${CONFIG_PATH}" == "${LOCAL_CONFIG}" ]; then
    echo "WARNING: using local config file!" 1>&2
fi

if [ "${CONFIG_PATH}" == "-" ]; then
    CONFIG_PATH="${NO_CONFIG}"
    echo "{}" > "${CONFIG_PATH}"
else
    if [ "${CONFIG_PATH}" != "${DOCKER_CONFIG}" ]; then
        cp "${CONFIG_PATH}" "${DOCKER_CONFIG}"
        CONFIG_PATH="${DOCKER_CONFIG}"
    fi
fi

make -s version-file

echo "building ${IMAGE_NAME}"

docker build \
    --build-arg "CONFIG_PATH=${CONFIG_PATH}" \
    --build-arg "PORT=${PORT}" \
    -t "${IMAGE_NAME}" \
    -f deploy/Dockerfile \
    .

echo "built ${IMAGE_NAME}"

rm version.txt
