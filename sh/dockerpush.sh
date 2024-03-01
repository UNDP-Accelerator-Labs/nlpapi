#!/usr/bin/env bash

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

IMAGE_TAG="${IMAGE_TAG:-$(make -s name)}"
IMAGE_NAME="nlpapi:${IMAGE_TAG}"
DOCKER_LOGIN_SERVER="acclabdocker.azurecr.io"

DOCKER_WORKER="${IMAGE_NAME}-worker"
DOCKER_API="${IMAGE_NAME}-api"

DOCKER_WORKER_URL="${DOCKER_LOGIN_SERVER}/${DOCKER_WORKER}"
DOCKER_API_URL="${DOCKER_LOGIN_SERVER}/${DOCKER_API}"

echo "pushing ${DOCKER_WORKER} to ${DOCKER_WORKER_URL}"

docker tag "${DOCKER_WORKER}" "${DOCKER_WORKER_URL}"
docker push "${DOCKER_WORKER_URL}"
docker rmi "${DOCKER_WORKER_URL}"

echo "pushing ${DOCKER_API} to ${DOCKER_API_URL}"

docker tag "${DOCKER_API}" "${DOCKER_API_URL}"
docker push "${DOCKER_API_URL}"
docker rmi "${DOCKER_API_URL}"
