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

start_redis() {
    pushd "$1"
    redis-server "redis.conf" --port "$2" >> "redis.log" 2>&1 &
    popd
}

start_redis rmain 6381 &
start_redis rdata 6383 &
start_redis rcache 6382 &

DEVICE=auto
# DEVICE="${DEVICE:-cpu}"
# if command -v nvidia-smi &> /dev/null; then
#     DEVICE=auto
# fi

cd ..
if [ "${DEVICE}" = "auto" ]; then
    exec python -u -m scattermind --config study/config.json worker --graph study/graphs/
else
    exec python -u -m scattermind --config study/config.json --device "${DEVICE}" worker --graph study/graphs/
fi
