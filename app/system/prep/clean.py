import re
import unicodedata
from html import unescape
from typing import overload


def clean(text: str) -> str:
    text = text.strip()
    while True:
        prev_text = text
        text = unescape(text)
        if prev_text == text:
            break
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"\n\n+", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\n\n+", "\n\n", text)
    text = re.sub(r"\s\s+", " ", text)  # ignore all newlines...
    return text


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?\s*>", "\n", text.strip())
    text = re.sub(r"<(?:\"[^\"]*\"['\"]*|'[^']*'['\"]*|[^'\">])+>", "", text)
    return text


@overload
def normalize_text(text: str) -> str:
    ...


@overload
def normalize_text(text: None) -> None:
    ...


def normalize_text(text: str | None) -> str | None:
    if text is None:
        return None
    return clean(strip_html(text)).strip()


BOP = "{"
BCL = "}"
RED_FLAGS: list[str] = ["null", "none", "undefined", "void", "0"]
RED_FLAG_VARIATIONS: set[str] = {
    rtext
    for red in RED_FLAGS
    for rtext in (red, f"({red})", f"{BOP}{red}{BCL}")
}
RED_LEN = max((len(red) for red in RED_FLAG_VARIATIONS))


@overload
def sanity_check(text: str) -> str:
    ...


@overload
def sanity_check(text: None) -> None:
    ...


def sanity_check(text: str | None) -> str | None:
    if text is None:
        return None
    text = f"{text}"
    canonical = text.strip()
    if len(canonical) > RED_LEN:
        return text
    canonical = canonical.lower()
    if canonical in RED_FLAG_VARIATIONS:
        raise ValueError(
            f"{canonical=} in {text=}! this might be a bug on the sender side")
    return text
