#!/bin/sh

set -e

echo "deleting /smind_cache"
rm -rfv /smind_cache
echo "deleting /rbody"
rm -rfv /rbody
echo "deleting /rcache"
rm -rfv /rcache
echo "deleting /rdata"
rm -rfv /rdata
echo "deleting /rmain"
rm -rfv /rmain
echo "deleting /qdrant_data"
rm -rfv /qdrant_data

echo "done"
