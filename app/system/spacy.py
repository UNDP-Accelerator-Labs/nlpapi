import contextlib
from typing import Callable, Iterator, Literal

import spacy
from spacy.language import Language
from spacy_language_detection import LanguageDetector  # type: ignore


LanguageStr = Literal["en"]
LANGUAGES: dict[LanguageStr, str] = {
    "en": "en_core_web_sm",
}

SPACY_LANG: str | None = None
SPACY_NLP: Language | None = None
SPACY_LANG_DETECTOR: Language | None = None


def load_language(language: LanguageStr) -> Language:
    lang = LANGUAGES.get(language)
    if lang is None:
        raise ValueError(
            f"unknown language ({sorted(LANGUAGES.keys())}): {language}")
    return spacy.load(lang)


@contextlib.contextmanager
def get_spacy(language: LanguageStr) -> Iterator[spacy.language.Language]:
    global SPACY_NLP
    global SPACY_LANG

    if language != SPACY_LANG or SPACY_NLP is None:
        SPACY_NLP = spacy.load("en_core_web_sm")
        SPACY_LANG = language
    yield SPACY_NLP


def ld_factory(
        nlp: Language,  # pylint: disable=unused-argument
        name: str) -> LanguageDetector:  # pylint: disable=unused-argument
    return LanguageDetector(seed=42)


Language.factory("language_detector", func=ld_factory)


@contextlib.contextmanager
def get_lang_detector() -> Iterator[spacy.language.Language]:
    global SPACY_LANG_DETECTOR

    if SPACY_LANG_DETECTOR is None:
        nlp = load_language("en")
        nlp.add_pipe("language_detector", last=True)
        SPACY_LANG_DETECTOR = nlp
    yield SPACY_LANG_DETECTOR


LengthCounter = Callable[[str], str]
LengthResult = Callable[[], int]


def create_length_counter() -> tuple[LengthCounter, LengthResult]:
    total = 0

    def length_counter(text: str) -> str:
        nonlocal total

        total += len(text)
        return text

    def length_result() -> int:
        return total

    return length_counter, length_result
