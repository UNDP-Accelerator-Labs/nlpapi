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
import threading
import traceback
import uuid
from collections.abc import Callable
from typing import TypedDict

from redipy import Redis

from app.misc.util import json_compact_str, json_read_str
from app.system.smind.vec import AddEmbed


ProcessError = TypedDict('ProcessError', {
    "db": str,
    "main_id": str,
    "user": str,
    "error": str,
})
ProcessEntry = TypedDict('ProcessEntry', {
    "db": str,
    "main_id": str,
    "user": uuid.UUID,
})
ProcessEntryJSON = TypedDict('ProcessEntryJSON', {
    "main_id": str,
    "db": str,
    "user": str,
})
EmbedQueueStats = TypedDict('EmbedQueueStats', {
    "queue": int,
    "error": int,
})
AddEmbedFn = Callable[[ProcessEntry], AddEmbed]


ADDER_LOCK = threading.RLock()
ADDER_COND = threading.Condition(ADDER_LOCK)
ADDER_THREAD: threading.Thread | None = None
ADDER_QUEUE_KEY = "main_ids"
ADDER_ERROR_KEY = "errors"


def adder_info(add_queue_redis: Redis) -> EmbedQueueStats:
    adder_queue_key = ADDER_QUEUE_KEY
    adder_error_key = ADDER_ERROR_KEY

    with add_queue_redis.pipeline() as pipe:
        pipe.llen(adder_queue_key)
        pipe.llen(adder_error_key)
        queue_len, error_len = pipe.execute()
    return {
        "queue": queue_len,
        "error": error_len,
    }


def get_process_error(obj_str: str) -> ProcessError:
    return json_read_str(obj_str)


def get_process_entry(obj_str: str) -> ProcessEntry:
    obj: ProcessEntryJSON = json_read_str(obj_str)
    return {
        "db": obj["db"],
        "main_id": obj["main_id"],
        "user": uuid.UUID(obj["user"]),
    }


def process_entry_to_json(entry: ProcessEntry) -> str:
    obj: ProcessEntryJSON = {
        "db": entry["db"],
        "main_id": entry["main_id"],
        "user": entry["user"].hex,
    }
    return process_entry_json_to_str(obj)


def process_entry_json_to_str(obj: ProcessEntryJSON) -> str:
    return json_compact_str(obj)


def get_embed_errors(add_queue_redis: Redis) -> list[ProcessError]:
    adder_error_key = ADDER_ERROR_KEY

    return [
        get_process_error(obj_str)
        for obj_str in add_queue_redis.lrange(adder_error_key, 0, -1)
    ]


def adder_enqueue(
        add_queue_redis: Redis,
        add_embed_fn: AddEmbedFn,
        entry: ProcessEntry) -> None:
    adder_queue_key = ADDER_QUEUE_KEY

    add_queue_redis.rpush(adder_queue_key, process_entry_to_json(entry))
    maybe_adder_thread(add_queue_redis, add_embed_fn)


def requeue_errors(
        add_queue_redis: Redis,
        add_embed_fn: AddEmbedFn) -> bool:
    adder_queue_key = ADDER_QUEUE_KEY
    adder_error_key = ADDER_ERROR_KEY

    any_enqueued = False
    while True:
        obj_str = add_queue_redis.lpop(adder_error_key)
        if obj_str is None:
            break
        error = get_process_error(obj_str)
        add_queue_redis.rpush(
            adder_queue_key,
            process_entry_json_to_str({
                "db": error["db"],
                "main_id": error["main_id"],
                "user": error["user"],
            }))
        any_enqueued = True
    if any_enqueued:
        maybe_adder_thread(add_queue_redis, add_embed_fn)
    return any_enqueued


def maybe_adder_thread(
        add_queue_redis: Redis,
        add_embed_fn: AddEmbedFn) -> None:
    global ADDER_THREAD  # pylint: disable=global-statement

    adder_queue_key = ADDER_QUEUE_KEY
    adder_error_key = ADDER_ERROR_KEY

    def get_item() -> ProcessEntry | None:
        res = add_queue_redis.lpop(adder_queue_key)
        if res is None:
            return None
        return get_process_entry(res)

    def run() -> None:
        global ADDER_THREAD  # pylint: disable=global-statement

        try:
            while th is ADDER_THREAD:
                with ADDER_LOCK:
                    entry = ADDER_COND.wait_for(get_item, 600.0)
                if entry is None:
                    continue
                print(f"ADDER: processing {entry['main_id']} to {entry['db']}")
                try:
                    info = add_embed_fn(entry)
                    print(f"ADDER: done {entry['main_id']}: {info}")
                except BaseException:  # pylint: disable=broad-except
                    error_str = traceback.format_exc()
                    error: ProcessError = {
                        "db": entry["db"],
                        "main_id": entry["main_id"],
                        "user": entry["user"].hex,
                        "error": error_str,
                    }
                    add_queue_redis.rpush(
                        adder_error_key,
                        json_compact_str(error))
                    print(f"ADDER: error {entry['main_id']}")
        finally:
            with ADDER_LOCK:
                if th is ADDER_THREAD:
                    ADDER_THREAD = None

    with ADDER_LOCK:
        if ADDER_THREAD is not None and ADDER_THREAD.is_alive():
            ADDER_COND.notify_all()
            return
        th = threading.Thread(target=run, daemon=True)
        ADDER_THREAD = th
        th.start()
