#!/bin/sh

set -e

remove() {
  find "$1" ! -name "$1" -a -prune -exec rm -rfv -- {} +
}

echo "deleting /smind_cache"
remove /smind_cache
echo "deleting /rbody"
remove /rbody
echo "deleting /rcache"
remove /rcache
echo "deleting /rdata"
remove /rdata
echo "deleting /rmain"
remove /rmain
echo "deleting /qdrant_data"
remove /qdrant_data

echo "done"
