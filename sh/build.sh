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
RMAIN_CFG="study/rmain/redis.conf"
RDATA_CFG="study/rdata/redis.conf"
RCACHE_CFG="study/rcache/redis.conf"

cp "${SMIND_CONFIG}" "${SMIND_CFG}"

IMAGE_TAG="${IMAGE_TAG:-$(make -s name)}"
IMAGE_NAME="nlpapi:${IMAGE_TAG}"
CONFIG_PATH="${CONFIG_PATH:-${DOCKER_CONFIG}}"
PORT="${PORT:-8080}"

if [ ! -z "${DEV}" ]; then
    IMAGE_NAME="${IMAGE_NAME}-dev"
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

    docker build \
        --build-arg "PORT=6381" \
        --build-arg "CFG_FILE=${RMAIN_CFG}" \
        -t "${IMAGE_NAME}-rmain" \
        -f deploy/redis.Dockerfile \
        .

    docker build \
        --build-arg "PORT=6382" \
        --build-arg "CFG_FILE=${RDATA_CFG}" \
        -t "${IMAGE_NAME}-rdata" \
        -f deploy/redis.Dockerfile \
        .

    docker build \
        --build-arg "PORT=6383" \
        --build-arg "CFG_FILE=${RCACHE_CFG}" \
        -t "${IMAGE_NAME}-rcache" \
        -f deploy/redis.Dockerfile \
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

    docker buildx build \
        --platform linux/amd64 \
        --build-arg "PORT=6381" \
        --build-arg "CFG_FILE=${RMAIN_CFG}" \
        -t "${IMAGE_NAME}-rmain" \
        -f deploy/redis.Dockerfile \
        .

    docker buildx build \
        --platform linux/amd64 \
        --build-arg "PORT=6382" \
        --build-arg "CFG_FILE=${RDATA_CFG}" \
        -t "${IMAGE_NAME}-rdata" \
        -f deploy/redis.Dockerfile \
        .

    docker buildx build \
        --platform linux/amd64 \
        --build-arg "PORT=6383" \
        --build-arg "CFG_FILE=${RCACHE_CFG}" \
        -t "${IMAGE_NAME}-rcache" \
        -f deploy/redis.Dockerfile \
        .
fi

echo "# created by sh/build.sh" > deploy/default.env
echo "DOCKER_WORKER=${IMAGE_NAME}-worker" >> deploy/default.env
echo "DOCKER_API=${IMAGE_NAME}-api" >> deploy/default.env
echo "DOCKER_RMAIN=${IMAGE_NAME}-rmain" >> deploy/default.env
echo "DOCKER_RDATA=${IMAGE_NAME}-rdata" >> deploy/default.env
echo "DOCKER_RCACHE=${IMAGE_NAME}-rcache" >> deploy/default.env

echo "built ${IMAGE_NAME}-api"
echo "built ${IMAGE_NAME}-worker"
echo "built ${IMAGE_NAME}-rmain"
echo "built ${IMAGE_NAME}-rdata"
echo "built ${IMAGE_NAME}-rcache"
