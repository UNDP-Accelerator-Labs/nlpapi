FROM continuumio/miniconda3:24.1.2-0
RUN apt-get update && apt-get -y upgrade \
  && apt-get install -y --no-install-recommends \
    build-essential \
    manpages-dev \
    software-properties-common \
    git \
    libpq-dev \
    gcc \
    linux-libc-dev \
    libc6-dev \
    make
WORKDIR /usr/src/app
# FIXME: change to cuda image once we move to GPU
RUN pip install --progress-bar off --no-cache-dir 'torch~=2.2.0' torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
COPY Makefile .
ARG REQUIREMENTS_PATH
COPY "${REQUIREMENTS_PATH}" "requirements.docker.txt"
RUN mkdir sh
COPY sh/install.sh sh
RUN FORCE_CPU="1" REQUIREMENTS_PATH="requirements.docker.txt" make install-worker
COPY LICENSE .
COPY sh/ sh/
COPY nlpapi/ nlpapi/
RUN python -m compileall .
COPY version.txt .
ARG SMIND_GRAPHS
ARG SMIND_CONFIG
COPY "${SMIND_CONFIG}" smind-config.json
COPY "${SMIND_GRAPHS}" graphs/
HEALTHCHECK --interval=30s --timeout=30s --start-period=20s --retries=3 CMD ["/bin/bash", "-l", "-c", "python -u -m scattermind --config smind-config.json healthcheck"]
ENTRYPOINT ["/bin/bash", "-l", "-c"]
CMD ["python -u -m scattermind --boot --version-file version.txt --config smind-config.json worker --graph graphs/ --max-task-retries 2"]
