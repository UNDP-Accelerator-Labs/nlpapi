#!/usr/bin/env bash

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

IMAGE_TAG="${IMAGE_TAG:-$(make -s name)}"
IMAGE_NAME="nlpapi:${IMAGE_TAG}"
DOCKER_LOGIN_SERVER="acclabdocker.azurecr.io"

dpush() {
    IMAGE="${IMAGE_NAME}-$1"
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
