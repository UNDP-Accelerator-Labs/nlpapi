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
import json
import re
import threading
import time
import traceback
from typing import Literal

from scattermind.api.api import ScattermindAPI
from scattermind.system.names import GNamespace
from scattermind.system.response import TASK_COMPLETE
from scattermind.system.torch_util import tensor_to_str

from app.misc.util import get_json_error_str, get_time_str, retry_err, to_bool
from app.system.db.db import DBConnector
from app.system.deepdive.collection import (
    add_segments,
    combine_segments,
    convert_deep_dive_result,
    DeepDivePromptInfo,
    DeepDiveResult,
    DocumentObj,
    get_deep_dive_prompt_info,
    get_documents_in_queue,
    get_segments_in_queue,
    set_deep_dive_segment,
    set_error,
    set_error_segment,
    set_tag,
    set_url_title,
    set_verify_segment,
    VerifyResult,
)
from app.system.prep.clean import normalize_text
from app.system.prep.fulltext import FullTextFn, TagFn, UrlTitleFn
from app.system.smind.api import GraphProfile


DIVER_LOCK = threading.RLock()
DIVER_COND = threading.Condition(DIVER_LOCK)
DIVER_THREAD: threading.Thread | None = None


def log_diver(msg: str) -> None:
    print(f"{get_time_str()} DIVER: {msg}")


def maybe_diver_thread(
        db: DBConnector,
        smind: ScattermindAPI,
        graph_llama: GraphProfile,
        get_full_text: FullTextFn,
        get_url_title: UrlTitleFn,
        get_tag: TagFn) -> None:
    global DIVER_THREAD  # pylint: disable=global-statement

    def get_docs() -> list[DocumentObj]:
        return list(retry_err(get_documents_in_queue, db))

    def run() -> None:
        global DIVER_THREAD  # pylint: disable=global-statement

        try:
            while th is DIVER_THREAD:
                with DIVER_LOCK:
                    docs = DIVER_COND.wait_for(get_docs, 600.0)
                process_pending(
                    db,
                    docs,
                    smind,
                    graph_llama,
                    get_full_text,
                    get_url_title,
                    get_tag)

        finally:
            with DIVER_LOCK:
                if th is DIVER_THREAD:
                    DIVER_THREAD = None

    with DIVER_LOCK:
        if DIVER_THREAD is not None and DIVER_THREAD.is_alive():
            DIVER_COND.notify_all()
            return
        th = threading.Thread(target=run, daemon=True)
        DIVER_THREAD = th
        th.start()


def process_pending(
        db: DBConnector,
        docs: list[DocumentObj],
        smind: ScattermindAPI,
        graph_llama: GraphProfile,
        get_full_text: FullTextFn,
        get_url_title: UrlTitleFn,
        get_tag: TagFn) -> None:
    if not docs:
        return
    for _ in range(3):
        count = process_segments(db, smind, graph_llama)
        if count <= 0:
            break
        log_diver(f"processed {count} segments")
    log_diver(f"found {len(docs)} for processing!")
    for doc in docs:
        doc_id = doc["id"]
        main_id = doc["main_id"]
        if doc["url"] is None or doc["title"] is None:
            log_diver(f"processing {main_id}: url and title")
            url_title, error = get_url_title(main_id, is_logged_in=True)
            url = "#"
            title = "ERROR: unknown"
            if error is not None:
                title = f"ERROR: {error}"
            if url_title is not None:
                url, title = url_title
            retry_err(set_url_title, db, doc_id, url, title)
        if doc["tag_reason"] is None:
            log_diver(f"processing {main_id}: tag")
            tag, tag_reason = get_tag(main_id)
            retry_err(set_tag, db, doc_id, tag, tag_reason)
        if doc["is_valid"] is not None and doc["deep_dive_result"] is not None:
            continue
        if doc["error"] is not None:
            continue
        categories = doc["segmentation"]["categories"]
        combined = retry_err(combine_segments, db, doc, categories)
        if combined == "empty":
            log_diver(f"processing {main_id}: getting full text")
            full_text, error_msg = get_full_text(main_id)
            full_text = normalize_text(full_text)
            if full_text is None:
                log_diver(f"processing {main_id}: error retrieving full text")
                retry_err(
                    set_error,
                    db,
                    doc_id,
                    f"could not retrieve document for {main_id}: {error_msg}")
                continue
            pages = retry_err(add_segments, db, doc, full_text)
            log_diver(f"processing {main_id}: adding {pages} segments")
            continue
        if combined == "incomplete":
            continue
        log_diver(f"processing {main_id}: done")
    log_diver("done processing")


LLM_TIMEOUT = 300


def process_segments(
        db: DBConnector,
        smind: ScattermindAPI,
        graph_llama: GraphProfile,
        ) -> int:
    segments = list(retry_err(get_segments_in_queue, db))
    ns = graph_llama.get_ns()
    for queue_counts in smind.get_queue_stats(ns):
        queue_length = queue_counts["queue_length"]
        sleep_time = LLM_TIMEOUT // 2 * queue_length
        if queue_length > 0 and sleep_time > 0:
            log_diver(
                "current queue: "
                f"{queue_counts['name']}={queue_length} sleep={sleep_time}s")
            time.sleep(sleep_time)
    prompt_ids = {
        prompt_id
        for segment in segments
        for prompt_id in [segment["verify_id"], segment["categories_id"]]
    }
    with db.get_session() as session:
        prompt_infos = get_deep_dive_prompt_info(session, prompt_ids)
    for segment in segments:
        seg_id = segment["id"]
        main_id = segment["main_id"]
        page = segment["page"]
        full_text = segment["content"]
        is_verify = segment["is_valid"] is None
        prompt_id = (
            segment["verify_id"] if is_verify else segment["categories_id"])
        prompt_info = prompt_infos[prompt_id]
        category_prompt_info = prompt_infos[segment["categories_id"]]
        categories = category_prompt_info["categories"]
        assert categories is not None
        if not is_verify and segment["is_valid"] is False:
            log_diver(f"processing segment {main_id}@{page}: skip invalid")
            retry_err(
                set_deep_dive_segment,
                db,
                seg_id,
                {
                    "reason": (
                        "Segment did not pass filter! "
                        "No interpretation performed!"),
                    "values": {
                        cat: 0
                        for cat in categories
                    },
                })
            continue
        log_diver(
            f"processing segment {main_id}@{page} ({seg_id}): "
            f"llm ({prompt_info['name']}) size={len(full_text)}")
        llm_out, llm_error = llm_response(smind, ns, full_text, prompt_info)
        if llm_out is not None:
            error_msg = (
                f"ERROR: could not interpret model output:\n{llm_out}")
            # prompt_info["categories"] is None  is_verify
            if is_verify:
                vres, verror = interpret_verify(llm_out)
                if vres is None:
                    verror = (
                        ""
                        if verror is None
                        else f"\nSTACKTRACE: {verror}")
                    retry_err(
                        set_error_segment,
                        db,
                        seg_id,
                        f"{error_msg}{verror}")
                else:
                    retry_err(
                        set_verify_segment,
                        db,
                        seg_id,
                        vres["is_hit"],
                        vres["reason"])
            else:
                ddres, derror = interpret_deep_dive(llm_out, categories)
                if ddres is None:
                    derror = (
                        ""
                        if derror is None
                        else f"\nSTACKTRACE: {derror}")
                    retry_err(
                        set_error_segment,
                        db,
                        seg_id,
                        f"{error_msg}{derror}")
                else:
                    retry_err(set_deep_dive_segment, db, seg_id, ddres)
        elif llm_error == "timeout":
            log_diver(
                f"processing segment {main_id}@{page}: "
                f"llm timed out ({prompt_info['name']})")
            retry_err(
                set_error_segment,
                db,
                seg_id,
                f"llm timed out for {main_id}@{page}")
        elif llm_error == "missing":
            log_diver(
                f"processing segment {main_id}@{page}: "
                f"llm error ({prompt_info['name']})")
            retry_err(
                set_error_segment,
                db,
                seg_id,
                f"error in task: {llm_out}")
        else:
            raise ValueError(f"unexpected error: {llm_out=} {llm_error=}")
    return len(segments)


def llm_response(
        smind: ScattermindAPI,
        ns: GNamespace,
        full_text: str,
        prompt_info: DeepDivePromptInfo,
        ) -> tuple[str | None, Literal["timeout", "missing", "okay"]]:
    post_prompt = prompt_info["post_prompt"]
    if post_prompt is None:
        post_prompt = " "
    task_id = smind.enqueue_task(
        ns,
        {
            "prompt": full_text,
            "main_prompt": prompt_info["main_prompt"],
            "post_prompt": post_prompt,
        })
    for _, result in smind.wait_for(
            [task_id], timeout=LLM_TIMEOUT, auto_clear=True):
        if result["status"] not in TASK_COMPLETE:
            return (None, "timeout")
        res = result["result"]
        if res is None:
            return (None, "missing")
        return (tensor_to_str(res["response"]), "okay")
    return (None, "missing")


LP = r"{"
RP = r"}"


def parse_json(text: str) -> tuple[dict | None, str | None]:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r",\s+}", RP, text)  # NOTE: remove trailing commas
    start = text.find(LP)
    if start < 0:
        return (None, f"no '{LP}' in output")
    end = text.rfind(RP)
    if end < 0:
        text = f"{text}{RP}"
        end = len(text)
    else:
        end += 1
    text = text[start:end]
    try:
        return (json.loads(text), None)
    except json.decoder.JSONDecodeError as ferr:
        first_error = (
            f"{get_json_error_str(ferr)}\n"
            f"Stacktrace:\n{traceback.format_exc()}")
        text_single = text.replace("\"\"", "\"")
        if text_single == text:
            return (None, first_error)
        try:
            return (json.loads(text_single), None)
        except json.decoder.JSONDecodeError as serr:
            second_error = (
                f"{get_json_error_str(serr)}\n"
                f"Stacktrace:\n{traceback.format_exc()}")
            return (
                None,
                f"First try:\n{first_error}\nSecond try:\n{second_error}",
            )


def interpret_verify(text: str) -> tuple[VerifyResult | None, str | None]:
    obj, error = parse_json(text)
    if obj is None:
        return (None, error)
    try:
        return (
            {
                "reason": f"{obj['reason']}",
                "is_hit": to_bool(obj["is_hit"]),
            },
            None,
        )
    except KeyError:
        return (None, traceback.format_exc())


def interpret_deep_dive(
        text: str,
        categories: list[str]) -> tuple[DeepDiveResult | None, str | None]:
    obj, error = parse_json(text)
    if obj is None:
        return (None, error)
    try:
        return (convert_deep_dive_result(obj, categories=categories), None)
    except (KeyError, ValueError):
        return (None, traceback.format_exc())
