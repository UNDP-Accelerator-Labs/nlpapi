
import uuid
from collections.abc import Mapping
from typing import Any

from app.api.mod import Module
from app.system.db.db import DBConnector
from app.system.language.pipeline import extract_language


class LanguageModule(Module):
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
