import uuid
from collections.abc import Mapping
from typing import Any

from app.api.mod import Module
from app.system.db.db import DBConnector
from app.system.location.pipeline import extract_locations
from app.system.location.response import (
    DEFAULT_MAX_REQUESTS,
    GeoQuery,
    LanguageStr,
)
from app.system.smind.api import GraphProfile


class LocationModule(Module):
    def __init__(
            self,
            db: DBConnector,
            ner_graphs: dict[LanguageStr, GraphProfile]) -> None:
        self._db = db
        self._ner_graphs = ner_graphs

    @staticmethod
    def name() -> str:
        return "location"

    def execute(
            self,
            input_str: str,
            user: uuid.UUID,
            args: dict[str, Any]) -> Mapping[str, Any]:
        obj: GeoQuery = {
            "input": input_str,
            "return_input": args.get("return_input", False),
            "return_context": args.get("return_context", True),
            "strategy": args.get("strategy", "top"),
            "language": args.get("language", "en"),
            "max_requests": args.get("max_requests", DEFAULT_MAX_REQUESTS),
        }
        return extract_locations(self._db, self._ner_graphs, obj, user)
