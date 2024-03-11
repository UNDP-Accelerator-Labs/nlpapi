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
RUN pip install --progress-bar off --no-cache-dir 'torch~=2.2.0' torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
COPY Makefile .
ARG REQUIREMENTS_PATH
COPY "${REQUIREMENTS_PATH}" "requirements.docker.txt"
RUN mkdir sh
COPY sh/install.sh sh
RUN REQUIREMENTS_PATH="requirements.docker.txt" make install-api
COPY . .
ARG PORT=8080
ARG CONFIG_PATH
ARG SMIND_GRAPHS
ARG SMIND_CONFIG
COPY "${SMIND_CONFIG}" smind-config.json
COPY "${SMIND_GRAPHS}" graphs/
COPY "${CONFIG_PATH}" config.json
ENV API_SERVER_NAMESPACE=default
ENV HOST=0.0.0.0
ENV PORT=${PORT}
ENV SMIND_CFG=smind-config.json
ENV GRAPH_PATH=graphs/
ENV CONFIG_PATH=config.json
EXPOSE ${PORT}
ENTRYPOINT ["/bin/bash", "-l", "-c"]
CMD ["python -u -m app --dedicated"]
