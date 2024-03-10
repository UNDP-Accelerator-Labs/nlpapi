#!/usr/bin/env bash

set -e

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

mkdir -p buildtmp

# FIXME keep track of separate versions for each image. not all images need to update every time

DOCKER_LOGIN_SERVER="acclabdocker.azurecr.io"
PYTHON="${PYTHON:-python3}"

DOCKER_CONFIG=docker.config.json
LOCAL_CONFIG=config.json
NO_CONFIG=noconfig.json
SMIND_CONFIG="${SMIND_CONFIG:-deploy/smind-config.json}"
SMIND_GRAPHS="${SMIND_GRAPHS:-deploy/graphs/}"

QDRANT_API_TOKEN=$(make -s uuid)

SMIND_CFG="buildtmp/smind-config.json"
SMIND_GRS="buildtmp/graphs/"
RMAIN_CFG="study/rmain/redis.conf"
RDATA_CFG="study/rdata/redis.conf"
RCACHE_CFG="study/rcache/redis.conf"

cp "${SMIND_CONFIG}" "${SMIND_CFG}"
cp -R "${SMIND_GRAPHS}" "${SMIND_GRS}"

IMAGE_TAG="${IMAGE_TAG:-$(make -s name)}"
IMAGE_BASE="nlpapi"
CONFIG_PATH="${CONFIG_PATH:-${DOCKER_CONFIG}}"
PORT="${PORT:-8080}"

if [ ! -z "${DEV}" ]; then
    IMAGE_BASE="${IMAGE_BASE}-dev"
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

echo "building ${IMAGE_BASE}"

if [ ! -z "${DEV}" ]; then
    docker build \
        --build-arg "CONFIG_PATH=${CONFIG_PATH}" \
        --build-arg "SMIND_CONFIG=${SMIND_CFG}" \
        --build-arg "SMIND_GRAPHS=${SMIND_GRS}" \
        --build-arg "PORT=${PORT}" \
        -t "${IMAGE_BASE}-api:${IMAGE_TAG}" \
        -f deploy/api.Dockerfile \
        .

    docker build \
        --build-arg "SMIND_CONFIG=${SMIND_CFG}" \
        --build-arg "SMIND_GRAPHS=${SMIND_GRS}" \
        -t "${IMAGE_BASE}-worker:${IMAGE_TAG}" \
        -f deploy/worker.Dockerfile \
        .

    docker build \
        --build-arg "PORT=6381" \
        --build-arg "CFG_FILE=${RMAIN_CFG}" \
        -t "${IMAGE_BASE}-rmain:${IMAGE_TAG}" \
        -f deploy/redis.Dockerfile \
        .

    docker build \
        --build-arg "PORT=6382" \
        --build-arg "CFG_FILE=${RDATA_CFG}" \
        -t "${IMAGE_BASE}-rdata:${IMAGE_TAG}" \
        -f deploy/redis.Dockerfile \
        .

    docker build \
        --build-arg "PORT=6383" \
        --build-arg "CFG_FILE=${RCACHE_CFG}" \
        -t "${IMAGE_BASE}-rcache:${IMAGE_TAG}" \
        -f deploy/redis.Dockerfile \
        .

    DOCKER_COMPOSE_OUT="docker-compose.dev.yml"
else
    docker buildx build \
        --platform linux/amd64 \
        --build-arg "CONFIG_PATH=${CONFIG_PATH}" \
        --build-arg "SMIND_CONFIG=${SMIND_CFG}" \
        --build-arg "SMIND_GRAPHS=${SMIND_GRS}" \
        --build-arg "PORT=${PORT}" \
        -t "${IMAGE_BASE}-api:${IMAGE_TAG}" \
        -f deploy/api.Dockerfile \
        .

    docker buildx build \
        --platform linux/amd64 \
        --build-arg "SMIND_CONFIG=${SMIND_CFG}" \
        --build-arg "SMIND_GRAPHS=${SMIND_GRS}" \
        -t "${IMAGE_BASE}-worker:${IMAGE_TAG}" \
        -f deploy/worker.Dockerfile \
        .

    docker buildx build \
        --platform linux/amd64 \
        --build-arg "PORT=6381" \
        --build-arg "CFG_FILE=${RMAIN_CFG}" \
        -t "${IMAGE_BASE}-rmain:${IMAGE_TAG}" \
        -f deploy/redis.Dockerfile \
        .

    docker buildx build \
        --platform linux/amd64 \
        --build-arg "PORT=6382" \
        --build-arg "CFG_FILE=${RDATA_CFG}" \
        -t "${IMAGE_BASE}-rdata:${IMAGE_TAG}" \
        -f deploy/redis.Dockerfile \
        .

    docker buildx build \
        --platform linux/amd64 \
        --build-arg "PORT=6383" \
        --build-arg "CFG_FILE=${RCACHE_CFG}" \
        -t "${IMAGE_BASE}-rcache:${IMAGE_TAG}" \
        -f deploy/redis.Dockerfile \
        .

    DOCKER_COMPOSE_OUT="docker-compose.yml"
fi

echo "# created by sh/build.sh" > deploy/default.env
echo "DOCKER_WORKER=${IMAGE_BASE}-worker:${IMAGE_TAG}" >> deploy/default.env
echo "DOCKER_API=${IMAGE_BASE}-api:${IMAGE_TAG}" >> deploy/default.env
echo "DOCKER_RMAIN=${IMAGE_BASE}-rmain:${IMAGE_TAG}" >> deploy/default.env
echo "DOCKER_RDATA=${IMAGE_BASE}-rdata:${IMAGE_TAG}" >> deploy/default.env
echo "DOCKER_RCACHE=${IMAGE_BASE}-rcache:${IMAGE_TAG}" >> deploy/default.env
echo "DOCKER_QDRANT=${IMAGE_BASE}-qdrant:${IMAGE_TAG}" >> deploy/default.env
echo "QDRANT_API_TOKEN=${QDRANT_API_TOKEN}" >> deploy/default.env

echo "built ${IMAGE_BASE}-api:${IMAGE_TAG}"
echo "built ${IMAGE_BASE}-worker:${IMAGE_TAG}"
echo "built ${IMAGE_BASE}-rmain:${IMAGE_TAG}"
echo "built ${IMAGE_BASE}-rdata:${IMAGE_TAG}"
echo "built ${IMAGE_BASE}-rcache:${IMAGE_TAG}"
echo "built ${IMAGE_BASE}-qdrant:${IMAGE_TAG}"

! read -r -d '' PY_COMPOSE <<'EOF'
import os
import sys

prefix = sys.argv[1]
dcompose = sys.argv[2]
denv = sys.argv[3]
dout = sys.argv[4]
substitute = {}
with open(denv, "r", encoding="utf-8") as fin:
    for line in fin:
        line = line.rstrip().split("#", 1)[0].strip()
        if not line:
            continue
        variable, value = line.split("=", 1)
        variable = f"${variable}".strip()
        value = f"{value.strip()}"
        if variable.startswith("DOCKER_"):
            value = f"{prefix}/{value}"
        substitute[variable] = value
with open(dcompose, "r", encoding="utf-8") as din:
    content = din.read()
for variable, value in sorted(
        substitute.items(), key=lambda e: len(e[0]), reverse=True):
    content = content.replace(variable, value)
with open(dout, "w", encoding="utf-8") as fout:
    fout.write(content)
EOF

${PYTHON} -c "${PY_COMPOSE}" "${DOCKER_LOGIN_SERVER}" "deploy/docker-compose.yml" "deploy/default.env" "${DOCKER_COMPOSE_OUT}"
