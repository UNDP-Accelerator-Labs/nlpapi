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

from app.system.db.base import DeepDiveCollection, DeepDiveElement
from app.system.db.db import DBConnector


CollectionObj = TypedDict('CollectionObj', {
    "id": int,
    "user": UUID,
    "name": str,
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
    "deep_dive": int,
    "verify_key": str,
    "deep_dive_key": str,
    "is_valid": bool | None,
    "verify_reason": str | None,
    "deep_dive_result": DeepDiveResult | None,
    "error": str | None,
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


def get_collections(db: DBConnector, user: UUID) -> Iterable[CollectionObj]:
    with db.get_session() as session:
        stmt = sa.select(DeepDiveCollection.id, DeepDiveCollection.name)
        stmt = stmt.where(DeepDiveCollection.user == user)
        for row in session.execute(stmt):
            yield {
                "id": int(row.id),
                "user": user,
                "name": row.name,
            }


def add_documents(
        db: DBConnector,
        collection_id: int,
        main_ids: list[str]) -> list[int]:
    res: list[int] = []
    with db.get_session() as session:
        for main_id in main_ids:
            cstmt = db.upsert(DeepDiveElement).values(
                main_id=main_id,
                deep_dive_id=collection_id)
            cstmt = cstmt.returning(DeepDiveElement.id)
            eid = session.execute(cstmt).scalar()
            if eid is None:
                raise ValueError(f"error adding documents: {main_ids}")
            res.append(int(eid))
    return res


def get_documents(
        db: DBConnector, collection_id: int) -> Iterable[DocumentObj]:
    with db.get_session() as session:
        stmt = sa.select(
            DeepDiveElement.id,
            DeepDiveElement.deep_dive_id,
            DeepDiveElement.main_id,
            DeepDiveElement.is_valid,
            DeepDiveElement.verify_reason,
            DeepDiveElement.deep_dive_result,
            DeepDiveElement.error,
            DeepDiveCollection.verify_key,
            DeepDiveCollection.deep_dive_key,
            ).join(DeepDiveElement.deep_dive_id)
        stmt = stmt.where(DeepDiveCollection.id == collection_id)
        for row in session.execute(stmt):
            yield {
                "id": row.id,
                "main_id": row.main_id,
                "deep_dive": row.deep_dive_id,
                "verify_key": row.verify_key,
                "deep_dive_key": row.deep_dive_key,
                "is_valid": row.is_valid,
                "verify_reason": row.verify_reason,
                "deep_dive_result": row.deep_dive_result,
                "error": row.error,
            }


def set_verify(
        db: DBConnector,
        doc_id: int,
        is_valid: bool | None,
        reason: str | None) -> None:
    if (is_valid is None) != (reason is None):
        raise ValueError(
            f"either both are None or neither {is_valid=} {reason=}")
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
        deep_dive: DeepDiveResult | None) -> None:
    with db.get_session() as session:
        stmt = sa.update(DeepDiveElement)
        stmt = stmt.where(DeepDiveElement.id == doc_id)
        stmt = stmt.values(deep_dive_result=deep_dive)
        session.execute(stmt)


def set_error(db: DBConnector, doc_id: int, error: str | None) -> None:
    with db.get_session() as session:
        stmt = sa.update(DeepDiveElement)
        stmt = stmt.where(DeepDiveElement.id == doc_id)
        stmt = stmt.values(error=error)
        session.execute(stmt)


def get_documents_in_queue(db: DBConnector) -> Iterable[DocumentObj]:
    with db.get_session() as session:
        stmt = sa.select(
            DeepDiveElement.id,
            DeepDiveElement.deep_dive_id,
            DeepDiveElement.main_id,
            DeepDiveElement.is_valid,
            DeepDiveElement.verify_reason,
            DeepDiveElement.deep_dive_result,
            DeepDiveElement.error,
            DeepDiveCollection.verify_key,
            DeepDiveCollection.deep_dive_key,
            ).join(DeepDiveElement.deep_dive_id)
        stmt = stmt.where(sa.and_(
            sa.or_(
                DeepDiveElement.is_valid.is_(None),
                DeepDiveElement.deep_dive_result.is_(None)),
            DeepDiveElement.error.is_(None)))
        for row in session.execute(stmt):
            yield {
                "id": row.id,
                "main_id": row.main_id,
                "deep_dive": row.deep_dive_id,
                "verify_key": row.verify_key,
                "deep_dive_key": row.deep_dive_key,
                "is_valid": row.is_valid,
                "verify_reason": row.verify_reason,
                "deep_dive_result": row.deep_dive_result,
                "error": row.error,
            }


def create_deep_dive_tables(db: DBConnector) -> None:
    db.create_tables([DeepDiveCollection, DeepDiveElement])
