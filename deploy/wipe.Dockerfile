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
COPY "${REDIS_VERSION_FILE}" /app/public/version/index.html
COPY "${WIPE_RUN_SCRIPT}" /app/run_wipe.sh
ARG PORT=8080
ENV HOST=0.0.0.0
ENV PORT=${PORT}
EXPOSE ${PORT}
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["/app/run_redis.sh"]
