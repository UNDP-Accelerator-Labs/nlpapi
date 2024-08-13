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
"""Database logic for auto-tags."""
from collections.abc import Iterable
from typing import TypedDict

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.misc.util import get_time_str, json_compact_str, json_read_str
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
"""A document in a tag group. The document is identified by main id."""


TagKeyword = TypedDict('TagKeyword', {
    "id": int,
    "keyword": str,
    "tag_group_to": int | None,
})
"""A raw keyword of a document. The exclusive upper end of tag groups is
given by `tag_group_to`. If its value is None it is valid to the latest tag
group. Keywords don't change very often unless the document content changes.
Therefore, the same keyword will appear in multiple tag groups."""


TagClusterEntry = TypedDict('TagClusterEntry', {
    "id": int,
    "name": str,
})
"""A tag cluster. The `name` is the representative keyword."""


def create_tag_group(
        session: Session,
        name: str | None,
        *,
        is_updating: bool,
        cluster_args: dict) -> int:
    """
    Creates a new tag group.

    Args:
        session (Session): The database session.
        name (str | None): The optional name of the tag group. If unspecified
            the current time is used.
        is_updating (bool): Whether the tag group will update the platforms'
            tagging tables.
        cluster_args (dict): Arguments to the clustering algorithm.

    Returns:
        int: The tag group id.
    """
    if name is None:
        name = f"tag {get_time_str()}"
    stmt = sa.insert(TagGroupTable).values(
        name=name,
        is_updating=is_updating,
        cluster_args=json_compact_str(cluster_args))
    stmt = stmt.returning(TagGroupTable.id)
    row_id = session.execute(stmt).scalar()
    if row_id is None:
        raise ValueError(f"error adding tag group {name}")
    return int(row_id)


def get_tag_group(session: Session, name: str | None) -> int:
    """
    Get a tag group by name.

    Args:
        session (Session): The database session.
        name (str | None): The name of the tag group to retrieve. If the name
            is None the latest updating tag group is returned.

    Raises:
        ValueError: If the tag group doesn't exist.

    Returns:
        int: The tag group id.
    """
    stmt = sa.select(TagGroupTable.id)
    if name is not None:
        stmt = stmt.where(TagGroupTable.name == name)
    else:
        stmt = stmt.where(TagGroupTable.is_updating.is_(True))
    stmt = stmt.order_by(TagGroupTable.id.desc())
    stmt = stmt.limit(1)
    tag_group = session.execute(stmt).scalar()
    if tag_group is None:
        raise ValueError(f"could not find tag group {name=}")
    return int(tag_group)


def is_updating_tag_group(session: Session, tag_group: int) -> bool:
    """
    Whether the tag group is updating. That is, whether it will update the
    platforms' tagging tables.

    Args:
        session (Session): The database session.
        tag_group (int): The tag group.

    Returns:
        bool: True, if the tag group is updating.
    """
    stmt = sa.select(TagGroupTable.is_updating)
    stmt = stmt.where(TagGroupTable.id == tag_group)
    tag_group_is_updating = session.execute(stmt).scalar()
    if tag_group_is_updating is None:
        return False
    return bool(tag_group_is_updating)


def get_tag_group_cluster_args(session: Session, tag_group: int) -> dict:
    """
    Get the clustering arguments for the given tag group.

    Args:
        session (Session): The database session.
        tag_group (int): The tag group.

    Returns:
        dict: The clustering arguments.
    """
    stmt = sa.select(TagGroupTable.cluster_args)
    stmt = stmt.where(TagGroupTable.id == tag_group)
    tag_group_cluster_args = session.execute(stmt).scalar()
    if tag_group_cluster_args is None:
        return {}
    return json_read_str(tag_group_cluster_args)


def add_tag_members(
        db: DBConnector,
        session: Session,
        tag_group_id: int,
        main_ids: list[str]) -> None:
    """
    Add documents to a tag group.

    Args:
        db (DBConnector): The database connector.
        session (Session): The database session.
        tag_group_id (int): The tag group.
        main_ids (list[str]): The list of documents as main ids.
    """
    for main_id in main_ids:
        cstmt = db.upsert(TagGroupMembers).values(
            main_id=main_id,
            tag_group=tag_group_id)
        cstmt = cstmt.on_conflict_do_nothing()
        session.execute(cstmt)


def get_incomplete(session: Session) -> Iterable[TagElement]:
    """
    Retrieves all documents that still need to be processed.

    Args:
        session (Session): The database session.

    Yields:
        TagElement: The unprocessed document.
    """
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
    """
    Sets the keywords for a given document of a tag group. Entries are updated
    so that `tag_group_from` reflects the earliest tag group with the given
    keywords and `tag_group_to` is the exclusive upper end or None if the
    latest tag group contains the keywords. In most cases only the previous
    keyword entries need to be updated (if at all). If an out of order tag
    group is used a situation can happen where a hole needs to be punched into
    a range. Example:
    ```
        "foo" 0, 4
        "bar" 0, None
        "baz" 1, 5
        "blip" 0, None
        "blap" 3, 5
        "flop" 1, None
    ```
    setting `["blub", "blip", "blap", "flop"]` for tag group 2
    (out of order tag group):
    ```
        "foo" 0, 2
        "foo" 3, 4
        "bar" 0, 2
        "bar" 3, None
        "baz" 1, 2
        "baz" 3, 5
        "blip" 0, None
        "blap" 3, 5
        "blub" 2, 3
        "flop" 1, None
    ```
    setting `["foo", "blub", "blip", "bar", "baz"]` for tag group 6
    ```
        "foo" 0, 2
        "foo" 3, 4
        "foo" 6, None
        "bar" 0, 2
        "bar" 3, None
        "baz" 1, 2
        "baz" 3, 5
        "baz" 6, None
        "blip" 0, None
        "blap" 3, 5
        "blub" 2, 3
        "blub" 6, None
        "flop" 1, 6
    ```

    Args:
        db (DBConnector): The database connector.
        session (Session): The database session.
        tag_group (int): The tag group.
        main_id (str): The document main id.
        keywords (list[str]): The full list of keywords for the given document.
    """

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
    """
    Whether all raw keywords for a tag group are computed.

    Args:
        session (Session): The database session.
        tag_group (int): The tag group.

    Returns:
        bool: True, if all raw keywords are computed for the given tag group.
    """
    stmt = sa.select(TagGroupMembers.complete).where(sa.and_(
        TagGroupMembers.complete.is_(False),
        TagGroupMembers.tag_group == tag_group))
    return session.execute(stmt).first() is None


def get_keywords(session: Session, tag_group: int) -> set[str]:
    """
    Get all distinct raw keywords in the given tag group.

    Args:
        session (Session): The database session.
        tag_group (int): The tag group.

    Returns:
        set[str]: The set of raw keywords.
    """
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
    """
    Delete all computed clusters for the given tag group.

    Args:
        session (Session): The database session.
        tag_group (int): The tag group.
    """
    stmt = sa.delete(TagCluster).where(TagCluster.tag_group == tag_group)
    session.execute(stmt)


def create_cluster(
        db: DBConnector,
        session: Session,
        tag_group: int,
        representative: str,
        keywords: set[str]) -> None:
    """
    Create a new cluster for the given tag group.

    Args:
        db (DBConnector): The database connector.
        session (Session): The database session.
        tag_group (int): The tag group.
        representative (str): The cluster representative.
        keywords (set[str]): The keywords belonging to the cluster.
    """
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
    """
    Retrieve all cluster representatives for the given document.

    Args:
        session (Session): The database session.
        tag_group (int): The tag group.
        main_id (str): The main id.

    Returns:
        set[str]: The cluster representatives.
    """
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
    """
    Get the cluster id for the given cluster representative.

    Args:
        session (Session): The database session.
        tag_group (int): The tag group.
        tag (str): The cluster representative.

    Raises:
        ValueError: If no cluster with this representative exists.

    Returns:
        int: The cluster id.
    """
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
    """
    Get all clusters for a given tag group.

    Args:
        session (Session): The database session.
        tag_group (int): The tag group.

    Returns:
        list[TagClusterEntry]: All clusters.
    """
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
    """
    Gets all documents for a given cluster.

    Args:
        session (Session): The database session.
        tag_group (int): The tag group.
        tag_cluster (int): The cluster id.

    Returns:
        set[str]: The main ids that have the cluster as tag.
    """
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
    """
    Creates all tag related tables.

    Args:
        db (DBConnector): The database connector.
    """
    db.create_tables(
        [
            TagGroupTable,
            TagGroupMembers,
            TagNamesTable,
            TagCluster,
            TagClusterMember,
        ])
