from datetime import datetime

from app.misc.util import json_compact_str
from app.system.db.base import QueryLog
from app.system.db.db import DBConnector
from app.system.smind.vec import MetaKey


def log_query(
        db: DBConnector,
        *,
        db_name: str,
        text: str,
        filters: dict[MetaKey, list[str]] | None) -> None:
    if filters is None:
        filters_obj: dict[MetaKey, list[str]] = {}
    else:
        filters_obj = {
            key: value
            for (key, value) in filters.items()
            if value
        }
    filters_str = json_compact_str(filters_obj)
    date_str = datetime.today().strftime(r"%Y-%m-%d")
    with db.get_session() as session:
        stmt = db.upsert(QueryLog).values(
            vecdb=db_name,
            query=text,
            filters=filters_str,
            access_date=date_str)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                QueryLog.vecdb,
                QueryLog.query,
                QueryLog.filters,
                QueryLog.access_date,
            ],
            set_={
                QueryLog.access_count: QueryLog.access_count + 1,
            })
        session.execute(stmt)


def create_query_log(db: DBConnector) -> None:
    db.create_tables([QueryLog])
