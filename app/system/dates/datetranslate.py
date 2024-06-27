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
import re
from datetime import datetime

import translators as ts  # type: ignore
from dateutil import parser
from dateutil.parser import ParserError
from translators.server import TranslatorError  # type: ignore

from app.system.language.langdetect import get_lang
from app.system.stats import LengthCounter


P_RE = re.compile(r"<p>(.*?)<\/p>")
H_RE = re.compile(r"<h6 class=\"posted-date\">(.*?)</h6>")
SPACE_RE = re.compile(r"[\s\n]+")


def get_translate_lang(
        raw: str,
        language: str | None,
        lnc: LengthCounter) -> str:
    if language is not None and language != "en":
        return language
    lang_res = get_lang(raw, lnc)
    langs = lang_res["languages"]
    if not langs:
        return "en"
    return langs[0]["lang"]


def translate_date(*, date: str, lang: str) -> str:
    if lang == "en":
        return date
    try:
        return ts.translate_text(date, from_language=lang, to_language="en")
    except TranslatorError:
        return date


def parse_date(date_en: str) -> datetime | None:
    try:
        return parser.parse(date_en)
    except ParserError:
        return None


def get_date_candidate(
        raw_html: str,
        *,
        posted_date_str: str | None,
        use_date_str: bool) -> str:
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
    raw = " ".join(P_RE.findall(raw_html))
    lang = get_translate_lang(raw, language, lnc)
    date = get_date_candidate(
        raw_html, posted_date_str=posted_date_str, use_date_str=use_date_str)
    date_en = translate_date(date=date, lang=lang)
    return parse_date(date_en)
