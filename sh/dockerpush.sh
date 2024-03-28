#!/usr/bin/env bash

set -e

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

IMAGE_TAG="${IMAGE_TAG:-$(make -s name)}"
IMAGE_BASE="nlpapi"
DOCKER_LOGIN_SERVER="acclabdocker.azurecr.io"

DEVMODE_CONF_FILE="deploy/devmode.conf"
REDIS_VERSION_FILE="deploy/redis.version"
QDRANT_VERSION_FILE="deploy/qdrant.version"
WIPE_VERSION_FILE="deploy/wipe.version"

source "${DEVMODE_CONF_FILE}"
source "${REDIS_VERSION_FILE}"
source "${QDRANT_VERSION_FILE}"
source "${WIPE_VERSION_FILE}"

if [ ! -z "${DEVMODE}" ]; then
    QDRANT_DOCKER_VERSION="${QDRANT_DOCKER_VERSION}-devmode"
    REDIS_DOCKER_VERSION="${REDIS_DOCKER_VERSION}-devmode"
    WIPE_DOCKER_VERSION="${WIPE_DOCKER_VERSION}-devmode"
fi

dpush() {
    IMAGE="${IMAGE_BASE}-$1:$2"
    URL="${DOCKER_LOGIN_SERVER}/${IMAGE}"
    if ! docker pull "${URL}" &> /dev/null ; then
        echo "pushing ${IMAGE} to ${URL}"

        docker tag "${IMAGE}" "${URL}"
        docker push "${URL}"
        docker rmi "${URL}"
        sleep 1
    else
        echo "${URL} already exists"
    fi
}

dpush "worker" "${IMAGE_TAG}"
dpush "api" "${IMAGE_TAG}"
dpush "rmain" "${REDIS_DOCKER_VERSION}"
dpush "rdata" "${REDIS_DOCKER_VERSION}"
dpush "rcache" "${REDIS_DOCKER_VERSION}"
dpush "rbody" "${REDIS_DOCKER_VERSION}"
dpush "wipe" "${WIPE_DOCKER_VERSION}"

QDRANT_BASE="qdrant/qdrant:v1.8.0"
docker pull --platform linux/amd64 "${QDRANT_BASE}"

IMAGE_QDRANT="${IMAGE_BASE}-qdrant:${QDRANT_DOCKER_VERSION}"
URL_QDRANT="${DOCKER_LOGIN_SERVER}/${IMAGE_QDRANT}"
if ! docker pull "${URL_QDRANT}" &> /dev/null ; then
    echo "pushing ${QDRANT_BASE} to ${URL_QDRANT}"

    docker tag "${QDRANT_BASE}" "${URL_QDRANT}"
    docker push "${URL_QDRANT}"
    docker rmi "${URL_QDRANT}"
else
    echo "${URL_QDRANT} already exists"
fi
