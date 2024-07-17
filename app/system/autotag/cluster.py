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
from typing import Literal, Protocol, TypedDict

from redipy import Redis
from scattermind.system.torch_util import tensor_to_str

from app.misc.util import CHUNK_PADDING, CHUNK_SIZE, NL, only
from app.system.autotag.autotag import (
    add_tag_members,
    create_tag_group,
    get_incomplete,
    is_ready,
    write_tag,
)
from app.system.db.db import DBConnector
from app.system.prep.fulltext import AllDocsFn, FullTextFn, IsRemoveFn
from app.system.prep.snippify import snippify_text
from app.system.smind.api import GraphProfile
from app.system.workqueues.queue import register_process_queue


class TaggerProcessor(Protocol):  # pylint: disable=too-few-public-methods
    def __call__(self, *, name: str | None, bases: list[str]) -> None:
        ...


InitTaggerPayload = TypedDict('InitTaggerPayload', {
    "stage": Literal["init"],
    "name": str | None,
    "bases": list[str],
})
TagTaggerPayload = TypedDict('TagTaggerPayload', {
    "stage": Literal["tag"],
})
CluterTaggerPayload = TypedDict('CluterTaggerPayload', {
    "stage": Literal["cluster"],
    "tag_group": int,
})
TaggerPayload = InitTaggerPayload | TagTaggerPayload | CluterTaggerPayload


BATCH_SIZE = 20
TOP_K = 10


def register_tagger(
        db: DBConnector,
        *,
        process_queue_redis: Redis,
        graph_tags: GraphProfile,
        get_all_docs: AllDocsFn,
        is_remove_doc: IsRemoveFn,
        get_full_text: FullTextFn) -> TaggerProcessor:

    def tagger_payload_to_json(entry: TaggerPayload) -> dict[str, str]:
        if entry["stage"] == "init":
            return {
                "stage": "init",
                "name": "" if entry["name"] is None else entry["name"],
                "bases": ",".join(entry["bases"]),
            }
        if entry["stage"] == "tag":
            return {
                "stage": "tag",
            }
        if entry["stage"] == "cluster":
            return {
                "stage": "cluster",
                "tag_group": f"{entry['tag_group']}",
            }
        raise ValueError(f"invalid stage {entry['stage']}")

    def tagger_payload_from_json(payload: dict[str, str]) -> TaggerPayload:
        if payload["stage"] == "init":
            return {
                "stage": "init",
                "name": payload["name"] if payload["name"] else None,
                "bases": payload["bases"].split(","),
            }
        if payload["stage"] == "tag":
            return {
                "stage": "tag",
            }
        if payload["stage"] == "cluster":
            return {
                "stage": "cluster",
                "tag_group": int(payload['tag_group']),
            }
        raise ValueError(f"invalid stage {payload['stage']}")

    def tagger_compute(entry: TaggerPayload) -> str:
        if entry["stage"] == "init":
            total = 0
            with db.get_session() as session:
                cur_tag_group = create_tag_group(session, entry["name"])
                for base in entry["bases"]:
                    cur_main_ids: list[str] = []
                    for cur_main_id in get_all_docs(base):
                        if is_remove_doc(cur_main_id):
                            continue
                        cur_main_ids.append(cur_main_id)
                    add_tag_members(
                        db, session, cur_tag_group, cur_main_ids)
                    total += len(cur_main_ids)
                process_enqueue(
                    process_queue_redis,
                    {
                        "stage": "tag",
                    })
            return f"created tag group {cur_tag_group} with {total} entries"
        if entry["stage"] == "tag":
            batch_size = BATCH_SIZE
            with db.get_session() as session:
                processing_count = 0
                tag_groups: set[int] = set()
                errors: list[str] = []
                for elem in get_incomplete(session):
                    main_id = elem["main_id"]
                    tag_group = elem["tag_group"]
                    keywords, error = tag_doc(
                        main_id,
                        graph_tags=graph_tags,
                        get_full_text=get_full_text,
                        top_k=TOP_K)
                    if keywords is None:
                        errors.append(
                            "error while processing "
                            f"{main_id} for {tag_group}:\n{error}")
                    else:
                        write_tag(
                            db,
                            session,
                            tag_group,
                            main_id,
                            list(keywords))
                    tag_groups.add(tag_group)
                    processing_count += 1
                    if processing_count >= batch_size:
                        break
                if processing_count > 0:
                    process_enqueue(
                        process_queue_redis,
                        {
                            "stage": "tag",
                        })
                for tag_group in tag_groups:
                    if is_ready(session, tag_group):
                        process_enqueue(
                            process_queue_redis,
                            {
                                "stage": "cluster",
                                "tag_group": tag_group,
                            })
                if errors:
                    raise ValueError(
                        f"errors while processing:\n{NL.join(errors)}")
            return f"finished {main_id}"
        if entry["stage"] == "cluster":
            # FIXME
            return "TODO"
        raise ValueError(f"invalid stage {entry['stage']}")

    process_enqueue = register_process_queue(
        "tagger",
        tagger_payload_to_json,
        tagger_payload_from_json,
        tagger_compute)

    def tagger_processor(*, name: str | None, bases: list[str]) -> None:
        process_enqueue(
            process_queue_redis,
            {
                "stage": "init",
                "name": name,
                "bases": bases,
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
