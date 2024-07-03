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
import traceback
from collections.abc import Callable
from datetime import datetime
from typing import TypeAlias

import sqlalchemy as sa
from scattermind.system.util import maybe_first

from app.misc.lru import LRU
from app.misc.util import CHUNK_PADDING, DocStatus, fmt_time, TITLE_CHUNK_SIZE
from app.system.dates.datetranslate import extract_date
from app.system.db.base import (
    ArticleContentTable,
    ArticlesRawHTMLTable,
    ArticlesTable,
    PadTable,
    UsersTable,
)
from app.system.db.db import DBConnector
from app.system.prep.clean import sanity_check
from app.system.prep.snippify import snippify_text
from app.system.stats import create_length_counter


FullTextFn: TypeAlias = Callable[[str], tuple[str | None, str | None]]
UrlTitleFn: TypeAlias = Callable[
    [str], tuple[tuple[str, str] | None, str | None]]
TagFn: TypeAlias = Callable[[str], tuple[str | None, str]]
StatusDateTypeFn: TypeAlias = Callable[
    [str], tuple[tuple[DocStatus, str | None, str] | None, str | None]]


def get_base_doc(main_id: str) -> tuple[str, int]:
    base, doc_id_str = main_id.split(":", 1)
    return base.strip(), int(doc_id_str)


def get_title(title: str | None) -> str | None:
    if title is not None and not f"{title}".strip():
        title = None
    if title is not None:
        title = sanity_check(f"{title}")
    return title


def read_pad(
        db: DBConnector,
        doc_id: int,
        *,
        combine_title: bool,
        ignore_unpublished: bool) -> tuple[str | None, str | None]:
    with db.get_session() as session:
        stmt = sa.select(
            PadTable.status, PadTable.full_text, PadTable.title)
        stmt = stmt.where(PadTable.id == doc_id)
        row = session.execute(stmt).one_or_none()
        if row is None:
            return (None, f"could not find {doc_id=}")
        if ignore_unpublished and int(row.status) <= 1:
            return (None, "pad is unpublished")
        res = sanity_check(f"{row.full_text}")
        title = get_title(row.title)
        if combine_title and title:
            res = f"{title}\n\n{res}"
        return (res, None)


def read_blog(
        db: DBConnector,
        doc_id: int,
        *,
        combine_title: bool,
        ignore_unpublished: bool) -> tuple[str | None, str | None]:
    with db.get_session() as session:
        stmt = sa.select(
            ArticlesTable.id,
            ArticlesTable.title,
            ArticlesTable.relevance,
            ArticleContentTable.article_id,
            ArticleContentTable.content)
        stmt = stmt.where(sa.and_(
            ArticleContentTable.article_id == ArticlesTable.id,
            ArticlesTable.id == doc_id))
        row = session.execute(stmt).one_or_none()
        if row is None:
            return (None, f"could not find {doc_id=}")
        if ignore_unpublished and int(row.relevance) <= 1:
            return (None, "article not relevant")
        content = sanity_check(f"{row.content}".strip())
        if not content:
            return (None, "empty content")
        title = get_title(row.title)
        if combine_title and title:
            content = f"{title}\n\n{content}"
        return (content, None)


FULL_TEXT_LRU: LRU[str, tuple[str | None, str | None]] = LRU(100)


def create_full_text(
        platforms: dict[str, DBConnector],
        blogs: dict[str, DBConnector],
        *,
        combine_title: bool,
        ignore_unpublished: bool,
        ) -> FullTextFn:

    def get_full_text(main_id: str) -> tuple[str | None, str | None]:
        lru = FULL_TEXT_LRU
        res = lru.get(main_id)
        if res is None:
            try:
                base, doc_id = get_base_doc(main_id)
                pdb = platforms.get(base)
                bdb = blogs.get(base)
                if pdb is not None:
                    res = read_pad(
                        pdb,
                        doc_id,
                        combine_title=combine_title,
                        ignore_unpublished=ignore_unpublished)
                elif bdb is not None:
                    res = read_blog(
                        bdb,
                        doc_id,
                        combine_title=combine_title,
                        ignore_unpublished=ignore_unpublished)
                else:
                    res = (None, f"unknown {base=}")
            except Exception:  # pylint: disable=broad-exception-caught
                res = (None, traceback.format_exc())
            if res[0] is not None:
                lru.set(main_id, res)
        return res

    return get_full_text


PLATFORM_URLS: dict[str, str] = {
    "solution": "https://solutions.sdg-innovation-commons.org/en/view/pad?id=",
    "actionplan": (
        "https://learningplans.sdg-innovation-commons.org/en/view/pad?id="),
    "experiment": (
        "https://experiments.sdg-innovation-commons.org/en/view/pad?id="),
}


def get_url_title_pad(
        db: DBConnector,
        base: str,
        doc_id: int,
        *,
        ignore_unpublished: bool,
        ) -> tuple[tuple[str, str | None] | None, str | None]:
    url_base = PLATFORM_URLS.get(base)
    if url_base is None:
        return (None, f"unknown {base=}")
    url = f"{url_base}{doc_id}"
    with db.get_session() as session:
        stmt = sa.select(PadTable.status, PadTable.title)
        stmt = stmt.where(PadTable.id == doc_id)
        row = session.execute(stmt).one_or_none()
        if row is None:
            return (None, f"could not find {doc_id=}")
        if ignore_unpublished and int(row.status) <= 1:
            return (None, "pad is unpublished")
        title = get_title(row.title)
        return ((url, title), None)


def get_url_title_blog(
        db: DBConnector,
        doc_id: int,
        *,
        ignore_unpublished: bool,
        ) -> tuple[tuple[str, str | None] | None, str | None]:
    with db.get_session() as session:
        stmt = sa.select(
            ArticlesTable.id,
            ArticlesTable.url,
            ArticlesTable.title,
            ArticlesTable.relevance)
        stmt = stmt.where(ArticlesTable.id == doc_id)
        row = session.execute(stmt).one_or_none()
        if row is None:
            return (None, f"could not find {doc_id=}")
        if ignore_unpublished and int(row.relevance) <= 1:
            return (None, "article not relevant")
        url = f"{row.url}"
        title = get_title(row.title)
        return ((url, title), None)


def create_url_title(
        platforms: dict[str, DBConnector],
        blogs: dict[str, DBConnector],
        *,
        get_full_text: FullTextFn,
        ignore_unpublished: bool) -> UrlTitleFn:

    def get_url_title(
            main_id: str,
            ) -> tuple[tuple[str, str] | None, str | None]:
        try:
            base, doc_id = get_base_doc(main_id)
            pdb = platforms.get(base)
            bdb = blogs.get(base)
            if pdb is not None:
                res = get_url_title_pad(
                    pdb,
                    base,
                    doc_id,
                    ignore_unpublished=ignore_unpublished)
            elif bdb is not None:
                res = get_url_title_blog(
                    bdb,
                    doc_id,
                    ignore_unpublished=ignore_unpublished)
            else:
                res = (None, f"unknown {base=}")
        except Exception:  # pylint: disable=broad-exception-caught
            res = (None, traceback.format_exc())
        urltitle, error = res
        if urltitle is not None:
            url, title = urltitle
            if title is None:
                input_str, input_error = get_full_text(main_id)
                if input_str is None:
                    return (
                        None,
                        "could not retrieve full text to "
                        f"infer title: {input_error}",
                    )
                title_loc = maybe_first(snippify_text(
                    input_str,
                    chunk_size=TITLE_CHUNK_SIZE,
                    chunk_padding=CHUNK_PADDING))
                if title_loc is None:
                    return (None, f"cannot infer title for {input_str=}")
                title, _ = title_loc
            urltitle = (url, title)
        return (urltitle, error)

    return get_url_title


def get_tag_pad(
        login_db: DBConnector,
        db: DBConnector,
        doc_id: int,
        *,
        ignore_unpublished: bool,
        ) -> tuple[str | None, str]:
    with db.get_session() as session:
        stmt = sa.select(PadTable.status, PadTable.owner)
        stmt = stmt.where(PadTable.id == doc_id)
        row = session.execute(stmt).one_or_none()
        if row is None:
            return (None, f"could not find {doc_id=}")
        if ignore_unpublished and int(row.status) <= 1:
            return (None, "pad is unpublished")
        user_id = row.owner
    with login_db.get_session() as lsession:
        stmt = sa.select(UsersTable.iso3)
        stmt = stmt.where(UsersTable.uuid == user_id)
        row = lsession.execute(stmt).one_or_none()
        if row is None:
            return (None, f"could not find {user_id=}")
        return (row.iso3, "retrieved from users.iso3")


def get_tag_blog(
        db: DBConnector,
        doc_id: int,
        *,
        ignore_unpublished: bool,
        ) -> tuple[str | None, str]:
    with db.get_session() as session:
        stmt = sa.select(
            ArticlesTable.id,
            ArticlesTable.iso3,
            ArticlesTable.relevance)
        stmt = stmt.where(ArticlesTable.id == doc_id)
        row = session.execute(stmt).one_or_none()
        if row is None:
            return (None, f"could not find {doc_id=}")
        if ignore_unpublished and int(row.relevance) <= 1:
            return (None, "article not relevant")
        return (row.iso3, "retrieved from articles.iso3")


def create_tag_fn(
        platforms: dict[str, DBConnector],
        blogs: dict[str, DBConnector],
        *,
        ignore_unpublished: bool) -> TagFn:

    def get_tag(main_id: str) -> tuple[str | None, str]:
        try:
            base, doc_id = get_base_doc(main_id)
            pdb = platforms.get(base)
            bdb = blogs.get(base)
            if pdb is not None:
                login_db = platforms["login"]
                res = get_tag_pad(
                    login_db,
                    pdb,
                    doc_id,
                    ignore_unpublished=ignore_unpublished)
            elif bdb is not None:
                res = get_tag_blog(
                    bdb,
                    doc_id,
                    ignore_unpublished=ignore_unpublished)
            else:
                res = (None, f"unknown {base=}")
        except Exception:  # pylint: disable=broad-exception-caught
            res = (None, traceback.format_exc())
        return res

    return get_tag


DOC_TYPES: dict[str, str] = {
    "solution": "solution",
    "actionplan": "action plan",
    "experiment": "experiment",
}


STATUS_MAP: dict[int, DocStatus] = {
    2: "preview",
    3: "public",
}


def get_status_date_type_pad(
        db: DBConnector,
        base: str,
        doc_id: int,
        *,
        ignore_unpublished: bool,
        ) -> tuple[tuple[DocStatus, str | None, str] | None, str | None]:
    with db.get_session() as session:
        stmt = sa.select(PadTable.status, PadTable.update_at)
        stmt = stmt.where(PadTable.id == doc_id)
        row = session.execute(stmt).one_or_none()
        if row is None:
            return (None, f"could not find {doc_id=}")
        status_int = int(row.status)
        if ignore_unpublished and status_int <= 1:
            return (None, "pad is unpublished")
        doc_type = DOC_TYPES.get(base)
        if doc_type is None:
            return (None, f"{base} is not supported!")
        if row.update_at:
            date = datetime.fromisoformat(f"{row.update_at}").isoformat()
        else:
            date = None
        status = STATUS_MAP.get(status_int)
        if status is None:
            return (None, f"invalid {status_int=}")
        return ((status, date, doc_type), None)


def get_status_date_type_blog(
        db: DBConnector,
        doc_id: int,
        *,
        ignore_unpublished: bool,
        ) -> tuple[tuple[DocStatus, str | None, str] | None, str | None]:
    with db.get_session() as session:
        stmt = sa.select(
            ArticlesTable.id,
            ArticlesTable.posted_date,
            ArticlesTable.posted_date_str,
            ArticlesTable.article_type,
            ArticlesTable.relevance,
            ArticlesRawHTMLTable.raw_html)
        stmt = stmt.where(sa.and_(
            ArticlesTable.id == doc_id,
            ArticlesTable.id == ArticlesRawHTMLTable.article_id))
        row = session.execute(stmt).one_or_none()
        if row is None:
            return (None, f"could not find {doc_id=}")
        if ignore_unpublished and int(row.relevance) <= 1:
            return (None, "article not relevant")
        status: DocStatus = "public"
        if row.posted_date:
            date: str | None = datetime.fromisoformat(
                f"{row.posted_date}").isoformat()
        else:
            lnc, _ = create_length_counter()
            date_res = extract_date(
                row.raw_html,
                posted_date_str=row.posted_date_str,
                language=None,
                use_date_str=True,
                lnc=lnc)
            date = None if date_res is None else fmt_time(date_res)
        doc_type = f"{row.article_type}"
        return ((status, date, doc_type), None)


def create_status_date_type(
        platforms: dict[str, DBConnector],
        blogs: dict[str, DBConnector],
        *,
        ignore_unpublished: bool) -> StatusDateTypeFn:

    def get_status_date_type(
            main_id: str,
            ) -> tuple[tuple[DocStatus, str | None, str] | None, str | None]:
        try:
            base, doc_id = get_base_doc(main_id)
            pdb = platforms.get(base)
            bdb = blogs.get(base)
            if pdb is not None:
                res = get_status_date_type_pad(
                    pdb,
                    base,
                    doc_id,
                    ignore_unpublished=ignore_unpublished)
            elif bdb is not None:
                res = get_status_date_type_blog(
                    bdb,
                    doc_id,
                    ignore_unpublished=ignore_unpublished)
            else:
                res = (None, f"unknown {base=}")
        except Exception:  # pylint: disable=broad-exception-caught
            res = (None, traceback.format_exc())
        return res

    return get_status_date_type
