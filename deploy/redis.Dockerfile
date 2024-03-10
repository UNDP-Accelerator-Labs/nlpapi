FROM redis:6.2-alpine
ARG PORT
ARG CFG_FILE
ARG REDIS_VERSION_FILE
COPY "${CFG_FILE}" redis.conf
COPY "${REDIS_VERSION_FILE}" redis.version
ENV PORT=${PORT}
EXPOSE ${PORT}
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["redis-server redis.conf --port ${PORT}"]
