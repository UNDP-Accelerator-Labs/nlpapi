#!/usr/bin/env bash

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

IMAGE_NAME="smartsearch:$(make -s name)"
DOCKER_LOGIN_SERVER="acclabdocker.azurecr.io"
DOCKER_IMAGE_URL="${DOCKER_LOGIN_SERVER}/${IMAGE_NAME}"

docker tag "${IMAGE_NAME}" "${DOCKER_IMAGE_URL}"
docker push "${DOCKER_IMAGE_URL}"
docker rmi "${DOCKER_IMAGE_URL}"
