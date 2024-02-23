#!/usr/bin/env bash

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

PYTHON="${PYTHON:-python3}"
FILE=${1:-requirements.txt}

cat "${FILE}" | sed -E 's/([=~>]=|<=?).+//' | sort -sf | diff -U 1 "requirements.noversion.txt" -
