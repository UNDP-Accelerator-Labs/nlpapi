#!/usr/bin/env bash

set -ex

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

PYTHON="${PYTHON:-python}"
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

if ${PYTHON} -c 'import torch;assert torch.__version__.startswith("2.")' &>/dev/null 2>&1; then
    PYTORCH=$(${PYTHON} -c 'import torch;print(torch.__version__)')
    echo "pytorch available: ${PYTORCH}"
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

if [ -z "${MODE}" ] || [ "${MODE}" = "worker" ]; then
    echo "initializing spacy"
    ${PYTHON} -m spacy download en_core_web_sm
    ${PYTHON} -m spacy download xx_ent_wiki_sm
fi

! read -r -d '' PY_TORCH_VERIFY <<'EOF'
import sys
import torch

def get_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    # if torch.cuda.is_available():
    if torch.backends.cudnn.enabled:
        return torch.device("cuda")
    return torch.device("cpu")

options = []
device_name = f"{get_device()}"
if device_name == "mps":
    options.append("-DLLAMA_METAL=on")
elif device_name == "cuda":
    options.append("-DLLAMA_CUDA=on")
elif device_name == "cpu":
    options.append("-DLLAMA_BLAS=ON")
    options.append("-DLLAMA_BLAS_VENDOR=OpenBLAS")
sys.stdout.write(" ".join(options))
sys.stdout.flush()
EOF

LLAMA_CMAKE_ARGS=$(${PYTHON} -c "${PY_TORCH_VERIFY}")
if [ ! -z "${FORCE_CUDA}" ]; then
    LLAMA_CMAKE_ARGS="-DLLAMA_CUDA=on"
elif [ ! -z "${FORCE_CPU}" ]; then
    LLAMA_CMAKE_ARGS=
fi

if grep -q "METAL" <<< "${LLAMA_CMAKE_ARGS}"; then
    ${PYTHON} -m pip install llama-cpp-python==0.2.68 --extra-index-url "https://abetlen.github.io/llama-cpp-python/whl/metal"
elif grep -q "CUDA" <<< "${LLAMA_CMAKE_ARGS}"; then
    CUDA_VERSION_SHORT="${CUDA_VERSION_SHORT:-cu121}"
    if [ ! -z "${FORCE_BUILD_LLAMA}" ]; then
        CUDACXX=nvcc CMAKE_ARGS="-DLLAMA_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=all-major" FORCE_CMAKE=1 \
            ${PYTHON} -m pip install llama-cpp-python==0.2.68 --no-cache-dir --force-reinstall --upgrade
    else
        ${PYTHON} -m pip install llama-cpp-python --prefer-binary --no-cache-dir --extra-index-url "https://abetlen.github.io/llama-cpp-python/whl/${CUDA_VERSION_SHORT}"
        # ${PYTHON} -m pip install llama-cpp-python --prefer-binary --no-cache-dir --extra-index-url "https://jllllll.github.io/llama-cpp-python-cuBLAS-wheels/AVX2/${CUDA_VERSION_SHORT}"
    fi
else
    CMAKE_ARGS="${LLAMA_CMAKE_ARGS}" ${PYTHON} -m pip install --progress-bar off llama-cpp-python==0.2.68
fi
