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
