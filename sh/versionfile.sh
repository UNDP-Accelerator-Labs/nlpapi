#!/usr/bin/env bash

set -e

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

make -s name > version.txt
make -s commit >> version.txt
date +"%Y-%m-%dT%H:%M:%S%z" >> version.txt
