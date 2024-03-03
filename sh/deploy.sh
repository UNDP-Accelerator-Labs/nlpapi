#!/usr/bin/env bash

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

if ! make -s git-check ; then
    echo "working directory needs to be clean to deploy"
    exit 1
fi

BRANCH_MAIN=main

if [[ $(make -s branch) != "${BRANCH_MAIN}" && $(make -s branch) != v* ]]; then
    echo "must be on ${BRANCH_MAIN} or v* to deploy"
    exit 2
fi

git fetch --tags
TAG=$(make -s next-version)

if [ $(git tag --points-at HEAD) ]; then
    echo "commit is already deployed!"
    exit 3
fi

echo "deploying version: ${TAG}"
git tag "${TAG}"
git push --tags
