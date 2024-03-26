#!/bin/sh

cd "/app/public"
echo "starting server"
nohup python -m http.server -b "${HOST}" -p "${PORT}" &> /app/public/server.txt &

echo "sleep"
sleep 30

echo "starting wipe"
/bin/sh -c /app/wipe.sh 2>&1 | tee /app/public/output.txt || echo "wipe $?"
echo "wipe finished"

while true; do
  sleep 60
done
