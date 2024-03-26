#!/bin/sh

set -e

remove() {
  echo "plan for deleting $1:"
  find "$1" ! -name "$1" -a -prune
  echo "remove:"
  find "$1" ! -name "$1" -a -prune -exec rm -rfv -- {} +
}

remove /smind_cache
remove /rbody
remove /rcache
remove /rdata
remove /rmain
remove /qdrant_data

echo "done"
