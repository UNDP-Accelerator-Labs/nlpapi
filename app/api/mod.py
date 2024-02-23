import uuid
from collections.abc import Mapping
from typing import Any


class Module:
    @staticmethod
    def name() -> str:
        raise NotImplementedError()

    def execute(
            self,
            input_str: str,
            user: uuid.UUID,
            args: dict[str, Any]) -> Mapping[str, Any]:
        raise NotImplementedError()
