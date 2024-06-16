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

import sqlalchemy as sa

from app.misc.lru import LRU
from app.system.db.base import ArticleContentTable, ArticlesTable, PadTable
from app.system.db.db import DBConnector
from app.system.prep.clean import sanity_check


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
        if combine_title:
            title = sanity_check(f"{row.title}")
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
        if combine_title:
            title = sanity_check(f"{row.title}")
            content = f"{title}\n\n{content}"
        return (content, None)


def create_full_text(
        platforms: dict[str, DBConnector],
        blogs_db: DBConnector,
        *,
        combine_title: bool,
        ignore_unpublished: bool,
        ) -> Callable[[str], tuple[str | None, str | None]]:

    def get_full_text(main_id: str) -> tuple[str | None, str | None]:
        try:
            base, doc_id_str = main_id.split(":")
            base = base.strip()
            doc_id = int(doc_id_str.strip())
            pdb = platforms.get(base)
            if pdb is not None:
                return read_pad(
                    pdb,
                    doc_id,
                    combine_title=combine_title,
                    ignore_unpublished=ignore_unpublished)
            if base == "blog":
                return read_blog(
                    blogs_db,
                    doc_id,
                    combine_title=combine_title,
                    ignore_unpublished=ignore_unpublished)
            return (None, f"unknown {base=}")
        except Exception:  # pylint: disable=broad-exception-caught
            return (None, traceback.format_exc())

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
        ) -> tuple[tuple[str, str] | None, str | None]:
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
        title = f"{row.title}"
        return ((url, title), None)


def get_url_title_blog(
        db: DBConnector,
        doc_id: int,
        *,
        ignore_unpublished: bool,
        ) -> tuple[tuple[str, str] | None, str | None]:
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
        title = f"{row.title}"
        return ((url, title), None)


URL_TITLE_LRU: LRU[str, tuple[tuple[str, str] | None, str | None]] = LRU(1000)


def get_url_title(
        platforms: dict[str, DBConnector],
        blogs_db: DBConnector,
        main_id: str,
        *,
        ignore_unpublished: bool,
        ) -> tuple[tuple[str, str] | None, str | None]:
    lru = URL_TITLE_LRU
    res = lru.get(main_id)
    if res is None:
        try:
            base, doc_id_str = main_id.split(":")
            base = base.strip()
            doc_id = int(doc_id_str.strip())
            pdb = platforms.get(base)
            if pdb is not None:
                res = get_url_title_pad(
                    pdb,
                    base,
                    doc_id,
                    ignore_unpublished=ignore_unpublished)
            elif base == "blog":
                res = get_url_title_blog(
                    blogs_db,
                    doc_id,
                    ignore_unpublished=ignore_unpublished)
            else:
                res = (None, f"unknown {base=}")
        except Exception:  # pylint: disable=broad-exception-caught
            res = (None, traceback.format_exc())
        lru.set(main_id, res)
    return res
