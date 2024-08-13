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
"""Location NER."""
import re
from collections.abc import Iterable

from app.system.prep.snippify import Location, snippify_text
from app.system.smind.api import get_ner_results_immediate, GraphProfile
from app.system.stats import LengthCounter


MAX_PROCESSING_SIZE = 1000
"""Processing chunk size."""
PROCESSING_GRACE = 50
"""Chunk overlap."""

BOUNDARY = re.compile(r"\b")
"""Regex for word boundaries."""


def get_locations(
        graph_profile: GraphProfile,
        text: str,
        lnc: LengthCounter) -> Iterable[tuple[str, int, int]]:
    """
    Gets all detected locations in the given text.

    Args:
        graph_profile (GraphProfile): The NER model.
        text (str): The text to process.
        lnc (LengthCounter): The length counter.

    Yields:
        tuple[str, int, int]: Tuple of entity text and start and end index.
    """
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
