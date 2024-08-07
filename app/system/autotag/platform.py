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
from sqlalchemy.orm import Session

from app.system.db.base import GlobalTagsTable, PlatformTaggingTable
from app.system.db.db import DBConnector
from app.system.prep.fulltext import get_base_doc


TAG_AI_TYPE = "auto_thematic"


def clear_global_tags(session: Session) -> None:
    stmt = sa.delete(GlobalTagsTable).where(
        GlobalTagsTable.type == TAG_AI_TYPE)
    session.execute(stmt)


def clear_platform_tags(session: Session) -> None:
    stmt = sa.delete(PlatformTaggingTable).where(
        PlatformTaggingTable.type == TAG_AI_TYPE)
    session.execute(stmt)


def fill_global_tags(session: Session, all_tags: set[str]) -> dict[str, int]:
    res: dict[str, int] = {}
    for keyword in all_tags:
        stmt = sa.insert(GlobalTagsTable).values(
            name=keyword,
            contributor=None,
            language="en",  # FIXME be smarter than this
            label=None,
            type=TAG_AI_TYPE,
            key=None,
            description=None)
        stmt = stmt.returning(GlobalTagsTable.id)
        row_id = session.execute(stmt).scalar()
        if row_id is None:
            raise ValueError(f"error adding {keyword=} to global tag table")
        res[keyword] = int(row_id)
    return res


def add_pad_tags(
        session: Session,
        pad_id: int,
        keywords: set[str],
        lookup: dict[str, int]) -> None:
    for keyword in keywords:
        stmt = sa.insert(PlatformTaggingTable).values(
            pad=pad_id,
            tag_id=lookup[keyword],
            type=TAG_AI_TYPE)
        session.execute(stmt)


def process_main_ids(
        main_ids: list[str],
        *,
        platforms: set[str],
        get_keywords: Callable[[str], set[str]],
        ) -> tuple[set[str], dict[str, dict[int, set[str]]]]:
    all_tags: set[str] = set()
    kwords: dict[str, dict[int, set[str]]] = {}
    for main_id in main_ids:
        base, pad_id = get_base_doc(main_id)
        if base not in platforms:
            continue  # NOTE: we ignore blogs etc
        kw_pads = kwords.get(base)
        if kw_pads is None:
            kw_pads = {}
            kwords[base] = kw_pads
        cur_kws = get_keywords(main_id)
        if cur_kws:
            all_tags.update(cur_kws)
            kw_pads[pad_id] = set(cur_kws)
    return all_tags, kwords


def fill_in_everything(
        global_db: DBConnector,
        platforms: dict[str, DBConnector],
        *,
        all_tags: set[str],
        kwords: dict[str, dict[int, set[str]]],
        ) -> None:
    with global_db.get_session() as g_session:
        clear_global_tags(g_session)
        lookup = fill_global_tags(g_session, all_tags)
    for base, p_db in platforms.items():
        kws = kwords.get(base, {})
        with p_db.get_session() as p_session:
            clear_platform_tags(p_session)
            for pad_id, pad_kws in kws.items():
                add_pad_tags(p_session, pad_id, pad_kws, lookup)
