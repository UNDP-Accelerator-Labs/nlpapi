#!/usr/bin/env bash

set -e

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

mkdir -p buildtmp

PYTHON="${PYTHON:-python3}"

DOCKER_CONFIG=docker.config.json
LOCAL_CONFIG=config.json
NO_CONFIG=noconfig.json
DEFAULT_CONFIG=-
SMIND_CONFIG="${SMIND_CONFIG:-deploy/smind-config.json}"
SMIND_GRAPHS="${SMIND_GRAPHS:-deploy/graphs/}"

REDIS_VERSION_FILE="buildtmp/redis.version"
QDRANT_VERSION_FILE="buildtmp/qdrant.version"
WIPE_VERSION_FILE="buildtmp/wipe.version"
DEVMODE_CONF_FILE="buildtmp/devmode.conf"
REQUIREMENTS_API_FILE="buildtmp/requirements.api.txt"
REQUIREMENTS_WORKER_FILE="buildtmp/requirements.worker.txt"
SMIND_CFG="buildtmp/smind-config.json"
SMIND_GRS="buildtmp/graphs/"
RMAIN_CFG="buildtmp/rmain.conf"
RDATA_CFG="buildtmp/rdata.conf"
RCACHE_CFG="buildtmp/rcache.conf"
RBODY_CFG="buildtmp/rbody.conf"
REDIS_RUN_SCRIPT="buildtmp/run_redis.sh"
WIPE_RUN_SCRIPT="buildtmp/run_wipe.sh"
WIPE_SCRIPT="buildtmp/wipe.sh"

cp "deploy/redis/rmain.conf" "${RMAIN_CFG}"
cp "deploy/redis/rdata.conf" "${RDATA_CFG}"
cp "deploy/redis/rcache.conf" "${RCACHE_CFG}"
cp "deploy/redis/rbody.conf" "${RBODY_CFG}"
cp "deploy/redis.version" "${REDIS_VERSION_FILE}"
cp "deploy/qdrant.version" "${QDRANT_VERSION_FILE}"
cp "deploy/devmode.conf" "${DEVMODE_CONF_FILE}"
cp "deploy/run_redis.sh" "${REDIS_RUN_SCRIPT}"
cp "deploy/run_wipe.sh" "${WIPE_RUN_SCRIPT}"
cp "deploy/wipe.sh" "${WIPE_SCRIPT}"
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
    QDRANT_API_TOKEN=
else
    CONFIG_PATH="${CONFIG_PATH:-${DEFAULT_CONFIG}}"
    QDRANT_API_TOKEN=$(make -s uuid)
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

source "${DEVMODE_CONF_FILE}"
source "${REDIS_VERSION_FILE}"
source "${QDRANT_VERSION_FILE}"
source "deploy/wipe.version"

if [ ! -z "${DEVMODE}" ]; then
    QDRANT_DOCKER_VERSION="${QDRANT_DOCKER_VERSION}-devmode"
    REDIS_DOCKER_VERSION="${REDIS_DOCKER_VERSION}-devmode"
    WIPE_DOCKER_VERSION="${WIPE_DOCKER_VERSION}-devmode"
fi

echo "{\"app\": \"wipe\", \"version\": \"${WIPE_DOCKER_VERSION}\"}" > "${WIPE_VERSION_FILE}"

QUICK_SERVER_PATH="../quick_server"
REDIPY_PATH="../redipy"
SMIND_PATH="../scattermind"

QUICK_SERVER_URL="git+https://github.com/JosuaKrause/quick_server.git"
REDIPY_URL="git+https://github.com/JosuaKrause/redipy.git"
SMIND_URL="git+https://github.com/JosuaKrause/scattermind.git"

! read -r -d '' PY_LIB <<'EOF'
import os
import sys

fname = sys.argv[1]
lib_name = sys.argv[2]
lib_replace = sys.argv[3]
lines = []
with open(fname, "r", encoding="utf-8") as fin:
    for line in fin:
        line = line.rstrip()
        if not line.startswith(lib_name):
            lines.append(line)
            continue
        lines.append(lib_replace)
with open(fname, "w", encoding="utf-8") as fout:
    fout.write("\n".join(lines))
EOF

replace_lib() {
    REQ_FILE="$1"
    LIB="$2"
    LIB_PATH="$3"
    LIB_URL="$4"
    LIB_BRANCH="$5"
    if [ -d "${LIB_PATH}" ]; then
        pushd "${LIB_PATH}"
        LIB_HASH=$(git describe --match NOTATAG --always --abbrev=40 --dirty='!')
        popd
    else
        echo "${LIB_PATH} not found! using branch ${LIB_BRANCH} instead"
        LIB_HASH="${LIB_BRANCH}"
    fi
    case "${LIB_HASH}" in *!)
        echo "library ${LIB} at ${LIB_PATH} is dirty!"
        exit 1
    esac
    ${PYTHON} -c "${PY_LIB}" "${REQ_FILE}" "${LIB}" "${LIB_URL}@${LIB_HASH}"
}

cp "requirements.api.txt" "${REQUIREMENTS_API_FILE}"
cp "requirements.worker.txt" "${REQUIREMENTS_WORKER_FILE}"
if [ ! -z "${DEVMODE}" ]; then
    echo "library dev mode active"

    replace_lib "${REQUIREMENTS_API_FILE}" "quick-server" "${QUICK_SERVER_PATH}" "${QUICK_SERVER_URL}" "${QUICK_SERVER_BRANCH}"
    replace_lib "${REQUIREMENTS_API_FILE}" "redipy" "${REDIPY_PATH}" "${REDIPY_URL}" "${REDIPY_BRANCH}"
    replace_lib "${REQUIREMENTS_API_FILE}" "scattermind" "${SMIND_PATH}" "${SMIND_URL}" "${SMIND_BRANCH}"

    replace_lib "${REQUIREMENTS_WORKER_FILE}" "quick-server" "${QUICK_SERVER_PATH}" "${QUICK_SERVER_URL}" "${QUICK_SERVER_BRANCH}"
    replace_lib "${REQUIREMENTS_WORKER_FILE}" "redipy" "${REDIPY_PATH}" "${REDIPY_URL}" "${REDIPY_BRANCH}"
    replace_lib "${REQUIREMENTS_WORKER_FILE}" "scattermind" "${SMIND_PATH}" "${SMIND_URL}" "${SMIND_BRANCH}"
fi

if [ ! -z "${DEV}" ]; then
    DOCKER_COMPOSE_OUT="docker-compose.dev.yml"
    WEBAPP_STORAGE_HOME="./userdata"
    DOCKER_LOGIN_SERVER=
else
    DOCKER_COMPOSE_OUT="docker-compose.yml"
    WEBAPP_STORAGE_HOME=
    DOCKER_LOGIN_SERVER="acclabdocker.azurecr.io/"
fi
DOCKER_COMPOSE_WIPE_OUT="docker-compose.wipe.yml"

docker_build() {
    ARGS=("$@")
    if [ ! -z "${VERBOSE}" ]; then
        ARGS+=("--progress=plain")
    fi
    if [ ! -z "${NO_CACHE}" ]; then
        ARGS+=("--no-cache")
    fi
    _docker_build "${ARGS[@]}"
}

_docker_build() {
    TAG="$1"
    # if ! docker inspect --type=image "${TAG}" &> /dev/null ; then
    shift
    if [ ! -z "${DEV}" ]; then
        docker build -t "${TAG}" "${@}"
    else
        docker buildx build --platform linux/amd64 -t "${TAG}" "${@}"
    fi
    echo "built ${TAG}"
    # else
    #     echo "${TAG} already exists!"
    # fi
}

docker_build \
    "${IMAGE_BASE}-api:${IMAGE_TAG}" \
    --build-arg "REQUIREMENTS_PATH=${REQUIREMENTS_API_FILE}" \
    --build-arg "CONFIG_PATH=${CONFIG_PATH}" \
    --build-arg "SMIND_CONFIG=${SMIND_CFG}" \
    --build-arg "SMIND_GRAPHS=${SMIND_GRS}" \
    --build-arg "PORT=${PORT}" \
    -f deploy/api.Dockerfile \
    .

docker_build \
    "${IMAGE_BASE}-worker:${IMAGE_TAG}" \
    --build-arg "REQUIREMENTS_PATH=${REQUIREMENTS_WORKER_FILE}" \
    --build-arg "SMIND_CONFIG=${SMIND_CFG}" \
    --build-arg "SMIND_GRAPHS=${SMIND_GRS}" \
    -f deploy/worker.Dockerfile \
    .

echo "rmain:${REDIS_DOCKER_VERSION}" > buildtmp/rmain.version

docker_build \
    "${IMAGE_BASE}-rmain:${REDIS_DOCKER_VERSION}" \
    --build-arg "PORT=6379" \
    --build-arg "CFG_FILE=${RMAIN_CFG}" \
    --build-arg "REDIS_VERSION_FILE=buildtmp/rmain.version" \
    --build-arg "REDIS_RUN_SCRIPT=${REDIS_RUN_SCRIPT}" \
    -f deploy/redis.Dockerfile \
    .

echo "rdata:${REDIS_DOCKER_VERSION}" > buildtmp/rdata.version

docker_build \
    "${IMAGE_BASE}-rdata:${REDIS_DOCKER_VERSION}" \
    --build-arg "PORT=6379" \
    --build-arg "CFG_FILE=${RDATA_CFG}" \
    --build-arg "REDIS_VERSION_FILE=buildtmp/rdata.version" \
    --build-arg "REDIS_RUN_SCRIPT=${REDIS_RUN_SCRIPT}" \
    -f deploy/redis.Dockerfile \
    .

echo "rcache:${REDIS_DOCKER_VERSION}" > buildtmp/rcache.version

docker_build \
    "${IMAGE_BASE}-rcache:${REDIS_DOCKER_VERSION}" \
    --build-arg "PORT=6379" \
    --build-arg "CFG_FILE=${RCACHE_CFG}" \
    --build-arg "REDIS_VERSION_FILE=buildtmp/rcache.version" \
    --build-arg "REDIS_RUN_SCRIPT=${REDIS_RUN_SCRIPT}" \
    -f deploy/redis.Dockerfile \
    .

echo "rbody:${REDIS_DOCKER_VERSION}" > buildtmp/rbody.version

docker_build \
    "${IMAGE_BASE}-rbody:${REDIS_DOCKER_VERSION}" \
    --build-arg "PORT=6379" \
    --build-arg "CFG_FILE=${RBODY_CFG}" \
    --build-arg "REDIS_VERSION_FILE=buildtmp/rbody.version" \
    --build-arg "REDIS_RUN_SCRIPT=${REDIS_RUN_SCRIPT}" \
    -f deploy/redis.Dockerfile \
    .

docker_build \
    "${IMAGE_BASE}-wipe:${WIPE_DOCKER_VERSION}" \
    --build-arg "PORT=8080" \
    --build-arg "WIPE_SCRIPT=${WIPE_SCRIPT}" \
    --build-arg "WIPE_RUN_SCRIPT=${WIPE_RUN_SCRIPT}" \
    --build-arg "WIPE_VERSION_FILE=${WIPE_VERSION_FILE}" \
    -f deploy/wipe.Dockerfile \
    .

DEFAULT_ENV_FILE=deploy/default.env
echo "# created by sh/build.sh" > "${DEFAULT_ENV_FILE}"
echo "DOCKER_WORKER=${IMAGE_BASE}-worker:${IMAGE_TAG}" >> "${DEFAULT_ENV_FILE}"
echo "DOCKER_API=${IMAGE_BASE}-api:${IMAGE_TAG}" >> "${DEFAULT_ENV_FILE}"
echo "DOCKER_RMAIN=${IMAGE_BASE}-rmain:${REDIS_DOCKER_VERSION}" >> "${DEFAULT_ENV_FILE}"
echo "DOCKER_RDATA=${IMAGE_BASE}-rdata:${REDIS_DOCKER_VERSION}" >> "${DEFAULT_ENV_FILE}"
echo "DOCKER_RCACHE=${IMAGE_BASE}-rcache:${REDIS_DOCKER_VERSION}" >> "${DEFAULT_ENV_FILE}"
echo "DOCKER_RBODY=${IMAGE_BASE}-rbody:${REDIS_DOCKER_VERSION}" >> "${DEFAULT_ENV_FILE}"
if [ ! -z "${DEV}" ]; then
    echo "DOCKER_QDRANT=qdrant/qdrant:v1.8.0" >> "${DEFAULT_ENV_FILE}"
else
    echo "DOCKER_QDRANT=${IMAGE_BASE}-qdrant:${QDRANT_DOCKER_VERSION}" >> "${DEFAULT_ENV_FILE}"
fi
echo "DOCKER_WIPE=${IMAGE_BASE}-wipe:${WIPE_DOCKER_VERSION}" >> "${DEFAULT_ENV_FILE}"
echo "QDRANT_API_TOKEN=${QDRANT_API_TOKEN}" >> "${DEFAULT_ENV_FILE}"
if [ ! -z "${WEBAPP_STORAGE_HOME}" ]; then
    echo "{WEBAPP_STORAGE_HOME}=${WEBAPP_STORAGE_HOME}" >> "${DEFAULT_ENV_FILE}"
fi

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
            value = f"{prefix}{value}"
        if value.startswith("@"):
            with open(value[1:], "r", encoding="utf-8") as tin:
                value = tin.read()
        substitute[variable] = value
with open(dcompose, "r", encoding="utf-8") as din:
    content = din.read()
for variable, value in sorted(
        substitute.items(), key=lambda e: len(e[0]), reverse=True):
    content = content.replace(variable, value)
with open(dout, "w", encoding="utf-8") as fout:
    fout.write(content)
EOF

${PYTHON} -c "${PY_COMPOSE}" "${DOCKER_LOGIN_SERVER}" "deploy/docker-compose.app.yml" "${DEFAULT_ENV_FILE}" "${DOCKER_COMPOSE_OUT}"
${PYTHON} -c "${PY_COMPOSE}" "${DOCKER_LOGIN_SERVER}" "deploy/docker-compose.wipe.yml" "${DEFAULT_ENV_FILE}" "${DOCKER_COMPOSE_WIPE_OUT}"

echo "docker compose is ready at ${DOCKER_COMPOSE_OUT}"
echo "make sure to call make dockerpush before updating"
echo "wipe is at ${DOCKER_COMPOSE_WIPE_OUT} be careful with it!"
if [ -z "${DEV}" ] && [ -z "${CI}" ]; then
    echo "make sure to set the qdrant api key in your env. example:"
    echo "QDRANT__SERVICE__API_KEY=${QDRANT_API_TOKEN}"
fi
if [ ! -z "${DEV}" ]; then
    echo "run 'make compose' next to start the app on http://localhost:8080/search/"
elif [ -z "${CI}" ]; then
    echo "================================================="
    grep -Ev '^\s*$|^\s*\#' "${DOCKER_COMPOSE_OUT}"
else
    echo "run 'make build' locally (without dockerpush) to get the docker compose file"
fi
