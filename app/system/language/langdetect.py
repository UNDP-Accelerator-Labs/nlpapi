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
    for _ in range(NUM_PROBES):
        for lang, score in probe(text, rng, lnc):
            res[lang] += score
            counts[lang] += 1
    return {
        "languages": sorted(
            (
                {
                    "lang": lang,
                    "score": score / NUM_PROBES,
                    "count": counts[lang],
                }
                for lang, score in res.items()
            ),
            key=lambda entry: entry["score"],
            reverse=True),
    }
