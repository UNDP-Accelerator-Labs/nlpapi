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
import traceback

from scattermind.api.api import ScattermindAPI
from scattermind.system.response import TASK_COMPLETE
from scattermind.system.torch_util import tensor_to_str

from app.misc.util import get_json_error_str, get_time_str, to_bool
from app.system.db.db import DBConnector
from app.system.deepdive.collection import (
    DeepDiveResult,
    DocumentObj,
    get_documents_in_queue,
    set_deep_dive,
    set_error,
    set_tag,
    set_url_title,
    set_verify,
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
        return list(get_documents_in_queue(db))

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


MAX_LENGTH = 10000  # FIXME: use chunking


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
    log_diver(f"found {len(docs)} for processing!")
    ns = graph_llama.get_ns()
    for doc in docs:
        doc_id = doc["id"]
        main_id = doc["main_id"]
        if doc["url"] is None or doc["title"] is None:
            log_diver(f"processing {main_id}: url and title")
            url_title, error = get_url_title(doc["main_id"])
            url = "#"
            title = "ERROR: unknown"
            if error is not None:
                title = f"ERROR: {error}"
            if url_title is not None:
                url, title = url_title
            set_url_title(db, doc_id, url, title)
        if doc["tag_reason"] is None:
            log_diver(f"processing {main_id}: tag")
            tag, tag_reason = get_tag(doc["main_id"])
            set_tag(db, doc_id, tag, tag_reason)
        if doc["is_valid"] is not None and doc["deep_dive_result"] is not None:
            continue
        log_diver(f"processing {main_id}: getting full text")
        full_text, error_msg = get_full_text(main_id)
        full_text = normalize_text(full_text)
        warning = None
        if full_text is None:
            set_error(
                db,
                doc_id,
                "could not retrieve document "
                f"for {doc['main_id']}: {error_msg}")
            continue
        old_len = len(full_text)
        if old_len > MAX_LENGTH:
            full_text = full_text[:MAX_LENGTH]
            warning = (
                f"text too long ({old_len}); truncated to ({len(full_text)})")
        is_verify = doc["is_valid"] is None
        if is_verify:
            sp_key = doc["verify_key"]
        elif doc["is_valid"] is True:
            sp_key = doc["deep_dive_key"]
        else:
            log_diver(f"processing {main_id}: skip invalid")
            set_deep_dive(db, doc_id, {
                "reason": (
                    "Document is not about circular economy! "
                    "No interpretation performed!"),
                "cultural": 0,
                "economic": 0,
                "educational": 0,
                "institutional": 0,
                "legal": 0,
                "political": 0,
                "technological": 0,
            })
            sp_key = None
        if sp_key is None:
            continue
        log_diver(f"processing {main_id}: llm ({sp_key})")
        task_id = smind.enqueue_task(
            ns,
            {
                "prompt": full_text,
                "system_prompt_key": sp_key,
            })
        for _, result in smind.wait_for([task_id], timeout=600):
            if result["status"] not in TASK_COMPLETE:
                continue
            res = result["result"]
            if warning is None:
                warning = ""
            else:
                warning = f"\nWARNING: {warning}"
            if res is None:
                set_error(db, doc_id, f"error in task: {result}{warning}")
                continue
            text = tensor_to_str(res["response"])
            error_msg = (
                f"ERROR: could not interpret model output:\n{text}{warning}")
            if is_verify:
                vres, verror = interpret_verify(text, warning)
                if vres is None:
                    if verror is not None:
                        verror = f"\nSTACKTRACE: {verror}"
                    set_error(db, doc_id, f"{error_msg}{verror}")
                else:
                    set_verify(db, doc_id, vres["is_hit"], vres["reason"])
            else:
                ddres, derror = interpret_deep_dive(text, warning)
                if ddres is None:
                    if derror is not None:
                        derror = f"\nSTACKTRACE: {derror}"
                    set_error(db, doc_id, f"{error_msg}{derror}")
                else:
                    set_deep_dive(db, doc_id, ddres)
    log_diver("done processing")


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


def interpret_verify(
        text: str, warning: str) -> tuple[VerifyResult | None, str | None]:
    obj, error = parse_json(text)
    if obj is None:
        return (None, error)
    try:
        return (
            {
                "reason": f"{obj['reason']}{warning}",
                "is_hit": to_bool(obj["is_hit"]),
            },
            None,
        )
    except KeyError:
        return (None, traceback.format_exc())


def interpret_deep_dive(
        text: str, warning: str) -> tuple[DeepDiveResult | None, str | None]:
    obj, error = parse_json(text)
    if obj is None:
        return (None, error)
    try:
        return (
            {
                "reason": f"{obj['reason']}{warning}",
                "cultural": int(obj["cultural"]),
                "economic": int(obj["economic"]),
                "educational": int(obj["educational"]),
                "institutional": int(obj["institutional"]),
                "legal": int(obj["legal"]),
                "political": int(obj["political"]),
                "technological": int(obj["technological"]),
            },
            None,
        )
    except KeyError:
        return (None, traceback.format_exc())
