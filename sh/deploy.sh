#!/usr/bin/env bash
#
# NLP-API provides useful Natural Language Processing capabilities as API.
# Copyright (C) 2024 UNDP Accelerator Labs, Josua Krause
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
set -e

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
