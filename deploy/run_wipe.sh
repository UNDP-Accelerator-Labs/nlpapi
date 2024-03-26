#!/bin/sh

cd "/app/public"
echo "starting server"
python -m http.server -b "0.0.0.0" -p "${PORT}" &

echo "sleep"
sleep 30

echo "starting wipe"
/bin/sh -c /app/wipe.sh 2>&1 | tee /app/public/output.txt
echo "wipe finished"

while true; do
  sleep 60
done
