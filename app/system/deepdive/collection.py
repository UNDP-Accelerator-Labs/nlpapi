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
            }


def create_deep_dive_tables(db: DBConnector) -> None:
    db.create_tables([DeepDiveCollection, DeepDiveElement])
