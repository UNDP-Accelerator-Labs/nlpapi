from collections.abc import Callable
from typing import Literal, TYPE_CHECKING

import torch


if TYPE_CHECKING:
    from app.system.config import Config


FeedbackAction = Literal["approve", "dislike", "neutral"]
FB_APPROVE: FeedbackAction = "approve"
FB_DISLIKE: FeedbackAction = "dislike"
FB_NEUTRAL: FeedbackAction = "neutral"


class Ops:
    def __init__(self, config: 'Config') -> None:
        self._config = config

    def get_config(self) -> 'Config':
        return self._config

    def init(self) -> None:
        raise NotImplementedError()

    def add_source(self, name: str) -> None:
        raise NotImplementedError()

    def get_sources(self) -> list[str]:
        raise NotImplementedError()

    def add_corpus(self, name: str, model: str, version: int) -> None:
        raise NotImplementedError()

    def add_sources_to_corpus(self, corpus: str, sources: list[str]) -> None:
        raise NotImplementedError()

    def is_corpus_active(self, corpus: str) -> bool:
        raise NotImplementedError()

    def set_corpus_active(self, corpus: str, active: bool) -> None:
        raise NotImplementedError()

    def get_corpora(self) -> list[str]:
        raise NotImplementedError()

    def add_document(
            self, source: str, searchable: str, reference: str) -> int:
        raise NotImplementedError()

    def add_feedback(
            self,
            doc_id: int,
            model: str,
            prompt: str,
            action: FeedbackAction) -> None:
        raise NotImplementedError()

    def add_model(self, name: str, base: str, model_hash: str) -> None:
        raise NotImplementedError()

    def add_embedding(
            self,
            doc_id: int,
            model: str,
            embedding: torch.Tensor) -> None:
        raise NotImplementedError()

    def get_new_documents(self) -> list[tuple[str, int]]:
        raise NotImplementedError()

    def add_embedding_listener(self, cback: Callable[[], None]) -> None:
        raise NotImplementedError()


def get_ops(name: Literal["db"], config: 'Config') -> Ops:
    if name == "db":
        from app.system.ops.db import DbOps  # pylint: disable=cyclic-import

        return DbOps(config)
    raise ValueError(f"invalid name: {name}")
