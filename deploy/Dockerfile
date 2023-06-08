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
RUN pwd
COPY Makefile .
COPY requirements.txt .
RUN mkdir sh
COPY sh/install.sh sh
RUN ls -la
RUN make install
COPY . .
ARG API_SERVER_PORT=8080
ARG CONFIG_PATH
COPY "${CONFIG_PATH}" config.json
ENV API_SERVER_NAMESPACE=default
ENV API_SERVER_HOST=0.0.0.0
ENV API_SERVER_PORT=${API_SERVER_PORT}
EXPOSE ${API_SERVER_PORT}
ENTRYPOINT [ "/bin/bash", "-l", "-c" ]
CMD ["python -u -m app --dedicated"]
