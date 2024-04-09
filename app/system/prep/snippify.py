import re
from collections.abc import Iterable


Location = tuple[str, int]


MAX_PROCESSING_SIZE = 1000
PROCESSING_GRACE = 50

BOUNDARY = re.compile(r"\b")


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
    while True:
        chunk, remain = next_chunk(
            next_loc,
            chunk_size=chunk_size,
            chunk_padding=chunk_padding,
            boundary_re=boundary_re)
        yield chunk
        if remain is None:
            break
        next_loc = remain
