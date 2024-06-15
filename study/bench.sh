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

GPU="${GPU:-}"
if command -v nvidia-smi &> /dev/null; then
    GPU=1
fi

if [ ! -z "${GPU}" ]; then
    nvidia-smi
fi

echo "warmup"

python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma.json --input 'tell me about the tallest mountain in the world' --output -

echo "bench"

python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma.json --input 'tell me about the tallest mountain in the world' --output -

python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma.json --input @study/prompts/extract/test0.txt --output -

python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma.json --input @study/prompts/extract/ --output -

if [ ! -z "${GPU}" ]; then
    echo "warmup 7B"

    python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma_7bq.json --input 'tell me about the tallest mountain in the world' --output -

    echo "bench 7B"

    python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma_7bq.json --input 'tell me about the tallest mountain in the world' --output -

    python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma_7bq.json --input @study/prompts/extract/test0.txt --output -

    python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma_7bq.json --input @study/prompts/extract/ --output -
fi
