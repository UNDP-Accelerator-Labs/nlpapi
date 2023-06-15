#!/usr/bin/env bash

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

if ! make -s git-check ; then
    echo "working directory needs to be clean to deploy"
    exit 1
fi

BRANCH_MAIN=main

if [ $(make -s branch) != "${BRANCH_MAIN}" ]; then
    echo "must be on ${BRANCH_MAIN} to deploy"
    exit 2
fi

IMAGE_TAG=$(make -s next-version)

echo "building for version: ${IMAGE_TAG}"

CONFIG_PATH=- IMAGE_TAG=IMAGE_TAG make -s build
make -s azlogin
IMAGE_TAG=IMAGE_TAG make -s dockerpush
