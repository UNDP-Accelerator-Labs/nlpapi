#!/usr/bin/env bash

set -e

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

PYTHON="${PYTHON:-python}"
FILE=${1:-requirements.txt}

cat "${FILE}" | sed -E 's/([=~>]=|<=?).+//' | sort -sf | diff -U 1 "requirements.noversion.txt" -
