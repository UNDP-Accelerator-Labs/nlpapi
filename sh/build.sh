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
DEFAULT_CONFIG=-
SMIND_CONFIG="${SMIND_CONFIG:-deploy/smind-config.json}"
SMIND_GRAPHS="${SMIND_GRAPHS:-deploy/graphs/}"

QDRANT_API_TOKEN=$(make -s uuid)

REDIS_VERSION_FILE="buildtmp/redis.version"
QDRANT_VERSION_FILE="buildtmp/qdrant.version"
SMIND_CFG="buildtmp/smind-config.json"
SMIND_GRS="buildtmp/graphs/"
RMAIN_CFG="study/rmain/redis.conf"
RDATA_CFG="study/rdata/redis.conf"
RCACHE_CFG="study/rcache/redis.conf"

cp "deploy/redis.version" "${REDIS_VERSION_FILE}"
cp "deploy/qdrant.version" "${QDRANT_VERSION_FILE}"
cp "${SMIND_CONFIG}" "${SMIND_CFG}"
cp -R "${SMIND_GRAPHS}" "${SMIND_GRS}"

IMAGE_TAG="${IMAGE_TAG:-$(make -s name)}"
IMAGE_BASE="nlpapi"
PORT="${PORT:-8080}"

if [ ! -z "${DEV}" ]; then
    IMAGE_BASE="${IMAGE_BASE}-dev"
fi

if [ ! -z "${DEV}" ]; then
    CONFIG_PATH="${CONFIG_PATH:-${DOCKER_CONFIG}}"
else
    CONFIG_PATH="${CONFIG_PATH:-${DEFAULT_CONFIG}}"
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

source "${REDIS_VERSION_FILE}"
source "${QDRANT_VERSION_FILE}"

docker_build() {
    TAG="$1"
    if ! docker inspect --type=image "${TAG}" &> /dev/null ; then
        shift
        if [ ! -z "${DEV}" ]; then
            docker build -t "${TAG}" "${@}"
        else
            docker buildx build --platform linux/amd64 -t "${TAG}" "${@}"
        fi
        echo "built ${TAG}"
    else
        echo "${TAG} already exists!"
    fi
}

docker_build \
    "${IMAGE_BASE}-api:${IMAGE_TAG}" \
    --build-arg "CONFIG_PATH=${CONFIG_PATH}" \
    --build-arg "SMIND_CONFIG=${SMIND_CFG}" \
    --build-arg "SMIND_GRAPHS=${SMIND_GRS}" \
    --build-arg "PORT=${PORT}" \
    -f deploy/api.Dockerfile \
    .

docker_build \
    "${IMAGE_BASE}-worker:${IMAGE_TAG}" \
    --build-arg "SMIND_CONFIG=${SMIND_CFG}" \
    --build-arg "SMIND_GRAPHS=${SMIND_GRS}" \
    -f deploy/worker.Dockerfile \
    .

docker_build \
    "${IMAGE_BASE}-rmain:${REDIS_DOCKER_VERSION}" \
    --build-arg "PORT=6381" \
    --build-arg "CFG_FILE=${RMAIN_CFG}" \
    --build-arg "REDIS_VERSION_FILE=${REDIS_VERSION_FILE}" \
    -f deploy/redis.Dockerfile \
    .

docker_build \
    "${IMAGE_BASE}-rdata:${REDIS_DOCKER_VERSION}" \
    --build-arg "PORT=6382" \
    --build-arg "CFG_FILE=${RDATA_CFG}" \
    --build-arg "REDIS_VERSION_FILE=${REDIS_VERSION_FILE}" \
    -f deploy/redis.Dockerfile \
    .

docker_build \
    "${IMAGE_BASE}-rcache:${REDIS_DOCKER_VERSION}" \
    --build-arg "PORT=6383" \
    --build-arg "CFG_FILE=${RCACHE_CFG}" \
    --build-arg "REDIS_VERSION_FILE=${REDIS_VERSION_FILE}" \
    -f deploy/redis.Dockerfile \
    .

if [ ! -z "${DEV}" ]; then
    DOCKER_COMPOSE_OUT="docker-compose.dev.yml"
else
    DOCKER_COMPOSE_OUT="docker-compose.yml"
fi

DEFAULT_ENV_FILE=deploy/default.env
echo "# created by sh/build.sh" > "${DEFAULT_ENV_FILE}"
echo "DOCKER_WORKER=${IMAGE_BASE}-worker:${IMAGE_TAG}" >> "${DEFAULT_ENV_FILE}"
echo "DOCKER_API=${IMAGE_BASE}-api:${IMAGE_TAG}" >> "${DEFAULT_ENV_FILE}"
echo "DOCKER_RMAIN=${IMAGE_BASE}-rmain:${REDIS_DOCKER_VERSION}" >> "${DEFAULT_ENV_FILE}"
echo "DOCKER_RDATA=${IMAGE_BASE}-rdata:${REDIS_DOCKER_VERSION}" >> "${DEFAULT_ENV_FILE}"
echo "DOCKER_RCACHE=${IMAGE_BASE}-rcache:${REDIS_DOCKER_VERSION}" >> "${DEFAULT_ENV_FILE}"
echo "DOCKER_QDRANT=${IMAGE_BASE}-qdrant:${QDRANT_DOCKER_VERSION}" >> "${DEFAULT_ENV_FILE}"
echo "QDRANT_API_TOKEN=${QDRANT_API_TOKEN}" >> "${DEFAULT_ENV_FILE}"

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
        if variable.startswith("$DOCKER_"):
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

${PYTHON} -c "${PY_COMPOSE}" "${DOCKER_LOGIN_SERVER}" "deploy/docker-compose.yml" "${DEFAULT_ENV_FILE}" "${DOCKER_COMPOSE_OUT}"
