FROM continuumio/miniconda3
RUN apt-get update && apt-get -y upgrade \
  && apt-get install -y --no-install-recommends \
    git \
    libpq-dev \
    gcc \
    linux-libc-dev \
    libc6-dev \
    make
WORKDIR /usr/src/app
# NOTE: change to cuda image once we move to GPU
RUN pip install --progress-bar off --no-cache-dir torch~=2.2.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
COPY Makefile .
COPY requirements.worker.txt .
RUN mkdir sh
COPY sh/install.sh sh
RUN make install-worker
COPY . .
ARG SMIND_GRAPHS
ARG SMIND_CONFIG
COPY "${SMIND_CONFIG}" smind-config.json
COPY "${SMIND_GRAPHS}" graphs/
ENTRYPOINT ["/bin/bash", "-l", "-c"]
CMD ["python -m scattermind --config smind-config.json worker --graph graphs/"]
