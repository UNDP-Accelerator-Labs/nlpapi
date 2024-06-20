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
from uuid import UUID

import sqlalchemy as sa
from quick_server import PreventDefaultResponse
from sqlalchemy.orm import Session

from app.system.db.base import DeepDiveCollection, DeepDiveElement
from app.system.db.db import DBConnector


CollectionObj = TypedDict('CollectionObj', {
    "id": int,
    "user": UUID,
    "name": str,
    "deep_dive_key": str,
    "is_public": bool,
})


CollectionOptions = TypedDict('CollectionOptions', {
    "is_public": bool,
})


VerifyResult = TypedDict('VerifyResult', {
    "reason": str,
    "is_hit": bool,
})

DeepDiveResult = TypedDict('DeepDiveResult', {
    "reason": str,
    "cultural": int,
    "economic": int,
    "educational": int,
    "institutional": int,
    "legal": int,
    "political": int,
    "technological": int,
})


DocumentObj = TypedDict('DocumentObj', {
    "id": int,
    "main_id": str,
    "url": str | None,
    "title": str | None,
    "deep_dive": int,
    "verify_key": str,
    "deep_dive_key": str,
    "is_valid": bool | None,
    "verify_reason": str | None,
    "deep_dive_result": DeepDiveResult | None,
    "error": str | None,
    "tag": str | None,
    "tag_reason": str | None,
})


def get_deep_dive_keys(deep_dive: str) -> tuple[str, str]:
    if deep_dive == "circular_economy":
        return ("verify_circular_economy", "rate_circular_economy")
    raise ValueError(f"unknown {deep_dive=}")


def add_collection(
        db: DBConnector, user: UUID, name: str, deep_dive: str) -> int:
    verify_key, deep_dive_key = get_deep_dive_keys(deep_dive)
    with db.get_session() as session:
        stmt = sa.insert(DeepDiveCollection).values(
            name=name,
            user=user,
            verify_key=verify_key,
            deep_dive_key=deep_dive_key)
        stmt = stmt.returning(DeepDiveCollection.id)
        row_id = session.execute(stmt).scalar()
        if row_id is None:
            raise ValueError(f"error adding collection {name}")
    return int(row_id)


def set_options(
        db: DBConnector,
        collection_id: int,
        options: CollectionOptions,
        user: UUID | None) -> None:
    with db.get_session() as session:
        verify_user(session, collection_id, user, write=True)
        stmt = sa.update(DeepDiveCollection)
        stmt = stmt.where(DeepDiveCollection.id == collection_id)
        stmt = stmt.values(
            is_public=options["is_public"])
        session.execute(stmt)


def get_collections(db: DBConnector, user: UUID) -> Iterable[CollectionObj]:
    with db.get_session() as session:
        stmt = sa.select(
            DeepDiveCollection.id,
            DeepDiveCollection.name,
            DeepDiveCollection.deep_dive_key,
            DeepDiveCollection.is_public)
        stmt = stmt.where(sa.or_(
            DeepDiveCollection.user == user,
            DeepDiveCollection.is_public))
        stmt = stmt.order_by(DeepDiveCollection.id)
        for row in session.execute(stmt):
            yield {
                "id": int(row.id),
                "user": user,
                "name": row.name,
                "deep_dive_key": row.deep_dive_key,
                "is_public": row.is_public,
            }


def verify_user(
        session: Session,
        collection_id: int,
        user: UUID | None,
        *,
        write: bool,
        allow_none: bool = False) -> bool:
    if user is None:
        if not allow_none:
            raise PreventDefaultResponse(401, "invalid collection for user")
        return False
    stmt = sa.select(
        DeepDiveCollection.id,
        (DeepDiveCollection.user != user).label("is_readonly"))
    stmt = stmt.where(sa.and_(
        DeepDiveCollection.id == collection_id,
        sa.or_(
            DeepDiveCollection.user == user,
            sa.false() if write else DeepDiveCollection.is_public)))
    row = session.execute(stmt).one_or_none()
    if row is None or int(row.id) != collection_id:
        raise PreventDefaultResponse(401, "invalid collection for user")
    return bool(row.is_readonly)


def add_documents(
        db: DBConnector,
        collection_id: int,
        main_ids: list[str],
        user: UUID | None,
        *,
        allow_none: bool = False) -> list[int]:
    res: list[int] = []
    with db.get_session() as session:
        verify_user(
            session, collection_id, user, write=True, allow_none=allow_none)
        for main_id in main_ids:
            cstmt = db.upsert(DeepDiveElement).values(
                main_id=main_id,
                deep_dive_id=collection_id)
            cstmt = cstmt.on_conflict_do_nothing()
            cstmt = cstmt.returning(DeepDiveElement.id)
            eid = session.execute(cstmt).scalar()
            if eid is not None:
                res.append(int(eid))
    return res


def get_documents(
        db: DBConnector,
        collection_id: int,
        user: UUID | None,
        *,
        allow_none: bool = False) -> tuple[bool, list[DocumentObj]]:
    with db.get_session() as session:
        is_readonly = verify_user(
            session, collection_id, user, write=False, allow_none=allow_none)
        stmt = sa.select(
            DeepDiveElement.id,
            DeepDiveElement.deep_dive_id,
            DeepDiveElement.url,
            DeepDiveElement.title,
            DeepDiveElement.main_id,
            DeepDiveElement.is_valid,
            DeepDiveElement.verify_reason,
            DeepDiveElement.deep_dive_result,
            DeepDiveElement.error,
            DeepDiveElement.tag,
            DeepDiveElement.tag_reason,
            DeepDiveCollection.verify_key,
            DeepDiveCollection.deep_dive_key)
        stmt = stmt.where(sa.and_(
            DeepDiveElement.deep_dive_id == DeepDiveCollection.id,
            DeepDiveCollection.id == collection_id))
        stmt = stmt.order_by(DeepDiveElement.id)
        docs: list[DocumentObj] = [
            {
                "id": row.id,
                "main_id": row.main_id,
                "url": row.url,
                "title": row.title,
                "deep_dive": row.deep_dive_id,
                "verify_key": row.verify_key,
                "deep_dive_key": row.deep_dive_key,
                "is_valid": row.is_valid,
                "verify_reason": row.verify_reason,
                "deep_dive_result": row.deep_dive_result,
                "error": row.error,
                "tag": row.tag,
                "tag_reason": row.tag_reason,
            }
            for row in session.execute(stmt)
        ]
        return (is_readonly, docs)


def set_url_title(
        db: DBConnector,
        doc_id: int,
        url: str,
        title: str) -> None:
    with db.get_session() as session:
        stmt = sa.update(DeepDiveElement)
        stmt = stmt.where(DeepDiveElement.id == doc_id)
        stmt = stmt.values(
            url=url,
            title=title)
        session.execute(stmt)


def set_tag(
        db: DBConnector,
        doc_id: int,
        tag: str | None,
        tag_reason: str) -> None:
    with db.get_session() as session:
        stmt = sa.update(DeepDiveElement)
        stmt = stmt.where(DeepDiveElement.id == doc_id)
        stmt = stmt.values(
            tag=tag,
            tag_reason=tag_reason)
        session.execute(stmt)


def set_verify(
        db: DBConnector,
        doc_id: int,
        is_valid: bool,
        reason: str) -> None:
    with db.get_session() as session:
        stmt = sa.update(DeepDiveElement)
        stmt = stmt.where(DeepDiveElement.id == doc_id)
        stmt = stmt.values(
            verify_reason=reason,
            is_valid=is_valid)
        session.execute(stmt)


def set_deep_dive(
        db: DBConnector,
        doc_id: int,
        deep_dive: DeepDiveResult) -> None:
    with db.get_session() as session:
        stmt = sa.update(DeepDiveElement)
        stmt = stmt.where(DeepDiveElement.id == doc_id)
        stmt = stmt.values(deep_dive_result=deep_dive)
        session.execute(stmt)


def set_error(db: DBConnector, doc_id: int, error: str) -> None:
    with db.get_session() as session:
        stmt = sa.update(DeepDiveElement)
        stmt = stmt.where(DeepDiveElement.id == doc_id)
        stmt = stmt.values(error=error)
        session.execute(stmt)


def requeue(
        db: DBConnector,
        collection_id: int,
        user: UUID | None,
        main_ids: list[str],
        *,
        allow_none: bool = False) -> None:
    with db.get_session() as session:
        verify_user(
            session, collection_id, user, write=True, allow_none=allow_none)
        stmt = sa.update(DeepDiveElement)
        stmt = stmt.where(sa.and_(
            DeepDiveElement.deep_dive_id == collection_id,
            DeepDiveElement.main_id.in_(main_ids)))
        stmt = stmt.values(
            url=None,
            title=None,
            is_valid=None,
            verify_reason=None,
            deep_dive_result=sa.null(),
            error=None)
        session.execute(stmt)


def requeue_meta(
        db: DBConnector,
        collection_id: int,
        user: UUID | None,
        main_ids: list[str],
        *,
        allow_none: bool = False) -> None:
    with db.get_session() as session:
        verify_user(
            session, collection_id, user, write=True, allow_none=allow_none)
        stmt = sa.update(DeepDiveElement)
        stmt = stmt.where(sa.and_(
            DeepDiveElement.deep_dive_id == collection_id,
            DeepDiveElement.main_id.in_(main_ids)))
        stmt = stmt.values(url=None, title=None, tag=None, tag_reason=None)
        session.execute(stmt)


def get_documents_in_queue(db: DBConnector) -> Iterable[DocumentObj]:
    with db.get_session() as session:
        stmt = sa.select(
            DeepDiveElement.id,
            DeepDiveElement.deep_dive_id,
            DeepDiveElement.main_id,
            DeepDiveElement.url,
            DeepDiveElement.title,
            DeepDiveElement.is_valid,
            DeepDiveElement.verify_reason,
            DeepDiveElement.deep_dive_result,
            DeepDiveElement.error,
            DeepDiveElement.tag,
            DeepDiveElement.tag_reason,
            DeepDiveCollection.verify_key,
            DeepDiveCollection.deep_dive_key)
        stmt = stmt.where(sa.and_(
            DeepDiveElement.deep_dive_id == DeepDiveCollection.id,
            sa.or_(
                DeepDiveElement.url.is_(None),
                DeepDiveElement.title.is_(None),
                DeepDiveElement.is_valid.is_(None),
                DeepDiveElement.deep_dive_result.is_(None),
                DeepDiveElement.tag_reason.is_(None)),
            DeepDiveElement.error.is_(None)))
        for row in session.execute(stmt):
            yield {
                "id": row.id,
                "main_id": row.main_id,
                "url": row.url,
                "title": row.title,
                "deep_dive": row.deep_dive_id,
                "verify_key": row.verify_key,
                "deep_dive_key": row.deep_dive_key,
                "is_valid": row.is_valid,
                "verify_reason": row.verify_reason,
                "deep_dive_result": row.deep_dive_result,
                "error": row.error,
                "tag": row.tag,
                "tag_reason": row.tag_reason,
            }


def create_deep_dive_tables(db: DBConnector) -> None:
    db.create_tables([DeepDiveCollection, DeepDiveElement])
