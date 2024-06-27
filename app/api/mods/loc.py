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
