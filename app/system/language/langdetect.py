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
import collections
import random
from collections.abc import Iterable
from typing import TypedDict

import langdetect  # type: ignore
from langdetect import detect_langs

from app.system.stats import LengthCounter


MAX_PROCESSING_SIZE = 1000
NUM_PROBES = 10


LangTuple = tuple[str, float]


LangCandidate = TypedDict('LangCandidate', {
    "lang": str,
    "score": float,
    "count": int,
})


LangResponse = TypedDict('LangResponse', {
    "languages": list[LangCandidate],
})


def get_raw_lang(text: str, lnc: LengthCounter) -> Iterable[LangTuple]:
    if len(text) > MAX_PROCESSING_SIZE:
        raise ValueError(f"text too long {len(text)} > {MAX_PROCESSING_SIZE}")
    try:
        for res in detect_langs(lnc(text)):
            yield (f"{res.lang}", float(res.prob))
    except langdetect.lang_detect_exception.LangDetectException:
        pass


def probe(
        text: str,
        rng: random.Random | None,
        lnc: LengthCounter) -> Iterable[LangTuple]:
    pos = 0
    if rng is not None:
        pos = rng.randint(0, max(0, len(text) - MAX_PROCESSING_SIZE))
    probe_text = text[pos:pos + MAX_PROCESSING_SIZE + 1]
    if len(probe_text) > MAX_PROCESSING_SIZE:
        rpos = min(probe_text.rfind(" "), MAX_PROCESSING_SIZE)
        probe_text = probe_text[:rpos]
    yield from get_raw_lang(probe_text, lnc)


def get_lang(text: str, lnc: LengthCounter) -> LangResponse:
    rng = random.Random()
    res: collections.defaultdict[str, float] = \
        collections.defaultdict(lambda: 0.0)
    counts: collections.Counter[str] = collections.Counter()
    total = 0
    for _ in range(NUM_PROBES):
        for lang, score in probe(text, rng, lnc):
            res[lang] += score
            counts[lang] += 1
            total += 1
    return {
        "languages": sorted(
            (
                {
                    "lang": lang,
                    "score": score / total,
                    "count": counts[lang],
                }
                for lang, score in res.items()
            ),
            key=lambda entry: entry["score"],
            reverse=True),
    }
