import re
import unicodedata
from html import unescape


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


def normalize_text(text: str) -> str:
    return clean(strip_html(text)).strip()
