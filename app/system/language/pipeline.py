from uuid import UUID

from app.system.db.base import LocationUsers
from app.system.db.db import DBConnector
from app.system.language.spacy import get_lang, LangResponse


def extract_language(
        db: DBConnector, text: str, user: UUID) -> LangResponse:
    res = get_lang(text)
    with db.get_session() as session:
        total_length = len(text)
        stmt = db.upsert(LocationUsers).values(
            userid=user,
            language_count=1,
            language_length=total_length,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[LocationUsers.userid],
            set_={
                LocationUsers.language_count:
                    LocationUsers.language_count + 1,
                LocationUsers.language_length:
                    LocationUsers.language_length + total_length,
            })
        session.execute(stmt)
    return res
