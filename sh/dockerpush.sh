#!/usr/bin/env bash

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

IMAGE_TAG="${IMAGE_TAG:-$(make -s name)}"
IMAGE_NAME="nlpapi:${IMAGE_TAG}"
DOCKER_LOGIN_SERVER="acclabdocker.azurecr.io"

DOCKER_WORKER="${IMAGE_NAME}-worker"
DOCKER_API="${IMAGE_NAME}-api"
DOCKER_RMAIN="${IMAGE_NAME}-rmain"
DOCKER_RDATA="${IMAGE_NAME}-rdata"
DOCKER_RCACHE="${IMAGE_NAME}-rcache"

DOCKER_WORKER_URL="${DOCKER_LOGIN_SERVER}/${DOCKER_WORKER}"
DOCKER_API_URL="${DOCKER_LOGIN_SERVER}/${DOCKER_API}"
DOCKER_RMAIN_URL="${DOCKER_LOGIN_SERVER}/${DOCKER_RMAIN}"
DOCKER_RDATA_URL="${DOCKER_LOGIN_SERVER}/${DOCKER_RDATA}"
DOCKER_RCACHE_URL="${DOCKER_LOGIN_SERVER}/${DOCKER_RCACHE}"

echo "pushing ${DOCKER_WORKER} to ${DOCKER_WORKER_URL}"

docker tag "${DOCKER_WORKER}" "${DOCKER_WORKER_URL}"
docker push "${DOCKER_WORKER_URL}"
docker rmi "${DOCKER_WORKER_URL}"

echo "pushing ${DOCKER_API} to ${DOCKER_API_URL}"

docker tag "${DOCKER_API}" "${DOCKER_API_URL}"
docker push "${DOCKER_API_URL}"
docker rmi "${DOCKER_API_URL}"

echo "pushing ${DOCKER_RMAIN} to ${DOCKER_RMAIN_URL}"

docker tag "${DOCKER_RMAIN}" "${DOCKER_RMAIN_URL}"
docker push "${DOCKER_RMAIN_URL}"
docker rmi "${DOCKER_RMAIN_URL}"

echo "pushing ${DOCKER_RDATA} to ${DOCKER_RDATA_URL}"

docker tag "${DOCKER_RDATA}" "${DOCKER_RDATA_URL}"
docker push "${DOCKER_RDATA_URL}"
docker rmi "${DOCKER_RDATA_URL}"

echo "pushing ${DOCKER_RCACHE} to ${DOCKER_RCACHE_URL}"

docker tag "${DOCKER_RCACHE}" "${DOCKER_RCACHE_URL}"
docker push "${DOCKER_RCACHE_URL}"
docker rmi "${DOCKER_RCACHE_URL}"
