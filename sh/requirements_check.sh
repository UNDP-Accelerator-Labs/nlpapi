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

PYTHON="${PYTHON:-python}"
FILE=${1:-requirements.txt}

TMP=$(mktemp tmp.XXXXXX)

cat ${FILE} | sed -E 's/(\[[a-z]+\])?//g' > ${TMP}

${PYTHON} -m pip freeze | sort -sf | grep -i -E "^($(cat ${TMP} | sed -E 's/[=~>]=.+//g' | perl -p -e 'chomp if eof' | tr '\n' '|'))=" | diff -U 0 ${TMP} -

rm ${TMP}

echo "NOTE: '+' is your local version and '-' is the version in ${FILE}" 1>&2
