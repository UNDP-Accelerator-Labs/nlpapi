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
COPY Makefile .
COPY requirements.txt .
RUN mkdir sh
COPY sh/install.sh sh
RUN make install
COPY . .
ARG PORT=8080
ARG CONFIG_PATH
COPY "${CONFIG_PATH}" config.json
ENV API_SERVER_NAMESPACE=default
ENV HOST=0.0.0.0
ENV PORT=${PORT}
EXPOSE ${PORT}
ENTRYPOINT [ "/bin/bash", "-l", "-c" ]
CMD ["python -u -m app --dedicated"]
