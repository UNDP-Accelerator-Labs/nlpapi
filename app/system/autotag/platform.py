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
"""Performs tagging updates to the platforms' databases."""
from collections.abc import Callable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.system.db.base import GlobalTagsTable, PlatformTaggingTable
from app.system.db.db import DBConnector
from app.system.prep.fulltext import get_base_doc


TAG_AI_TYPE = "auto_thematic"
"""The tag type used for auto tags."""


def clear_global_tags(session: Session) -> None:
    """
    Clears all auto tags from the login tag table.

    Args:
        session (Session): The login database session.
    """
    stmt = sa.delete(GlobalTagsTable).where(
        GlobalTagsTable.type == TAG_AI_TYPE)
    session.execute(stmt)


def clear_platform_tags(session: Session) -> None:
    """
    Clears all auto tags from a platform tagging table.

    Args:
        session (Session): The platform database session.
    """
    stmt = sa.delete(PlatformTaggingTable).where(
        PlatformTaggingTable.type == TAG_AI_TYPE)
    session.execute(stmt)


def fill_global_tags(session: Session, all_tags: set[str]) -> dict[str, int]:
    """
    Fills the login tag table with all tags and returns the tag id mapping.

    Args:
        session (Session): The login database session.
        all_tags (set[str]): All tags.

    Returns:
        dict[str, int]: A mapping from tag to tag id.
    """
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
    """
    Adds tags to the platform tagging table for a given pad.

    Args:
        session (Session): The platform database session.
        pad_id (int): The pad id.
        keywords (set[str]): The tags to add.
        lookup (dict[str, int]): The tag id lookup.
    """
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
    """
    Processes the tags for the given main ids.

    Args:
        main_ids (list[str]): The main ids.
        platforms (set[str]): The supported platforms.
        get_keywords (Callable[[str], set[str]]): Callback to retrieve the
            tags of a given main id.

    Returns:
        tuple[set[str], dict[str, dict[int, set[str]]]]: The full set of tags
            to add to the login tag table and the mapping of base to pad id to
            tag set.
    """
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
    """
    Fills in all tags to the login tag table and the platforms' tagging tables.

    Args:
        global_db (DBConnector): The login database connector.
        platforms (dict[str, DBConnector]): The platforms' database connectors.
        all_tags (set[str]): All tags.
        kwords (dict[str, dict[int, set[str]]]): Mapping from base to pad id to
            tag set.
    """
    with global_db.get_session() as g_session:
        clear_global_tags(g_session)
        lookup = fill_global_tags(g_session, all_tags)
    for base, p_db in platforms.items():
        kws = kwords.get(base, {})
        with p_db.get_session() as p_session:
            clear_platform_tags(p_session)
            for pad_id, pad_kws in kws.items():
                add_pad_tags(p_session, pad_id, pad_kws, lookup)
