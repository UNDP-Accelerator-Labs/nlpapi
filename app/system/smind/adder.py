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
from typing import Protocol

from qdrant_client import QdrantClient
from redipy import Redis

from app.api.server import AdderPayload
from app.system.db.db import DBConnector
from app.system.location.response import LanguageStr
from app.system.prep.fulltext import (
    FullTextFn,
    get_base_doc,
    StatusDateTypeFn,
    TagFn,
    UrlTitleFn,
)
from app.system.smind.api import GraphProfile
from app.system.smind.search import vec_add
from app.system.smind.vec import AddEmbed, MetaObject
from app.system.workqueues.queue import process_enqueue, register_process_queue


class AdderProcessor(Protocol):  # pylint: disable=too-few-public-methods
    def __call__(self, *, vdb_str: str, main_id: str, user: uuid.UUID) -> None:
        ...


def register_adder(
        db: DBConnector,
        vec_db: QdrantClient,
        *,
        process_queue_redis: Redis,
        qdrant_cache: Redis,
        graph_embed: GraphProfile,
        ner_graphs: dict[LanguageStr, GraphProfile],
        get_articles: Callable[[str], str],
        get_full_text: FullTextFn,
        get_url_title: UrlTitleFn,
        get_tag: TagFn,
        get_status_date_type: StatusDateTypeFn,
        ) -> AdderProcessor:

    def adder_payload_to_json(entry: AdderPayload) -> dict[str, str]:
        return {
            "db": entry["db"],
            "main_id": entry["main_id"],
            "user": entry["user"].hex,
        }

    def adder_payload_from_json(payload: dict[str, str]) -> AdderPayload:
        return {
            "db": payload["db"],
            "main_id": payload["main_id"],
            "user": uuid.UUID(payload["user"]),
        }

    def adder_compute(entry: AdderPayload) -> AddEmbed:
        vdb_str = entry["db"]
        main_id = entry["main_id"]
        user = entry["user"]
        base, doc_id = get_base_doc(main_id)
        articles = get_articles(vdb_str)
        input_str, error_input = get_full_text(main_id)
        if input_str is None:
            raise ValueError(error_input)
        info, error_info = get_url_title(main_id)
        if info is None:
            raise ValueError(error_info)
        url, title = info
        sdt, error_sdt = get_status_date_type(main_id)
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

    adder_hnd = register_process_queue(
        "adder",
        adder_payload_to_json,
        adder_payload_from_json,
        adder_compute)

    def adder_processor(
            *, vdb_str: str, main_id: str, user: uuid.UUID) -> None:
        process_enqueue(
            process_queue_redis,
            adder_hnd,
            {
                "db": vdb_str,
                "main_id": main_id,
                "user": user,
            })

    return adder_processor
