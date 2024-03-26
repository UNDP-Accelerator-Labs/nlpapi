#!/bin/sh

set -e

cd "/app/public"
python -m http.server -b "0.0.0.0" -p "${PORT}" &

echo "deleting /smind_cache"
rm -rf /smind_cache
echo "deleting /rbody"
rm -rf /rbody
echo "deleting /rcache"
rm -rf /rcache
echo "deleting /rdata"
rm -rf /rdata
echo "deleting /rmain"
rm -rf /rmain
echo "deleting /qdrant_data"
rm -rf /qdrant_data

echo "done"
while true; do
  sleep 60
done
