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
"""Cleaning a text from unwanted characters and noise."""
import re
import unicodedata
from html import unescape
from typing import overload


def clean(text: str) -> str:
    """
    Remove redundant white-space, unescape characters, and normalize unicode
    characters.

    Args:
        text (str): The raw text.

    Returns:
        str: The clean text.
    """
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
    """
    Remove html elements.

    Args:
        text (str): The raw text.

    Returns:
        str: The clean text.
    """
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
    """
    Removes redundant white-space, unescapes characters, normalizes unicode
    characters, and removes html elements.

    Args:
        text (str | None): The raw text or None.

    Returns:
        str | None: The clean text or None if the input was None.
    """
    if text is None:
        return None
    return clean(strip_html(text)).strip()


BOP = r"{"
"""Opening curly brace."""
BCL = r"}"
"""Closing curly brace."""
RED_FLAGS: list[str] = ["null", "none", "undefined", "void", "0"]
"""Suspicious strings."""
RED_FLAG_VARIATIONS: set[str] = {
    rtext
    for red in RED_FLAGS
    for rtext in (red, f"({red})", f"{BOP}{red}{BCL}")
}
"""Variations of suspicious strings."""
RED_LEN = max((len(red) for red in RED_FLAG_VARIATIONS))
"""Maximum length of suspicious strings."""


@overload
def sanity_check(text: str) -> str:
    ...


@overload
def sanity_check(text: None) -> None:
    ...


def sanity_check(text: str | None) -> str | None:
    """
    Detects suspicious inputs. A suspicious input likely comes from an upstream
    error, such as accidentally converting a `null` value into a string or
    similar. Those inputs are rejected to fail fast on upstream errors.

    Args:
        text (str | None): The raw text or None.

    Raises:
        ValueError: If the input was suspicious.

    Returns:
        str | None: The raw text or None if the input was None.
    """
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
