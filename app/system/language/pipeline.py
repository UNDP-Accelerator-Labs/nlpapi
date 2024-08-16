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
"""Pipeline for extracting languages."""
from uuid import UUID

from app.system.db.base import LocationUsers
from app.system.db.db import DBConnector
from app.system.language.langdetect import get_lang, LangResponse
from app.system.stats import create_length_counter


def extract_language(
        db: DBConnector, text: str, user: UUID) -> LangResponse:
    """
    Extracts the language for a user and keeps track of the overall api usage.

    Args:
        db (DBConnector): The database connector.
        text (str): The full text.
        user (UUID): The user uuid.

    Returns:
        LangResponse: The language results.
    """
    lnc, lnr = create_length_counter()
    res = get_lang(text, lnc)
    with db.get_session() as session:
        total_length = lnr()
        stmt = db.upsert(LocationUsers).values(
            userid=user,
            language_count=1,
            language_length=total_length)
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
