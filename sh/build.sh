#!/usr/bin/env bash

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

IMAGE_NAME="smartsearch-$(make -s name)"

echo "building ${IMAGE_NAME}"

docker build --no-cache --progress=plain -t "${IMAGE_NAME}" -f deploy/Dockerfile .

echo "built ${IMAGE_NAME}"
