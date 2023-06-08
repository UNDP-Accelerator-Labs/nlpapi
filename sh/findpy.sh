#!/usr/bin/env bash

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

find . -type d \( \
        -path './venv' -o \
        -path './data' -o \
        -path './notebooks' -o \
        -path './.*' \
        \) -prune -o \( \
        -name '*.py' -o \
        -name '*.pyi' \
        \) \
    | grep -vF './venv' \
    | grep -vF './.' \
    | grep -vF './data' \
    | grep -vF './notebooks'
