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
import sqlalchemy as sa

from app.system.db.base import (
    TagCluster,
    TagClusterMember,
    TagGroupMembers,
    TagGroupTable,
    TagsTable,
)
from app.system.db.db import DBConnector


def create_tag_group(db: DBConnector, main_ids: list[str]) -> int:
    with db.get_session() as session:
        stmt = sa.insert(TagGroupTable).values(
            name=name,
            user=user,
            verify_key=verify_key,
            deep_dive_key=deep_dive_key)
        stmt = stmt.returning(DeepDiveCollection.id)
        row_id = session.execute(stmt).scalar()
        if row_id is None:
            raise ValueError(f"error adding collection {name}")
    return int(row_id)


def create_tag_tables(db: DBConnector) -> None:
    db.create_tables(
        [
            TagGroupTable,
            TagGroupMembers,
            TagsTable,
            TagCluster,
            TagClusterMember,
        ])
