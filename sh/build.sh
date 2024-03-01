#!/usr/bin/env bash

set -e

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

mkdir -p buildtmp
DOCKER_CONFIG=docker.config.json
LOCAL_CONFIG=config.json
NO_CONFIG=noconfig.json
SMIND_CONFIG="${SMIND_CONFIG:-deploy/smind-config.json}"
SMIND_GRAPHS="${SMIND_GRAPHS:-study/graphs/}"

SMIND_CFG="buildtmp/smind-config.json"

cp "${SMIND_CONFIG}" "${SMIND_CFG}"

IMAGE_TAG="${IMAGE_TAG:-$(make -s name)}"
IMAGE_NAME="nlpapi:${IMAGE_TAG}"
CONFIG_PATH="${CONFIG_PATH:-${DOCKER_CONFIG}}"
PORT="${PORT:-8080}"

if [ ! -z "${DEV}" ]; then
    IMAGE_TAG="${IMAGE_TAG}-dev"
fi

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
trap 'rm -- version.txt' EXIT

echo "building ${IMAGE_NAME}"

if [ ! -z "${DEV}" ]; then
    docker build \
        --build-arg "CONFIG_PATH=${CONFIG_PATH}" \
        --build-arg "SMIND_CONFIG=${SMIND_CFG}" \
        --build-arg "SMIND_GRAPHS=${SMIND_GRAPHS}" \
        --build-arg "PORT=${PORT}" \
        -t "${IMAGE_NAME}-api" \
        -f deploy/api.Dockerfile \
        .

    docker build \
        --build-arg "SMIND_CONFIG=${SMIND_CFG}" \
        --build-arg "SMIND_GRAPHS=${SMIND_GRAPHS}" \
        -t "${IMAGE_NAME}-worker" \
        -f deploy/worker.Dockerfile \
        .
else
    docker buildx build \
        --platform linux/amd64 \
        --build-arg "CONFIG_PATH=${CONFIG_PATH}" \
        --build-arg "SMIND_CONFIG=${SMIND_CFG}" \
        --build-arg "SMIND_GRAPHS=${SMIND_GRAPHS}" \
        --build-arg "PORT=${PORT}" \
        -t "${IMAGE_NAME}-api" \
        -f deploy/api.Dockerfile \
        .

    docker buildx build \
        --platform linux/amd64 \
        --build-arg "SMIND_CONFIG=${SMIND_CFG}" \
        --build-arg "SMIND_GRAPHS=${SMIND_GRAPHS}" \
        -t "${IMAGE_NAME}-worker" \
        -f deploy/worker.Dockerfile \
        .
fi

echo "# created by sh/build.sh" > deploy/default.env
echo "DOCKER_WORKER=${IMAGE_NAME}-worker" >> deploy/default.env
echo "DOCKER_API=${IMAGE_NAME}-api" >> deploy/default.env

echo "built ${IMAGE_NAME}-api"
echo "built ${IMAGE_NAME}-worker"
