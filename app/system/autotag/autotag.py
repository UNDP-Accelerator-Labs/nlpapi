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
from app.system.db.base import (
    TagCluster,
    TagClusterMember,
    TagGroupMembers,
    TagGroupTable,
    TagNamesTable,
)
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


TagClusterEntry = TypedDict('TagClusterEntry', {
    "id": int,
    "name": str,
})


def create_tag_group(
        session: Session,
        name: str | None,
        *,
        is_updating: bool) -> int:
    if name is None:
        name = f"tag {get_time_str()}"
    stmt = sa.insert(TagGroupTable).values(name=name, is_updating=is_updating)
    stmt = stmt.returning(TagGroupTable.id)
    row_id = session.execute(stmt).scalar()
    if row_id is None:
        raise ValueError(f"error adding tag group {name}")
    return int(row_id)


def get_tag_group(session: Session, name: str | None) -> int:
    stmt = sa.select(TagGroupTable.id)
    if name is not None:
        stmt = stmt.where(TagGroupTable.name == name)
    stmt = stmt.order_by(TagGroupTable.id.desc())
    stmt = stmt.limit(1)
    tag_group = session.execute(stmt).scalar()
    if tag_group is None:
        raise ValueError(f"could not find tag group {name=}")
    return int(tag_group)


def is_updating_tag_group(session: Session, tag_group: int) -> bool:
    stmt = sa.select(TagGroupTable.is_updating)
    stmt = stmt.where(TagGroupTable.id == tag_group)
    tag_group_is_updating = session.execute(stmt).scalar()
    if tag_group_is_updating is None:
        return False
    return bool(tag_group_is_updating)


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


def get_incomplete(session: Session) -> Iterable[TagElement]:
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
        session: Session,
        tag_group: int,
        main_id: str,
        keywords: list[str]) -> None:

    def get_previous_keywords() -> Iterable[TagKeyword]:
        stmt = sa.select(
            TagNamesTable.id,
            TagNamesTable.keyword,
            TagNamesTable.tag_group_to)
        stmt = stmt.where(sa.and_(
            TagNamesTable.main_id == main_id,
            TagNamesTable.tag_group_from <= tag_group,
            sa.or_(
                TagNamesTable.tag_group_to.is_(None),
                TagNamesTable.tag_group_to > tag_group)))
        for row in session.execute(stmt):
            yield {
                "id": row.id,
                "keyword": row.keyword,
                "tag_group_to": row.tag_group_to,
            }

    def finish_keywords(finished_ids: list[int]) -> None:
        stmt = sa.update(TagNamesTable)
        stmt = stmt.where(TagNamesTable.id.in_(finished_ids))
        stmt = stmt.values(tag_group_to=tag_group)
        session.execute(stmt)

    def add_new_keywords(
            new_keywords: list[str],
            *,
            include: bool,
            end_group: int | None) -> None:
        for keyword in new_keywords:
            stmt = db.upsert(TagNamesTable).values(
                main_id=main_id,
                tag_group_from=tag_group if include else tag_group + 1,
                tag_group_to=end_group,
                keyword=keyword)
            stmt = stmt.on_conflict_do_nothing()
            session.execute(stmt)

    def do_punch_hole(punch_hole: list[TagKeyword]) -> None:
        for tag in punch_hole:
            finish_keywords([tag["id"]])
            add_new_keywords(
                [tag["keyword"]],
                include=False,
                end_group=tag["tag_group_to"])

    def update_main_id() -> None:
        stmt = sa.update(TagGroupMembers)
        stmt = stmt.where(TagGroupMembers.main_id == main_id)
        stmt = stmt.values(complete=True)
        session.execute(stmt)

    kset = set(keywords)
    finished_ids: list[int] = []
    punch_hole: list[TagKeyword] = []
    old_keywords: set[str] = set()
    for kw_obj in get_previous_keywords():
        kw = kw_obj["keyword"]
        if kw not in kset:
            if kw_obj["tag_group_to"] is not None:
                punch_hole.append(kw_obj)
            else:
                finished_ids.append(kw_obj["id"])
        old_keywords.add(kw)
    new_keywords: list[str] = sorted(kset.difference(old_keywords))
    finish_keywords(finished_ids)
    add_new_keywords(new_keywords, include=True, end_group=None)
    do_punch_hole(punch_hole)
    update_main_id()


def is_ready(session: Session, tag_group: int) -> bool:
    stmt = sa.select(TagGroupMembers.complete).where(sa.and_(
        TagGroupMembers.complete.is_(False),
        TagGroupMembers.tag_group == tag_group))
    return session.execute(stmt).first() is None


def get_keywords(session: Session, tag_group: int) -> set[str]:
    main_ids = sa.select(TagGroupMembers.main_id)
    main_ids = main_ids.where(TagGroupMembers.tag_group == tag_group)
    stmt = sa.select(TagNamesTable.keyword)
    stmt = stmt.where(sa.and_(
        TagNamesTable.main_id.in_(main_ids),
        TagNamesTable.tag_group_from <= tag_group,
        sa.or_(
            TagNamesTable.tag_group_to.is_(None),
            TagNamesTable.tag_group_to > tag_group)))
    stmt = stmt.distinct()
    return {
        row.keyword
        for row in session.execute(stmt)
    }


def clear_clusters(session: Session, tag_group: int) -> None:
    stmt = sa.delete(TagCluster).where(TagCluster.tag_group == tag_group)
    session.execute(stmt)


def create_cluster(
        db: DBConnector,
        session: Session,
        tag_group: int,
        representative: str,
        keywords: set[str]) -> None:
    stmt = sa.insert(TagCluster).values(
        tag_group=tag_group,
        name=representative)
    stmt = stmt.returning(TagCluster.id)
    tag_cluster = session.execute(stmt).scalar()
    if tag_cluster is None:
        raise ValueError(f"error adding tag cluster for {representative}")
    for keyword in keywords:
        cstmt = db.upsert(TagClusterMember).values(
            tag_cluster=tag_cluster,
            keyword=keyword)
        cstmt = cstmt.on_conflict_do_nothing()
        session.execute(cstmt)


def get_tags_for_main_id(
        session: Session, tag_group: int, main_id: str) -> set[str]:
    stmt = sa.select(TagCluster.name).where(sa.and_(
        TagNamesTable.main_id == main_id,
        TagNamesTable.tag_group_from <= tag_group,
        sa.or_(
            TagNamesTable.tag_group_to.is_(None),
            TagNamesTable.tag_group_to > tag_group),
        TagNamesTable.keyword == TagClusterMember.keyword,
        TagClusterMember.tag_cluster == TagCluster.id))
    return {row.name for row in session.execute(stmt)}


def get_tag_cluster_id(session: Session, tag_group: int, tag: str) -> int:
    stmt = sa.select(TagCluster.id).where(sa.and_(
        TagCluster.tag_group == tag_group,
        TagCluster.name == tag))
    stmt = stmt.limit(1)
    cluster_id = session.execute(stmt).scalar()
    if cluster_id is None:
        raise ValueError(f"could not find tag cluster {tag=} {tag_group=}")
    return int(cluster_id)


def get_tag_clusters(
        session: Session, tag_group: int) -> list[TagClusterEntry]:
    stmt = sa.select(TagCluster.id, TagCluster.name).where(
        TagCluster.tag_group == tag_group)
    return [
        {
            "id": int(row.id),
            "name": row.name,
        }
        for row in session.execute(stmt)
    ]


def get_main_ids_for_tag(
        session: Session, tag_group: int, tag_cluster: int) -> set[str]:
    stmt = sa.select(TagNamesTable.main_id).where(sa.and_(
        TagNamesTable.tag_group_from <= tag_group,
        sa.or_(
            TagNamesTable.tag_group_to.is_(None),
            TagNamesTable.tag_group_to > tag_group),
        TagNamesTable.keyword == TagClusterMember.keyword,
        TagClusterMember.tag_cluster == tag_cluster))
    stmt = stmt.distinct()
    return {row.main_id for row in session.execute(stmt)}


def create_tag_tables(db: DBConnector) -> None:
    db.create_tables(
        [
            TagGroupTable,
            TagGroupMembers,
            TagNamesTable,
            TagCluster,
            TagClusterMember,
        ])
