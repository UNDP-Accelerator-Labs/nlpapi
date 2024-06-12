import sqlalchemy as sa

from app.system.db.base import DeepDiveCollection, DeepDiveElements
from app.system.db.db import DBConnector


def get_deep_dive_keys(deep_dive: str) -> tuple[str, str]:
    if deep_dive == "circular_economy":
        return ("verify_circular_economy", "rate_circular_economy")
    raise ValueError(f"unknown {deep_dive=}")


def add_collection(db: DBConnector, name: str, deep_dive: str) -> int:
    verify_key, deep_dive_key = get_deep_dive_keys(deep_dive)
    with db.get_session() as session:
        # FIXME: finish up
        stmt = sa.insert(DeepDiveCollection).values(
            name=name,
            verify_key=verify_key,
            deep_dive_key=deep_dive_key)
        session.execute(stmt)
    return 0


def create_deep_dive_tables(db: DBConnector) -> None:
    db.create_tables([DeepDiveCollection, DeepDiveElements])
