#!/usr/bin/env bash

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

DOCKER_REGISTRY="acclabdockereu"

az login
az acr login --name "${DOCKER_REGISTRY}"
