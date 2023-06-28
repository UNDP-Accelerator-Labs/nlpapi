import re
from typing import Iterable

import spacy

from app.system.spacy import LengthCounter


Location = tuple[str, int]


MAX_PROCESSING_SIZE = 1000
PROCESSING_GRACE = 50

BOUNDARY = re.compile(r"\b")


def get_raw_locations(
        nlp: spacy.language.Language,
        chunk: Location,
        lnc: LengthCounter) -> Iterable[tuple[str, int, int]]:
    text, offset = chunk
    doc = nlp(lnc(text))
    for ent in doc.ents:
        if ent.label_ not in ["LOC", "GPE"]:
            continue
        yield (ent.text, ent.start_char + offset, ent.end_char + offset)


def next_chunk(text: str, offset: int) -> tuple[Location, Location | None]:
    if len(text) < MAX_PROCESSING_SIZE:
        return (text, offset), None
    bix = MAX_PROCESSING_SIZE
    min_pos = MAX_PROCESSING_SIZE - PROCESSING_GRACE
    max_pos = MAX_PROCESSING_SIZE + PROCESSING_GRACE
    boundary = BOUNDARY.search(f"w{text[min_pos:max_pos]}", 1)
    if boundary is not None:
        bix = min_pos + boundary.start() - 1
    fix = bix + PROCESSING_GRACE
    boundary = BOUNDARY.search(f"w{text[bix:bix + PROCESSING_GRACE][::-1]}", 1)
    if boundary is not None:
        fix = bix + PROCESSING_GRACE - (boundary.start() - 1)
    chunk = text[:fix]
    remain = text[bix:]
    return (chunk, offset), (remain, offset + bix)


def get_locations(
        nlp: spacy.language.Language,
        text: str,
        lnc: LengthCounter) -> Iterable[tuple[str, int, int]]:
    overlap_end = 0

    def get_overlap_end(chunk: Location) -> int:
        cur_text, cur_offset = chunk
        return cur_offset + len(cur_text)

    next_offset = 0
    next_text = text
    buff: list[tuple[str, int, int]] = []
    while True:
        chunk, remain = next_chunk(next_text, next_offset)
        next_buff = list(get_raw_locations(nlp, chunk, lnc))
        overlaps = {
            start
            for (_, start, _) in next_buff
            if start < overlap_end
        }
        yield from (
            hit
            for hit in buff
            if hit[1] not in overlaps
        )
        if remain is None:
            break
        buff = next_buff
        overlap_end = get_overlap_end(chunk)
        next_text, next_offset = remain
    yield from next_buff
