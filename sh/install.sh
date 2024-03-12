#!/usr/bin/env bash

set -ex

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

PYTHON="${PYTHON:-python3}"
which ${PYTHON} > /dev/null
if [ $? -ne 0 ]; then
    PYTHON=python
fi

MAJOR=$(${PYTHON} -c 'import sys; print(sys.version_info.major)')
MINOR=$(${PYTHON} -c 'import sys; print(sys.version_info.minor)')
echo "${PYTHON} v${MAJOR}.${MINOR}"
if [ ${MAJOR} -eq 3 ] && [ ${MINOR} -lt 11 ] || [ ${MAJOR} -lt 3 ]; then
    echo "${PYTHON} version must at least be 3.11" >&2
    exit 1
fi

${PYTHON} -m pip install --progress-bar off --upgrade pip
if [ -z "${MODE}" ]; then
    REQUIREMENTS_PATH="${REQUIREMENTS_PATH:-requirements.txt}"
    ${PYTHON} -m pip install --progress-bar off --upgrade -r "${REQUIREMENTS_PATH}"

    source deploy/devmode.conf
    if [ ! -z "${DEVMODE}" ]; then
        echo "library dev mode active"

        QUICK_SERVER_PATH="../quick_server"
        REDIPY_PATH="../redipy"
        SMIND_PATH="../scattermind"
        ${PYTHON} -m pip uninstall -y quick-server redipy scattermind
        QUICK_SERVER_URL="git+https://github.com/JosuaKrause/quick_server.git"
        REDIPY_URL="git+https://github.com/JosuaKrause/redipy.git"
        SMIND_URL="git+https://github.com/JosuaKrause/scattermind.git"
        if [ -d "${QUICK_SERVER_PATH}" ]; then
            ${PYTHON} -m pip install --upgrade -e "${QUICK_SERVER_PATH}"
        else
            ${PYTHON} -m pip install --upgrade "${QUICK_SERVER_URL}@${QUICK_SERVER_BRANCH}"
        fi
        if [ -d "${REDIPY_PATH}" ]; then
            ${PYTHON} -m pip install --upgrade -e "${REDIPY_PATH}"
        else
            ${PYTHON} -m pip install --upgrade "${REDIPY_URL}@${REDIPY_BRANCH}"
        fi
        if [ -d "${SMIND_PATH}" ]; then
            ${PYTHON} -m pip install --upgrade -e "${SMIND_PATH}"
        else
            ${PYTHON} -m pip install --upgrade "${SMIND_URL}@${SMIND_BRANCH}"
        fi
    fi
elif [ "${MODE}" = "api" ]; then
    REQUIREMENTS_PATH="${REQUIREMENTS_PATH:-requirements.api.txt}"
    ${PYTHON} -m pip install --progress-bar off --no-cache-dir --upgrade -r "${REQUIREMENTS_PATH}"
elif [ "${MODE}" = "worker" ]; then
    REQUIREMENTS_PATH="${REQUIREMENTS_PATH:-requirements.worker.txt}"
    ${PYTHON} -m pip install --progress-bar off --no-cache-dir --upgrade -r "${REQUIREMENTS_PATH}"
else
    echo "invalid mode ${MODE}" >&2
    exit 2
fi

! read -r -d '' PY_TORCH_VERIFY <<'EOF'
import torch

def get_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")

print(f"backend is (cpu|cuda|mps): {get_device()}")
EOF

if ${PYTHON} -c 'import torch;assert torch.__version__.startswith("2.")' &>/dev/null 2>&1; then
    PYTORCH=$(${PYTHON} -c 'import torch;print(torch.__version__)')
    echo "pytorch available: ${PYTORCH}"
    ${PYTHON} -c "${PY_TORCH_VERIFY}"
else
    if [ "${MODE}" = "api" ] || [ "${MODE}" = "worker" ]; then
        echo "should have torch already" >&2
        exit 3
    fi
    if [ ! $CI = "true" ] && command -v conda &>/dev/null 2>&1; then
        conda install -y pytorch torchvision torchaudio -c pytorch
    else
        ${PYTHON} -m pip install --progress-bar off --pre torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/nightly/cpu
    fi
    echo "installed pytorch. it's probably better if you install it yourself"
    echo "for MacOS follow these instructions: https://developer.apple.com/metal/pytorch/"
fi

if [ -z "${MODE}" ] || [ "${MODE}" = "api" ]; then
    echo "initializing spacy"
    # FIXME potentially use xx_ent_wiki_sm (https://spacy.io/models/xx)?
    ${PYTHON} -m spacy download en_core_web_sm
fi
