#!/usr/bin/env bash

set -ex

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

GPU="${GPU:-}"
if command -v nvidia-smi &> /dev/null; then
    GPU=1
fi

if [ ! -z "${GPU}" ]; then
    nvidia-smi
fi

python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma.json --input 'tell me about the tallest mountain in the world' --output -

python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma.json --input @study/prompts/extract/test0.txt --output -

python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma.json --input @study/prompts/extract/ --output -

if [ ! -z "${GPU}" ]; then
    python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma_7bq.json --input @study/prompts/extract/test0.txt --output -

    python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma_7bq.json --input @study/prompts/extract/ --output -
fi
