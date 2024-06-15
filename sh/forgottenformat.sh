#!/usr/bin/env bash
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
set -ex

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../" &> /dev/null

PYTHON="${PYTHON:-python}"

ANY_DOUBLE="([^\\\\\"]|\\\\\")*"
ANY_SINGLE="([^\\\\']|\\\\')*"
IS_CURLY="([{][^{]|[^}][}])"
EAT_DOUBLE="\"${ANY_DOUBLE}\""
EAT_SINGLE="'${ANY_SINGLE}'"
EAT_STRINGS="^([^\"'#]|${EAT_DOUBLE}|${EAT_SINGLE})*"

INVALID_F_DOUBLE="f\"([^\\\\\"}{]|\\\\\")*\""
INVALID_F_SINGLE="f'([^\\\\'}{]|\\\\')*'"
INVALIDS="${INVALID_F_DOUBLE}|${INVALID_F_SINGLE}"
NO_F_DOUBLE="[^rf]\"${ANY_DOUBLE}${IS_CURLY}${ANY_DOUBLE}\""  # we also allow r
NO_F_SINGLE="'${ANY_SINGLE}${IS_CURLY}${ANY_SINGLE}'"  # we disallow any curls
NO_FS="${NO_F_DOUBLE}|${NO_F_SINGLE}"

MAIN_MATCH="(${NO_FS}|${INVALIDS})"
REGEX="${EAT_STRINGS}${MAIN_MATCH}"
echo ${REGEX}

! read -r -d '' PY_FILTER <<'EOF'
import sys

stdin = sys.stdin
stdout = sys.stdout
is_triple = False
while True:
    line = stdin.readline()
    if not line:
        break
    if line.count('"""') % 2 != 0:
        is_triple = not is_triple
        continue
    if not is_triple:
        stdout.write(line)
        stdout.flush()
EOF

./sh/findpy.sh \
    | xargs grep -nE "['\"]" \
    | ${PYTHON} -c "${PY_FILTER}" \
    | grep -E "${REGEX}" \
    | grep --color=always -nE "${MAIN_MATCH}"
