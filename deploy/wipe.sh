#!/bin/sh

set -e

remove() {
  echo "plan for deleting $1:"
  find "$1" ! -wholename "$1" -a -prune
  echo "remove:"
  find "$1" ! -wholename "$1" -a -prune -exec rm -rfv -- {} +
}

remove /smind_cache
remove /rbody
remove /rcache
remove /rdata
remove /rmain
remove /qdrant_data
remove /qdrant_1
remove /qdrant_2

echo "done"
