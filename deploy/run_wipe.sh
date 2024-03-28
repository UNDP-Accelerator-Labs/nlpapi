#!/bin/sh

echo "starting server"
python -m http.server -b "${HOST}" -d "/app/public" "${PORT}" &

echo "sleep"
sleep 30

echo "starting wipe"
/bin/sh -c /app/wipe.sh 2>&1 | tee /app/public/output.txt || echo "wipe $?"
echo "wipe finished"

while true; do
  sleep 60
done
