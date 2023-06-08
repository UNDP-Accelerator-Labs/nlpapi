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
ENTRYPOINT [ "/bin/bash", "-l", "-c" ]
EXPOSE 8080
CMD ["make run-api"]
