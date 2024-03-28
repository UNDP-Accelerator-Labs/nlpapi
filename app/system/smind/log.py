from datetime import datetime

from app.system.db.base import QueryLog
from app.system.db.db import DBConnector


def log_query(db: DBConnector, *, db_name: str, text: str) -> None:
    date_str = datetime.today().strftime(r"%Y-%m-%d")
    with db.get_session() as session:
        stmt = db.upsert(QueryLog).values(
            vecdb=db_name,
            query=text,
            access_date=date_str)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                QueryLog.vecdb,
                QueryLog.query,
                QueryLog.access_date,
            ],
            set_={
                QueryLog.access_count: QueryLog.access_count + 1,
            })
        session.execute(stmt)


def create_query_log(db: DBConnector) -> None:
    db.create_tables([QueryLog])
