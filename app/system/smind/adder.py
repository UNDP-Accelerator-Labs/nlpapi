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
from collections.abc import Callable
from typing import Literal, Protocol, TypedDict

from qdrant_client import QdrantClient
from redipy import Redis

from app.misc.util import DocStatus, get_time_str
from app.system.db.db import DBConnector
from app.system.location.response import LanguageStr
from app.system.prep.fulltext import (
    AllDocsFn,
    FullTextFn,
    get_base_doc,
    IsRemoveFn,
    StatusDateTypeFn,
    TagFn,
    UrlTitleFn,
)
from app.system.smind.api import GraphProfile
from app.system.smind.search import AddEmbed, vec_add
from app.system.smind.vec import MetaObject
from app.system.workqueues.queue import register_process_queue


AddDoc = TypedDict('AddDoc', {
    "total": int,
})


class AdderProcessor(Protocol):  # pylint: disable=too-few-public-methods
    def __call__(self, *, vdb_str: str, main_id: str, user: uuid.UUID) -> None:
        ...


class BaseProcessor(Protocol):  # pylint: disable=too-few-public-methods
    def __call__(
            self, *, vdb_str: str, bases: list[str], user: uuid.UUID) -> None:
        ...


AdderAddBasePayload = TypedDict('AdderAddBasePayload', {
    "stage": Literal["base"],
    "db": str,
    "base": str,
    "user": uuid.UUID,
})
AdderUpdateDocPayload = TypedDict('AdderUpdateDocPayload', {
    "stage": Literal["doc"],
    "db": str,
    "main_id": str,
    "user": uuid.UUID,
})
AdderPayload = AdderUpdateDocPayload | AdderAddBasePayload


def register_adder(
        db: DBConnector,
        vec_db: QdrantClient,
        *,
        process_queue_redis: Redis,
        qdrant_cache: Redis,
        graph_embed: GraphProfile,
        ner_graphs: dict[LanguageStr, GraphProfile],
        get_articles: Callable[[str], str],
        get_all_docs: AllDocsFn,
        doc_is_remove: IsRemoveFn,
        get_full_text: FullTextFn,
        get_url_title: UrlTitleFn,
        get_tag: TagFn,
        get_status_date_type: StatusDateTypeFn,
        ) -> tuple[BaseProcessor, AdderProcessor]:

    def adder_payload_to_json(entry: AdderPayload) -> dict[str, str]:
        if "stage" not in entry:
            entry["stage"] = "doc"
        if entry["stage"] == "base":
            return {
                "stage": "base",
                "db": entry["db"],
                "base": entry["base"],
                "user": entry["user"].hex,
            }
        return {
            "stage": "doc",
            "db": entry["db"],
            "main_id": entry["main_id"],
            "user": entry["user"].hex,
        }

    def adder_payload_from_json(payload: dict[str, str]) -> AdderPayload:
        if "stage" not in payload:
            payload["stage"] = "doc"
        if payload["stage"] == "base":
            return {
                "stage": "base",
                "db": payload["db"],
                "base": payload["base"],
                "user": uuid.UUID(payload["user"]),
            }
        return {
            "stage": "doc",
            "db": payload["db"],
            "main_id": payload["main_id"],
            "user": uuid.UUID(payload["user"]),
        }

    def adder_compute(entry: AdderPayload) -> AddEmbed | AddDoc:
        vdb_str = entry["db"]
        user = entry["user"]
        if entry["stage"] == "base":
            total = 0
            for cur_main_id in get_all_docs(entry["base"]):
                adder_processor(
                    vdb_str=vdb_str, main_id=cur_main_id, user=user)
                total += 1
            return {
                "total": total,
            }
        main_id = entry["main_id"]
        is_remove, error_remove = doc_is_remove(main_id)
        if error_remove is not None:
            raise ValueError(error_remove)
        base, doc_id = get_base_doc(main_id)
        articles = get_articles(vdb_str)
        if not is_remove:
            input_str, error_input = get_full_text(main_id)
            if input_str is None:
                raise ValueError(error_input)
        else:
            input_str = ""
        if not is_remove:
            info, error_info = get_url_title(main_id)
            if info is None:
                raise ValueError(error_info)
            url, title = info
        else:
            url = "-"
            title = "-"
        sdt: tuple[DocStatus, str | None, str] | None
        error_sdt: str | None = "unknown error"
        if not is_remove:
            sdt, error_sdt = get_status_date_type(main_id)
        else:
            sdt = ("public", get_time_str(), "solution")
        if sdt is None:
            raise ValueError(error_sdt)
        status, date_str, doc_type = sdt
        meta_obj: MetaObject = {
            "status": status,
            "date": date_str,
            "doc_type": doc_type,
        }
        return vec_add(
            db,
            vec_db,
            input_str,
            qdrant_cache=qdrant_cache,
            articles=articles,
            articles_graph=graph_embed,
            ner_graphs=ner_graphs,
            get_tag=get_tag,
            user=user,
            base=base,
            doc_id=doc_id,
            url=url,
            title=title,
            meta_obj=meta_obj)

    process_enqueue = register_process_queue(
        "adder",
        adder_payload_to_json,
        adder_payload_from_json,
        adder_compute)

    def base_processor(
            *, vdb_str: str, bases: list[str], user: uuid.UUID) -> None:
        for base in bases:
            process_enqueue(
                process_queue_redis,
                {
                    "stage": "base",
                    "db": vdb_str,
                    "base": base,
                    "user": user,
                })

    def adder_processor(
            *, vdb_str: str, main_id: str, user: uuid.UUID) -> None:
        process_enqueue(
            process_queue_redis,
            {
                "stage": "doc",
                "db": vdb_str,
                "main_id": main_id,
                "user": user,
            })

    return base_processor, adder_processor
