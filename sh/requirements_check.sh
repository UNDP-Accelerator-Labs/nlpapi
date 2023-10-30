#!/usr/bin/env bash

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

PYTHON="${PYTHON:-python3}"
FILE=${1:-requirements.txt}

TMP=$(mktemp tmp.XXXXXX)

cat ${FILE} | sed -E 's/(\[[a-z]+\])?//g' > ${TMP}

${PYTHON} -m pip freeze | sort -sf | grep -i -E "^($(cat ${TMP} | sed -E 's/[=~>]=.+//g' | perl -p -e 'chomp if eof' | tr '\n' '|'))=" | diff -U 0 ${TMP} -

rm ${TMP}

echo "NOTE: '+' is your local version and '-' is the version in ${FILE}" 1>&2
