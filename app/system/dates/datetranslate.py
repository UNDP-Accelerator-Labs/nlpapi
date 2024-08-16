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
"""Extracts dates."""
import re
import time
from datetime import datetime

import requests
import translators as ts  # type: ignore
from dateutil import parser
from dateutil.parser import ParserError
from translators.server import TranslatorError  # type: ignore

from app.system.language.langdetect import get_lang
from app.system.stats import LengthCounter


P_RE = re.compile(r"<p>(.*?)<\/p>")
"""Regex to find the content of a leaf paragraph."""
H_RE = re.compile(r"<h6 class=\"posted-date\">(.*?)</h6>")
"""Regex to find the content of a leaf header."""
SPACE_RE = re.compile(r"[\s\n]+")
"""Regex for spaces."""


def get_translate_lang(
        raw: str,
        language: str | None,
        lnc: LengthCounter) -> str:
    """
    Get the language needed for translation. If `en` no translation is
    necessary.

    Args:
        raw (str): The raw content.
        language (str | None): Previously determined language or None.
        lnc (LengthCounter): The length counter for the language api.

    Returns:
        str: The iso language.
    """
    if language is not None and language != "en":
        return language
    lang_res = get_lang(raw, lnc)
    langs = lang_res["languages"]
    if not langs:
        return "en"
    return langs[0]["lang"]


TRANSLATE_FREQ: float = 1.0
"""How frequent (in secconds) a date can be translated."""
LAST_TRANSLATE: float | None = None
"""When the last translation happened."""


def translate_date(*, date: str, lang: str) -> str:
    """
    Translates the given date from the provided iso language.

    Args:
        date (str): The date string.
        lang (str): The iso language.

    Returns:
        str: The date in english.
    """
    global LAST_TRANSLATE  # pylint: disable=global-statement

    if lang == "en":
        return date
    if LAST_TRANSLATE is not None:
        diff = TRANSLATE_FREQ - (time.monotonic() - LAST_TRANSLATE)
        if diff > 0.0:
            time.sleep(diff)
    try:
        try:
            return ts.translate_text(
                date, from_language=lang, to_language="en")
        except TranslatorError:
            return date
        except requests.exceptions.HTTPError as err:
            response: requests.Response = err.response
            if response.status_code != 429:
                raise
            raise ValueError(f"quota reached: {response.headers}") from err
    finally:
        LAST_TRANSLATE = time.monotonic()


def parse_date(date_en: str) -> datetime | None:
    """
    Parses an english date string.

    Args:
        date_en (str): The english date string.

    Returns:
        datetime | None: The parsed date or None if it couldn't be parsed.
    """
    try:
        return parser.parse(date_en)
    except ParserError:
        return None


def get_date_candidate(
        raw_html: str,
        *,
        posted_date_str: str | None,
        use_date_str: bool) -> str:
    """
    Gets a candidate for a date string.

    Args:
        raw_html (str): The raw html.
        posted_date_str (str | None): A previously detected date string or
            None.
        use_date_str (bool): Whether to use the previously detected date string
            if it is available.

    Returns:
        str: A candidate date string.
    """
    if use_date_str and posted_date_str is not None:
        return posted_date_str
    date = " ".join(H_RE.findall(raw_html)).strip().lower()
    return SPACE_RE.sub(" ", date)


def extract_date(
        raw_html: str,
        *,
        posted_date_str: str | None,
        language: str | None,
        use_date_str: bool,
        lnc: LengthCounter) -> datetime | None:
    """
    Extracts the main date of the given raw html.

    Args:
        raw_html (str): The raw html.
        posted_date_str (str | None): Previously detected date string or None.
        language (str | None): Previously detected iso language or None.
        use_date_str (bool): Whether to use the previously detected date
            string.
        lnc (LengthCounter): The length counter for the language api.

    Returns:
        datetime | None: The parsed date or None if no date was found or if it
            didn't parse.
    """
    raw = " ".join(P_RE.findall(raw_html))
    lang = get_translate_lang(raw, language, lnc)
    date = get_date_candidate(
        raw_html, posted_date_str=posted_date_str, use_date_str=use_date_str)
    date_en = translate_date(date=date, lang=lang)
    return parse_date(date_en)
