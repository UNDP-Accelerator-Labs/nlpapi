#!/usr/bin/env bash

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

IMAGE_NAME="smartsearch-$(make -s name)"
CONFIG_PATH=${CONFIG_PATH:-docker.config.json}
API_SERVER_PORT=${API_SERVER_PORT:-8080}

echo "using config: ${CONFIG_PATH}"
if [ "${CONFIG_PATH}" == "config.json" ]; then
    echo "WARNING: using local config file!" 1>&2
fi

cp "${CONFIG_PATH}" docker.config.json

make -s version-file

echo "building ${IMAGE_NAME}"

docker build \
    --build-arg "CONFIG_PATH=docker.config.json" \
    --build-arg "API_SERVER_PORT=${API_SERVER_PORT}" \
    -t "${IMAGE_NAME}" \
    -f deploy/Dockerfile \
    .

echo "built ${IMAGE_NAME}"

rm version.txt
