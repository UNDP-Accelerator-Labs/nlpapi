#!/bin/sh

set -e

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
