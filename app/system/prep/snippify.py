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
from collections.abc import Iterable


Location = tuple[str, int]


MAX_PROCESSING_SIZE = 1000
PROCESSING_GRACE = 50

BOUNDARY = re.compile(r"\b")
FRONT = re.compile(r"^[\W_]+", re.UNICODE)


def next_chunk(
        start: Location,
        *,
        chunk_size: int,
        chunk_padding: int,
        boundary_re: re.Pattern) -> tuple[Location, Location | None]:
    text, offset = start
    if len(text) < chunk_size:
        return (text, offset), None
    bix = chunk_size
    min_pos = chunk_size - chunk_padding
    max_pos = chunk_size + chunk_padding
    boundary = boundary_re.search(f"w{text[min_pos:max_pos]}", 1)
    if boundary is not None:
        bix = min_pos + boundary.start() - 1
    fix = bix + chunk_padding
    boundary = boundary_re.search(f"w{text[bix:bix + chunk_padding][::-1]}", 1)
    if boundary is not None:
        fix = bix + chunk_padding - (boundary.start() - 1)
    chunk = text[:fix]
    remain = text[bix:]
    return (chunk, offset), (remain, offset + bix)


def snippify_text(
        text: str,
        *,
        chunk_size: int,
        chunk_padding: int) -> Iterable[Location]:
    next_loc = (text, 0)
    boundary_re = BOUNDARY
    front_re = FRONT
    while True:
        chunk, remain = next_chunk(
            next_loc,
            chunk_size=chunk_size,
            chunk_padding=chunk_padding,
            boundary_re=boundary_re)
        yield post_process(chunk, front_re=front_re)
        if remain is None:
            break
        next_loc = remain


def post_process(loc: Location, *, front_re: re.Pattern) -> Location:
    text, offset = loc
    short_text = front_re.sub("", text)
    offset += len(text) - len(short_text)
    return (short_text.rstrip(), offset)
