import re
from collections.abc import Iterable

from app.system.smind.api import get_ner_results_immediate, GraphProfile
from app.system.stats import LengthCounter


Location = tuple[str, int]


MAX_PROCESSING_SIZE = 1000
PROCESSING_GRACE = 50

BOUNDARY = re.compile(r"\b")


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
        graph_profile: GraphProfile,
        text: str,
        lnc: LengthCounter) -> Iterable[tuple[str, int, int]]:
    overlap_ends: list[int] = [0]

    def get_overlap_end(chunk: Location) -> int:
        cur_text, cur_offset = chunk
        return cur_offset + len(cur_text)

    next_offset = 0
    next_text = text
    chunks: list[Location] = []
    while True:
        chunk, remain = next_chunk(next_text, next_offset)
        chunks.append(chunk)
        overlap_ends.append(get_overlap_end(chunk))
        if remain is None:
            break
        next_text, next_offset = remain

    ner_res = get_ner_results_immediate(
        [lnc(chunk_text) for chunk_text, _ in chunks],
        graph_profile=graph_profile)

    next_buff: list[tuple[str, int, int]] = []
    buff: list[tuple[str, int, int]] = []
    for overlap_end, chunk, cur_ners in zip(overlap_ends, chunks, ner_res):
        if cur_ners is None:
            continue
        print(cur_ners)
        next_buff = [
            (text, start, end)
            for text, (start, end) in zip(cur_ners["text"], cur_ners["ranges"])
        ]
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

        buff = next_buff

    yield from next_buff
