#!/usr/bin/env bash

set -ex

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

PYTHON="${PYTHON:-python}"
STUBGEN="${STUBGEN:-stubgen}"
OUTPUT="${OUTPUT:-stubs}"
FORCE="${FORCE:-}"
PACKAGE="${1}"
FULL_OUTPUT="${OUTPUT}/${PACKAGE}"
TMP_FILE="~tmp"
STUBGEN_HEAD="stubgen.head"

if [ -z "${PACKAGE}" ]; then
    echo "usage: ${0} <package>"
    exit 1
fi

if [ -d "${FULL_OUTPUT}" ]; then
    if [ -z "${FORCE}" ]; then
        echo "output exists! aborting.. set FORCE=1 to overwrite"
        exit 1
    else
        echo "removing existing output"
        rm -r "${FULL_OUTPUT}"
    fi
fi

${STUBGEN} -p "${PACKAGE}" -o "${OUTPUT}"

if [ -f "${TMP_FILE}" ]; then
    echo "${TMP_FILE} already exists! cannot use as tmp file"
    exit 1
fi

find "${FULL_OUTPUT}" -name '*.pyi' \
    -exec echo \
        "mv {} ${TMP_FILE}" \
        "&& cp ${STUBGEN_HEAD} {}" \
        "&& ${PYTHON} stubgen.py ${TMP_FILE} {}" \
        "&& rm ${TMP_FILE}" \; \
    | sh
