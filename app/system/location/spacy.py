import re
from collections.abc import Iterable

from app.system.prep.snippify import Location, snippify_text
from app.system.smind.api import get_ner_results_immediate, GraphProfile
from app.system.stats import LengthCounter


MAX_PROCESSING_SIZE = 1000
PROCESSING_GRACE = 50

BOUNDARY = re.compile(r"\b")


def get_locations(
        graph_profile: GraphProfile,
        text: str,
        lnc: LengthCounter) -> Iterable[tuple[str, int, int]]:
    overlap_ends: list[int] = [0]

    def get_overlap_end(chunk: Location) -> int:
        cur_text, cur_offset = chunk
        return cur_offset + len(cur_text)

    chunks: list[Location] = []
    for chunk in snippify_text(
            text,
            chunk_size=MAX_PROCESSING_SIZE,
            chunk_padding=PROCESSING_GRACE):
        chunks.append(chunk)
        overlap_ends.append(get_overlap_end(chunk))

    ner_res = get_ner_results_immediate(
        [lnc(chunk_text) for chunk_text, _ in chunks],
        graph_profile=graph_profile)

    next_buff: list[tuple[str, int, int]] = []
    buff: list[tuple[str, int, int]] = []
    for overlap_end, chunk, cur_ners in zip(overlap_ends, chunks, ner_res):
        if cur_ners is None:
            continue
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
