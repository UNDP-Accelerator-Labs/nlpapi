#!/usr/bin/env bash

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

IMAGE_TAG="${IMAGE_TAG:-$(make -s name)}"
IMAGE_NAME="nlpapi:${IMAGE_TAG}"
DOCKER_LOGIN_SERVER="acclabdocker.azurecr.io"
PYTHON="${PYTHON:-python3}"

dpush() {
    IMAGE="${IMAGE_NAME}-$1"
    URL="${DOCKER_LOGIN_SERVER}/${IMAGE}"
    echo "pushing ${IMAGE} to ${URL}"

    docker tag "${IMAGE}" "${URL}"
    docker push "${URL}"
    docker rmi "${URL}"
}

dpush "worker"
dpush "api"
dpush "rmain"
dpush "rdata"
dpush "rcache"

! read -r -d '' PY_COMPOSE <<'EOF'
import os
import sys

prefix = sys.argv[1]
dcompose = sys.argv[2]
denv = sys.argv[3]
dout = sys.argv[4]
substitute = {}
with open(denv, "r", encoding="utf-8") as fin:
    for line in fin:
        line = line.rstrip().split("#", 1)[0].strip()
        if not line:
            continue
        variable, value = line.split("=", 1)
        substitute[f"${variable}".strip()] = f"{prefix}/{value.strip()}"
with open(dcompose, "r", encoding="utf-8") as din:
    content = din.read()
for variable, value in sorted(
        substitute.items(), key=lambda e: len(e[0]), reverse=True):
    content = content.replace(variable, value)
with open(dout, "w", encoding="utf-8") as fout:
    fout.write(content)
EOF

${PYTHON} -c "${PY_COMPOSE}" "${DOCKER_LOGIN_SERVER}" "deploy/docker-compose.yml" "deploy/default.env" "docker-compose.yml"
