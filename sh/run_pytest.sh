#!/usr/bin/env bash

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
