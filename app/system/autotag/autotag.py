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
from collections.abc import Iterable
from typing import TypedDict

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.misc.util import get_time_str
from app.system.db.base import TagGroupMembers, TagGroupTable, TagsTable
from app.system.db.db import DBConnector


TagElement = TypedDict('TagElement', {
    "tag_group": int,
    "main_id": str,
})


TagKeyword = TypedDict('TagKeyword', {
    "id": int,
    "keyword": str,
    "tag_group_to": int | None,
})


def create_tag_group(session: Session, name: str | None) -> int:
    if name is None:
        name = f"tag {get_time_str()}"
    stmt = sa.insert(TagGroupTable).values(name=name)
    stmt = stmt.returning(TagGroupTable.id)
    row_id = session.execute(stmt).scalar()
    if row_id is None:
        raise ValueError(f"error adding tag group {name}")
    return int(row_id)


def add_tag_members(
        db: DBConnector,
        session: Session,
        tag_group_id: int,
        main_ids: list[str]) -> None:
    for main_id in main_ids:
        cstmt = db.upsert(TagGroupMembers).values(
            main_id=main_id,
            tag_group=tag_group_id)
        cstmt = cstmt.on_conflict_do_nothing()
        session.execute(cstmt)


def get_incomplete(db: DBConnector) -> Iterable[TagElement]:
    with db.get_session() as session:
        stmt = sa.select(TagGroupMembers.tag_group, TagGroupMembers.main_id)
        stmt = stmt.where(TagGroupMembers.complete.is_(False))
        stmt = stmt.order_by(
            TagGroupMembers.tag_group, TagGroupMembers.main_id)
        for row in session.execute(stmt):
            yield {
                "tag_group": row.tag_group,
                "main_id": row.main_id,
            }


def write_tag(
        db: DBConnector,
        tag_group: int,
        main_id: str,
        keywords: list[str]) -> None:

    def get_previous_keywords(session: Session) -> Iterable[TagKeyword]:
        stmt = sa.select(
            TagsTable.id,
            TagsTable.keyword,
            TagsTable.tag_group_to)
        stmt = stmt.where(sa.and_(
            TagsTable.main_id == main_id,
            TagsTable.tag_group_from <= tag_group,
            sa.or_(
                TagsTable.tag_group_to.is_(None),
                TagsTable.tag_group_to > tag_group)))
        for row in session.execute(stmt):
            yield {
                "id": row.id,
                "keyword": row.keyword,
                "tag_group_to": row.tag_group_to,
            }

    def finish_keywords(session: Session, finished_ids: list[int]) -> None:
        stmt = sa.update(TagsTable)
        stmt = stmt.where(TagsTable.id.in_(finished_ids))
        stmt = stmt.values(tag_group_to=tag_group)
        session.execute(stmt)

    def add_new_keywords(
            session: Session,
            new_keywords: list[str],
            end_group: int | None) -> None:
        for keyword in new_keywords:
            stmt = db.upsert(TagsTable).values(
                main_id=main_id,
                tag_group_from=tag_group,
                tag_group_to=end_group,
                keyword=keyword)
            stmt = stmt.on_conflict_do_nothing()
            session.execute(stmt)

    def do_punch_hole(session: Session, punch_hole: list[TagKeyword]) -> None:
        for tag in punch_hole:
            finish_keywords(session, [tag["id"]])
            add_new_keywords(session, [tag["keyword"]], tag["tag_group_to"])

    def update_main_id(session: Session) -> None:
        stmt = sa.update(TagGroupMembers)
        stmt = stmt.where(TagGroupMembers.main_id == main_id)
        stmt = stmt.values(complete=True)
        session.execute(stmt)

    kset = set(keywords)
    with db.get_session() as session:
        finished_ids: list[int] = []
        punch_hole: list[TagKeyword] = []
        old_keywords: set[str] = set()
        for kw_obj in get_previous_keywords(session):
            kw = kw_obj["keyword"]
            if kw not in kset:
                if kw_obj["tag_group_to"] is not None:
                    punch_hole.append(kw_obj)
                else:
                    finished_ids.append(kw_obj["id"])
            old_keywords.add(kw)
        new_keywords: list[str] = sorted(kset.difference(old_keywords))
        finish_keywords(session, finished_ids)
        add_new_keywords(session, new_keywords, None)
        do_punch_hole(session, punch_hole)
        update_main_id(session)


def create_tag_tables(db: DBConnector) -> None:
    db.create_tables(
        [
            TagGroupTable,
            TagGroupMembers,
            TagsTable,
            # TagCluster,
            # TagClusterMember,
        ])
