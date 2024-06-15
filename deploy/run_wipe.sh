#!/bin/sh
#
# NLP-API provides useful Natural Language Processing capabilities as API.
# Copyright (C) 2024 UNDP Accelerator Labs, Josua Krause
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
set -e

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
