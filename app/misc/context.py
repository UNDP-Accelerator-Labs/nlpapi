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
import re


CONTEXT_SIZE = 20
CONTEXT_MAX_EXPAND = 10
CONTEXT_END = re.compile(r"\b")
CONTEXT_START = re.compile(r"\b")
ELLIPSIS = "…"


def get_context(text: str, start: int, stop: int) -> str:
    orig_start = start
    orig_stop = stop
    start = max(start - CONTEXT_SIZE, 0)
    stop += CONTEXT_SIZE
    end = CONTEXT_END.search(f"w{text[stop:stop + CONTEXT_MAX_EXPAND]}", 1)
    if end is not None:
        stop += end.start() - 1
    from_start = max(start - CONTEXT_MAX_EXPAND, 0)
    rev = text[from_start:start][::-1]
    front = CONTEXT_START.search(f"w{rev}", 1)
    if front is not None:
        start -= front.start() - 1
    if start == 1:
        start = 0
    if stop == len(text) - 1:
        stop = len(text)
    pre = ELLIPSIS if start > 0 else ""
    post = ELLIPSIS if stop < len(text) else ""
    return (
        f"{pre}{text[start:orig_start]}"
        f"*{text[orig_start:orig_stop]}*"
        f"{text[orig_stop:stop]}{post}")
