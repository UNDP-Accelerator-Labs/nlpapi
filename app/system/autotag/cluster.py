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
import collections
from typing import Protocol, TypedDict

from redipy import Redis
from scattermind.system.torch_util import tensor_to_str

from app.misc.util import CHUNK_PADDING, CHUNK_SIZE, NL, only
from app.system.autotag.autotag import write_tag
from app.system.db.db import DBConnector
from app.system.prep.fulltext import FullTextFn
from app.system.prep.snippify import snippify_text
from app.system.smind.api import GraphProfile
from app.system.workqueues.queue import register_process_queue


class TaggerProcessor(Protocol):  # pylint: disable=too-few-public-methods
    def __call__(self, *, tag_group: int, main_id: str) -> None:
        ...


TaggerPayload = TypedDict('TaggerPayload', {
    "tag_group": int,
    "main_id": str,
})


TOP_K = 10


def register_tagger(
        db: DBConnector,
        *,
        process_queue_redis: Redis,
        graph_tags: GraphProfile,
        get_full_text: FullTextFn) -> TaggerProcessor:

    def tagger_payload_to_json(entry: TaggerPayload) -> dict[str, str]:
        return {
            "tag_group": f"{entry['tag_group']}",
            "main_id": entry["main_id"],
        }

    def tagger_payload_from_json(payload: dict[str, str]) -> TaggerPayload:
        return {
            "tag_group": int(payload["tag_group"]),
            "main_id": payload["main_id"],
        }

    def tagger_compute(entry: TaggerPayload) -> str:
        tag_group = entry["tag_group"]
        main_id = entry["main_id"]
        keywords, error = tag_doc(
            main_id,
            graph_tags=graph_tags,
            get_full_text=get_full_text,
            top_k=TOP_K)
        if keywords is None:
            raise ValueError(f"error while processing {main_id}:\n{error}")
        write_tag(db, tag_group, main_id, list(keywords))
        return f"finished {main_id}"

    process_enqueue = register_process_queue(
        "tagger",
        tagger_payload_to_json,
        tagger_payload_from_json,
        tagger_compute)

    def tagger_processor(*, tag_group: int, main_id: str) -> None:
        process_enqueue(
            process_queue_redis,
            {
                "tag_group": tag_group,
                "main_id": main_id,
            })

    return tagger_processor


def tag_doc(
        main_id: str,
        *,
        graph_tags: GraphProfile,
        get_full_text: FullTextFn,
        top_k: int) -> tuple[set[str] | None, str | None]:
    full_text, error_ft = get_full_text(main_id)
    if full_text is None:
        return None, error_ft
    smind = graph_tags.get_api()
    ns = graph_tags.get_ns()
    input_field = only(graph_tags.get_input_fields())
    texts = [
        snippet
        for (snippet, _) in snippify_text(
            full_text,
            chunk_size=CHUNK_SIZE,
            chunk_padding=CHUNK_PADDING)
    ]
    tasks = [
        smind.enqueue_task(
            ns,
            {
                input_field: text,
            })
        for text in texts
    ]
    success = True
    error_msg = ""
    kwords: collections.defaultdict[str, float] = \
        collections.defaultdict(lambda: 0.0)
    for tid, resp in smind.wait_for(tasks, timeout=300, auto_clear=True):
        if resp["error"] is not None:
            error = resp["error"]
            error_msg = (
                f"{error_msg}\n{error['code']} ({error['ctx']}): "
                f"{error['message']}\n{NL.join(error['traceback'])}")
            success = False
            continue
        result = resp["result"]
        if result is None:
            error_msg = f"{error_msg}\nmissing result for {tid}"
            success = False
            continue
        keywords = tensor_to_str(result["tags"]).split(",")
        scores = list(result["scores"].cpu().tolist())
        if len(keywords) != len(scores):
            error_msg = (
                f"{error_msg}\nkeywords and scores mismatch: "
                f"{keywords=} {scores=}")
            success = False
            continue
        for keyword, score in zip(keywords, scores):
            kwords[keyword] += score
    if not success:
        return None, error_msg
    top_kwords = sorted(
        kwords.items(),
        key=lambda wordscore: wordscore[1],
        reverse=True)[:top_k]
    return {kword for (kword, _) in top_kwords}, None
