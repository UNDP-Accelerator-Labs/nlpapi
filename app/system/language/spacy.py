

import collections
import random
from typing import TypedDict

from app.system.spacy import get_lang_detector, LengthCounter


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


def get_raw_lang(text: str, lnc: LengthCounter) -> LangTuple:
    if len(text) > MAX_PROCESSING_SIZE:
        raise ValueError(f"text too long {len(text)} > {MAX_PROCESSING_SIZE}")
    with get_lang_detector() as nlp:
        mdoc = nlp(lnc(text))
        lang = mdoc._.language
    return (f"{lang['language']}", float(lang['score']))


def probe(
        text: str, rng: random.Random | None, lnc: LengthCounter) -> LangTuple:
    pos = 0
    if rng is not None:
        pos = rng.randint(0, max(0, len(text) - MAX_PROCESSING_SIZE))
    probe_text = text[pos:pos + MAX_PROCESSING_SIZE + 1]
    if len(probe_text) > MAX_PROCESSING_SIZE:
        rpos = min(probe_text.rfind(" "), MAX_PROCESSING_SIZE)
        probe_text = probe_text[:rpos]
    return get_raw_lang(probe_text, lnc)


def get_lang(text: str, lnc: LengthCounter) -> LangResponse:
    rng = random.Random()
    res: collections.defaultdict[str, float] = \
        collections.defaultdict(lambda: 0.0)
    counts: collections.Counter[str] = collections.Counter()
    for _ in range(NUM_PROBES):
        lang, score = probe(text, rng, lnc)
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
