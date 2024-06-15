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
from collections.abc import Callable

import sqlalchemy as sa

from app.system.db.base import ArticleContentTable, ArticlesTable, PadTable
from app.system.db.db import DBConnector
from app.system.prep.clean import sanity_check


def read_pad(
        db: DBConnector,
        doc_id: int,
        *,
        combine_title: bool,
        ignore_unpublished: bool) -> str | None:
    with db.get_session() as session:
        stmt = sa.select(
            PadTable.status, PadTable.full_text, PadTable.title)
        stmt = stmt.where(PadTable.id == doc_id)
        row = session.execute(stmt).one_or_none()
        if row is None:
            return None
        if ignore_unpublished and int(row.status) <= 1:
            return None
        res = sanity_check(f"{row.full_text}")
        if combine_title:
            title = sanity_check(f"{row.title}")
            res = f"{title}\n\n{res}"
        return res


def read_blog(
        db: DBConnector,
        doc_id: int,
        *,
        combine_title: bool,
        ignore_unpublished: bool) -> str | None:
    with db.get_session() as session:
        stmt = sa.select(
            ArticlesTable.id,
            ArticlesTable.title,
            ArticlesTable.relevance,
            ArticleContentTable.article_id,
            ArticleContentTable.content,
            ).join(ArticleContentTable.article_id)
        stmt = stmt.where(ArticlesTable.id == doc_id)
        row = session.execute(stmt).one_or_none()
        if row is None:
            return None
        if ignore_unpublished and int(row.relevance) <= 1:
            return None
        content = sanity_check(f"{row.content}".strip())
        if not content:
            return None
        if combine_title:
            title = sanity_check(f"{row.title}")
            content = f"{title}\n\n{content}"
        return content


def create_full_text(
        platforms: dict[str, DBConnector],
        blogs_db: DBConnector,
        *,
        combine_title: bool,
        ignore_unpublished: bool) -> Callable[[str], str | None]:

    def get_full_text(main_id: str) -> str | None:
        try:
            base, doc_id_str = main_id.split(":")
            base = base.strip()
            doc_id = int(doc_id_str.strip())
        except ValueError:
            return None
        pdb = platforms.get(base)
        if pdb is not None:
            return read_pad(
                pdb,
                doc_id,
                combine_title=combine_title,
                ignore_unpublished=ignore_unpublished)
        if base == "blogs":
            return read_blog(
                blogs_db,
                doc_id,
                combine_title=combine_title,
                ignore_unpublished=ignore_unpublished)
        return None

    return get_full_text
