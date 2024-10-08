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
"""The language module."""
import uuid
from collections.abc import Mapping
from typing import Any

from app.api.mod import Module
from app.system.db.db import DBConnector
from app.system.language.pipeline import extract_language


class LanguageModule(Module):
    """The language module."""
    def __init__(self, db: DBConnector) -> None:
        self._db = db

    @staticmethod
    def name() -> str:
        return "language"

    def execute(
            self,
            input_str: str,
            user: uuid.UUID,
            args: dict[str, Any]) -> Mapping[str, Any]:
        return extract_language(self._db, input_str, user)
