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
remove /qdrant_1
remove /qdrant_2
remove /qdrant_3

echo "done"
