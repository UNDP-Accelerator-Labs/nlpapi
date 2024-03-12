FROM redis:7.2.4
ARG PORT
ARG CFG_FILE
ARG REDIS_VERSION_FILE
ARG REDIS_RUN_SCRIPT
COPY "${CFG_FILE}" /app/redis.conf
COPY "${REDIS_VERSION_FILE}" /app/redis.version
COPY "${REDIS_RUN_SCRIPT}" /app/run_redis.sh
ENV PORT=${PORT}
EXPOSE ${PORT}
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["/app/run_redis.sh"]
