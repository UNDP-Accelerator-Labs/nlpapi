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
import threading
from collections.abc import Callable

from scattermind.api.api import ScattermindAPI
from scattermind.system.base import TaskId
from scattermind.system.response import TASK_COMPLETE
from scattermind.system.torch_util import tensor_to_str

from app.misc.util import to_bool
from app.system.db.db import DBConnector
from app.system.deepdive.collection import (
    DeepDiveResult,
    get_documents_in_queue,
    set_deep_dive,
    set_error,
    set_verify,
    VerifyResult,
)
from app.system.prep.clean import normalize_text
from app.system.smind.api import GraphProfile


DIVER_LOCK = threading.RLock()
DIVER_THREAD: threading.Thread | None = None


def maybe_diver_thread(
        db: DBConnector,
        smind: ScattermindAPI,
        graph_llama: GraphProfile,
        get_full_text: Callable[[str], tuple[str | None, str | None]]) -> None:
    global DIVER_THREAD  # pylint: disable=global-statement

    if DIVER_THREAD is not None and DIVER_THREAD.is_alive():
        return

    def run() -> None:
        global DIVER_THREAD  # pylint: disable=global-statement

        try:
            while th is DIVER_THREAD:
                if not process_pending(db, smind, graph_llama, get_full_text):
                    break
        finally:
            with DIVER_LOCK:
                if th is DIVER_THREAD:
                    DIVER_THREAD = None

    with DIVER_LOCK:
        if DIVER_THREAD is not None and DIVER_THREAD.is_alive():
            return
        th = threading.Thread(target=run, daemon=True)
        DIVER_THREAD = th
        th.start()


MAX_LENGTH = 20000  # FIXME: use 10000 for chunking


def process_pending(
        db: DBConnector,
        smind: ScattermindAPI,
        graph_llama: GraphProfile,
        get_full_text: Callable[[str], tuple[str | None, str | None]]) -> bool:
    docs = list(get_documents_in_queue(db))
    if not docs:
        return False
    tasks: dict[TaskId, tuple[int, bool, str | None]] = {}
    ns = graph_llama.get_ns()
    for doc in docs:
        doc_id = doc["id"]
        full_text, error_msg = get_full_text(doc["main_id"])
        full_text = normalize_text(full_text)
        warning = None
        if full_text is None:
            set_error(
                db,
                doc_id,
                "could not retrieve document "
                f"for {doc['main_id']}: {error_msg}")
            continue
        if len(full_text) > MAX_LENGTH:
            warning = f"text too long ({len(full_text)}); truncated"
            full_text = full_text[:MAX_LENGTH]
        is_verify = doc["is_valid"] is None
        if is_verify:
            sp_key = doc["verify_key"]
        else:
            sp_key = doc["deep_dive_key"]
        task_id = smind.enqueue_task(
            ns,
            {
                "prompt": full_text,
                "system_prompt_key": sp_key,
            })
        tasks[task_id] = (doc_id, is_verify, warning)
    while tasks:
        for task_id, result in smind.wait_for(list(tasks.keys()), timeout=600):
            if result["status"] not in TASK_COMPLETE:
                continue
            res = result["result"]
            doc_id, is_verify, warning = tasks.pop(task_id)
            if warning is None:
                warning = ""
            else:
                warning = f"\nWARNING: {warning}"
            if res is None:
                set_error(db, doc_id, f"error in task: {result}{warning}")
                continue
            text = tensor_to_str(res["response"])
            if is_verify:
                vres = interpret_verify(text, warning)
                if vres is None:
                    set_error(
                        db, doc_id, f"could not interpret: {text}{warning}")
                else:
                    set_verify(db, doc_id, vres["is_hit"], vres["reason"])
            else:
                ddres = interpret_deep_dive(text, warning)
                if ddres is None:
                    set_error(
                        db, doc_id, f"could not interpret: {text}{warning}")
                else:
                    set_deep_dive(db, doc_id, ddres)
    return True


def parse_json(text: str) -> dict | None:
    start = text.find(r"{")
    end = text.rfind(r"}")
    if start < 0 or end < 0:
        return None
    text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.decoder.JSONDecodeError:
        text_single = text.replace("\"\"", "\"")
        try:
            return json.loads(text_single)
        except json.decoder.JSONDecodeError:
            return None


def interpret_verify(text: str, warning: str) -> VerifyResult | None:
    obj = parse_json(text)
    if obj is None:
        return None
    try:
        return {
            "reason": f"{obj['reason']}{warning}",
            "is_hit": to_bool(obj["is_hit"]),
        }
    except KeyError:
        return None


def interpret_deep_dive(text: str, warning: str) -> DeepDiveResult | None:
    obj = parse_json(text)
    if obj is None:
        return None
    try:
        return {
            "reason": f"{obj['reason']}{warning}",
            "cultural": int(obj["cultural"]),
            "economic": int(obj["economic"]),
            "educational": int(obj["educational"]),
            "institutional": int(obj["institutional"]),
            "legal": int(obj["legal"]),
            "political": int(obj["political"]),
            "technological": int(obj["technological"]),
        }
    except KeyError:
        return None
