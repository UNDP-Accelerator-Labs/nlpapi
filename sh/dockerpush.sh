#!/usr/bin/env bash

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

IMAGE_TAG="${IMAGE_TAG:-$(make -s name)}"
IMAGE_BASE="nlpapi"
DOCKER_LOGIN_SERVER="acclabdocker.azurecr.io"

dpush() {
    IMAGE="${IMAGE_BASE}-$1:${IMAGE_TAG}"
    URL="${DOCKER_LOGIN_SERVER}/${IMAGE}"
    echo "pushing ${IMAGE} to ${URL}"

    docker tag "${IMAGE}" "${URL}"
    docker push "${URL}"
    docker rmi "${URL}"
}

dpush "worker"
dpush "api"
dpush "rmain"
dpush "rdata"
dpush "rcache"

QDRANT_BASE="qdrant/qdrant:v1.8.0"
docker pull --platform linux/amd64 "${QDRANT_BASE}"

IMAGE_QDRANT="${IMAGE_BASE}-qdrant:${IMAGE_TAG}"
URL="${DOCKER_LOGIN_SERVER}/${IMAGE_QDRANT}"
echo "pushing ${QDRANT_BASE} to ${URL}"

docker tag "${QDRANT_BASE}" "${URL}"
docker push "${URL}"
docker rmi "${URL}"
