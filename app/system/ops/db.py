import gzip
import io
from typing import Callable, Sequence

import numpy as np
import sqlalchemy as sa
import torch
from sqlalchemy.orm import InstrumentedAttribute

from app.misc.util import safe_ravel
from app.system.config import Config
from app.system.db.base import (
    CorpusSourcesTable,
    CorpusTable,
    DocsTable,
    EmbedTable,
    FeedbackTable,
    ModelsTable,
    SourceTable,
)
from app.system.db.db import DBConnector
from app.system.ops.ops import (
    FB_APPROVE,
    FB_DISLIKE,
    FB_NEUTRAL,
    FeedbackAction,
    Ops,
)


class DbOps(Ops):
    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._db = DBConnector(config["db"])
        self._source_cache: dict[str, int] | None = None
        self._corpus_cache: dict[str, int] | None = None
        self._model_cache: dict[str, int] | None = None
        self._embedding_listeners: list[Callable[[], None]] = []

    def _get_sources(self) -> dict[str, int]:
        if self._source_cache is None:
            with self._db.get_connection() as conn:
                stmt = sa.select(SourceTable.name, SourceTable.id)
                self._source_cache = {
                    row.name: row.id
                    for row in conn.execute(stmt)
                }
        return self._source_cache

    def _get_corpora(self) -> dict[str, int]:
        if self._corpus_cache is None:
            with self._db.get_connection() as conn:
                stmt = sa.select(CorpusTable.name, CorpusTable.id)
                self._corpus_cache = {
                    row.name: row.id
                    for row in conn.execute(stmt)
                }
        return self._corpus_cache

    def _get_models(self) -> dict[str, int]:
        if self._model_cache is None:
            with self._db.get_connection() as conn:
                stmt = sa.select(ModelsTable.name, ModelsTable.id)
                self._model_cache = {
                    row.name: row.id
                    for row in conn.execute(stmt)
                }
        return self._model_cache

    def init(self) -> None:
        self._db.init_db()

    def add_source(self, name: str) -> None:
        with self._db.get_session() as session:
            stmt = self._db.upsert(SourceTable).values(name=name)
            stmt = stmt.on_conflict_do_nothing()
            session.execute(stmt)
        self._source_cache = None

    def add_model(self, name: str, base: str, model_hash: str) -> None:
        with self._db.get_session() as session:
            stmt = self._db.upsert(ModelsTable).values(
                name=name,
                base=base,
                model_hash=model_hash)
            stmt = stmt.on_conflict_do_nothing()
            session.execute(stmt)
        self._model_cache = None

    def add_corpus(self, name: str, model: str, version: int) -> None:
        model_id = self._get_models().get(model)
        if model_id is None:
            raise ValueError(f"unknown model: {model}")
        with self._db.get_session() as session:
            stmt = self._db.upsert(CorpusTable).values(
                name=name,
                model=model_id,
                version=version,
                active=False)
            stmt = stmt.on_conflict_do_nothing()
            session.execute(stmt)
        self._corpus_cache = None

    def set_corpus_active(self, corpus: str, active: bool) -> None:
        with self._db.get_session() as session:
            stmt = sa.update(CorpusTable).where(
                CorpusTable.name == corpus).values(active=active)
            session.execute(stmt)
            astmt = sa.select(CorpusTable.active)
            astmt = astmt.where(CorpusTable.name == corpus)
            is_active = session.execute(astmt).scalar()
        if is_active:
            self._compute_new_embeddings()

    def get_sources(self) -> list[str]:
        return sorted(self._get_sources().keys())

    def add_sources_to_corpus(self, corpus: str, sources: list[str]) -> None:
        with self._db.get_session() as session:
            astmt = sa.select(CorpusTable.id, CorpusTable.active)
            astmt = astmt.where(CorpusTable.name == corpus)
            row = session.execute(astmt).first()
            if row is None:
                raise ValueError(f"{corpus} doesn't exist")
            corpus_id = row.id
            is_active = row.active
            if is_active:
                raise ValueError(
                    f"{corpus} is active. corpora must not be "
                    "active when adding sources")
            source_ids = sa.select(SourceTable.id).where(
                SourceTable.name.in_(sorted(set(sources))))
            stmt = self._db.upsert(CorpusSourcesTable).values(
                [
                    {
                        "corpus_id": corpus_id,
                        "source_id": source.id,
                    }
                    for source in session.execute(source_ids)
                ])
            stmt = stmt.on_conflict_do_nothing()
            session.execute(stmt)

    def is_corpus_active(self, corpus: str) -> bool:
        with self._db.get_session() as session:
            stmt = sa.select(CorpusTable.active)
            stmt = stmt.where(CorpusTable.name == corpus)
            return bool(session.execute(stmt).scalar())

    def get_corpora(self) -> list[str]:
        return sorted(self._get_corpora().keys())

    def add_document(
            self, source: str, searchable: str, reference: str) -> int:
        source_id = self._get_sources().get(source)
        if source_id is None:
            raise ValueError(f"unknown source: {source}")
        with self._db.get_session() as session:
            stmt = sa.insert(DocsTable).values(
                source_id=source_id,
                searchable=searchable,
                reference=reference).returning(DocsTable.id)
            res = session.execute(stmt).scalar()
            if res is None:
                raise ValueError(
                    "error while inserting: "
                    f"{source} {searchable} {reference}")
            self._compute_new_embeddings()
            return res

    def add_feedback(
            self,
            doc_id: int,
            model: str,
            prompt: str,
            action: FeedbackAction) -> None:
        model_id = self._get_models().get(model)
        if model_id is None:
            raise ValueError(f"unknown model: {model}")
        actions: dict[FeedbackAction, InstrumentedAttribute[int | None]] = {
            FB_APPROVE: FeedbackTable.approve,
            FB_DISLIKE: FeedbackTable.dislike,
            FB_NEUTRAL: FeedbackTable.neutral,
        }
        action_col = actions.get(action)
        if action_col is None:
            raise ValueError(f"unknown action: {action}")
        with self._db.get_session() as session:
            stmt = self._db.upsert(FeedbackTable).values(
                {
                    FeedbackTable.model_id: model_id,
                    FeedbackTable.doc_id: doc_id,
                    FeedbackTable.prompt: prompt,
                    action_col: action_col + 1,
                })
            session.execute(stmt)

    def add_embedding_listener(self, cback: Callable[[], None]) -> None:
        self._embedding_listeners.append(cback)

    def _compute_new_embeddings(self) -> None:
        for cback in self._embedding_listeners:
            cback()

    @staticmethod
    def _to_tensor(arr: Sequence[float]) -> torch.Tensor:
        return torch.DoubleTensor(list(arr))

    @staticmethod
    def _from_tensor(x: torch.Tensor) -> Sequence[float]:
        return safe_ravel(x.double().detach()).numpy().astype(np.float64)

    @staticmethod
    def _serialize(embed: torch.Tensor) -> bytes:
        bout = io.BytesIO()
        with gzip.GzipFile(fileobj=bout, mode="w") as fout:
            np.save(
                fout,
                safe_ravel(embed).double().detach().numpy().astype(np.float64))
        return bout.getvalue()

    @staticmethod
    def _deserialize(content: bytes) -> torch.Tensor:
        binp = io.BytesIO(content)
        with gzip.GzipFile(fileobj=binp, mode="r") as finp:
            return torch.DoubleTensor(np.load(finp))

    def add_embedding(
            self,
            doc_id: int,
            model: str,
            embedding: torch.Tensor) -> None:
        model_id = self._get_models().get(model)
        if model_id is None:
            raise ValueError(f"unknown model: {model}")
        with self._db.get_session() as session:
            stmt = self._db.upsert(EmbedTable).values({
                EmbedTable.model_id: model_id,
                EmbedTable.doc_id: doc_id,
                EmbedTable.embedding: self._serialize(embedding),
            })
            stmt = stmt.on_conflict_do_nothing()
            session.execute(stmt)

    def get_new_documents(self) -> list[tuple[str, int]]:
        with self._db.get_session() as session:
            stmt = sa.select(ModelsTable.name, DocsTable.id)
            stmt = stmt.join(sa.and_(
                ModelsTable.id == EmbedTable.model_id,
                DocsTable.id == EmbedTable.doc_id))
            stmt = stmt.where(sa.and_(
                EmbedTable.model_id.is_(None),
                EmbedTable.doc_id.is_(None),
                DocsTable.source_id == CorpusSourcesTable.source_id,
                CorpusTable.id == CorpusSourcesTable.corpus_id,
                ModelsTable.id == CorpusTable.model_id))
            return [
                (row.name, row.id)
                for row in session.execute(stmt)
            ]
