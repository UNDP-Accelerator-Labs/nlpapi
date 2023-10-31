import contextlib
from collections.abc import Iterator
from typing import Literal

import spacy
from spacy.language import Language


LanguageStr = Literal["en"]
LANGUAGES: dict[LanguageStr, str] = {
    "en": "en_core_web_sm",
}

SPACY_LANG: str | None = None
SPACY_NLP: Language | None = None


def load_language(language: LanguageStr) -> Language:
    lang = LANGUAGES.get(language)
    if lang is None:
        raise ValueError(
            f"unknown language ({sorted(LANGUAGES.keys())}): {language}")
    return spacy.load(lang)


@contextlib.contextmanager
def get_spacy(language: LanguageStr) -> Iterator[spacy.language.Language]:
    global SPACY_NLP  # pylint: disable=global-statement
    global SPACY_LANG  # pylint: disable=global-statement

    if language != SPACY_LANG or SPACY_NLP is None:
        SPACY_NLP = load_language(language)
        SPACY_LANG = language
    yield SPACY_NLP
