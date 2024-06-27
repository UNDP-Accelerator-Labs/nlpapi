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
set -ex

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

PYTHON="${PYTHON:-python}"
RESULT_FNAME="${RESULT_FNAME:-results.xml}"
IFS=',' read -a FILE_INFO <<< "$1"
FILES=("${FILE_INFO[@]}")
export USER_FILEPATH=./userdata

coverage erase

find . -type d \( \
    -path './venv' -o \
    -path './.*' -o \
    -path './stubs' \
    \) -prune -o \
    -name '*.py' \
    -exec ${PYTHON} -m compileall -q -j 0 {} +

run_test() {
    ${PYTHON} -m pytest \
        -xvv --full-trace \
        --junitxml="test-results/parts/result${2}.xml" \
        --cov --cov-append \
        $1
}
export -f run_test

if ! [ -z "${FILES}" ]; then
    IDX=0
    echo "${FILES[@]}"
    for CUR_TEST in "${FILES[@]}"; do
        run_test $CUR_TEST $IDX
        IDX=$((IDX+1))
    done
else
    IDX=0
    for CUR in $(find 'test' -type d \( \
            -path 'test/data' -o \
            -path 'test/__pycache__' \
            \) -prune -o \( \
            -name '*.py' -and \
            -name 'test_*' \
            \) | \
            grep -E '.*\.py' | \
            sort -sf); do
        run_test ${CUR} $IDX
        IDX=$((IDX+1))
    done
fi
${PYTHON} -m test merge_results --dir test-results --out-fname ${RESULT_FNAME}
rm -r test-results/parts

coverage xml -o coverage/reports/xml_report.xml
coverage html -d coverage/reports/html_report
