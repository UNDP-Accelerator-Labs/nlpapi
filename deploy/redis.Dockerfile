FROM redis:6.2-alpine
ARG PORT
ARG CFG_FILE
COPY "${CFG_FILE}" redis.conf
ENV PORT=${PORT}
EXPOSE ${PORT}
ENTRYPOINT [ "/bin/bash", "-l", "-c" ]
CMD ["redis-server redis.conf --port ${PORT}"]
