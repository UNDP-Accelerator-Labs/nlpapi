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
from typing import Any, Generic, TypeAlias, TypedDict, TypeVar

from redipy import Redis

from app.misc.util import get_time_str, json_compact_str, json_read_str


PL = TypeVar('PL')


ProcessHandlerId: TypeAlias = str


class ProcessEntry(TypedDict, Generic[PL]):
    payload: PL
    process: ProcessHandlerId


ProcessEntryJSON = TypedDict('ProcessEntryJSON', {
    "payload": dict[str, str],
    "process": ProcessHandlerId,
})


class ProcessError(ProcessEntryJSON):  # pylint: disable=inherit-non-class
    error: str


ProcessQueueStats = TypedDict('ProcessQueueStats', {
    "queue": int,
    "error": int,
})


class ProcessHandler(TypedDict, Generic[PL]):
    compute: Callable[[PL], Any]
    convert_to_json: Callable[[PL], dict[str, str]]
    convert_from_json: Callable[[dict[str, str]], PL]


PROCESS_LOCK = threading.RLock()
PROCESS_COND = threading.Condition(PROCESS_LOCK)
PROCESS_THREAD: threading.Thread | None = None
PROCESS_QUEUE_KEY = "process"
PROCESS_ERROR_KEY = "errors"


PROCESS_HND_LOOKUP: dict[ProcessHandlerId, ProcessHandler] = {}


def process_queue_info(process_queue_redis: Redis) -> ProcessQueueStats:
    process_queue_key = PROCESS_QUEUE_KEY
    process_error_key = PROCESS_ERROR_KEY

    with process_queue_redis.pipeline() as pipe:
        pipe.llen(process_queue_key)
        pipe.llen(process_error_key)
        queue_len, error_len = pipe.execute()
    return {
        "queue": queue_len,
        "error": error_len,
    }


NS_HND = uuid.UUID("9e7a13e0b1bd4366be1ac97c5f99943f")


def register_process_queue(
        name: str,
        convert_to_json: Callable[[PL], dict[str, str]],
        convert_from_json: Callable[[dict[str, str]], PL],
        compute: Callable[[PL], Any]) -> ProcessHandlerId:
    hnd_name = f"{name}-{uuid.uuid5(NS_HND, name).hex}"
    PROCESS_HND_LOOKUP[hnd_name] = {
        "compute": compute,
        "convert_to_json": convert_to_json,
        "convert_from_json": convert_from_json,
    }
    return hnd_name


def process_entry_to_json(
        process_hnd: ProcessHandler[PL],
        entry: ProcessEntry[PL]) -> ProcessEntryJSON:
    convert_to_json = process_hnd["convert_to_json"]
    return {
        "payload": convert_to_json(entry["payload"]),
        "process": entry["process"],
    }


def process_entry_from_json(
        process_hnd: ProcessHandler[PL],
        entry: ProcessEntryJSON) -> ProcessEntry[PL]:
    convert_from_json = process_hnd["convert_from_json"]
    return {
        "payload": convert_from_json(entry["payload"]),
        "process": entry["process"],
    }


def process_entry_to_redis(entry: ProcessEntryJSON) -> str:
    return json_compact_str(entry)


def process_error_to_redis(error: ProcessError) -> str:
    return json_compact_str(error)


def get_process_error(obj_str: str) -> ProcessError:
    return json_read_str(obj_str)


def get_process_entry_json(obj_str: str) -> ProcessEntryJSON:
    return json_read_str(obj_str)


def get_process_queue_errors(process_queue_redis: Redis) -> list[ProcessError]:
    process_error_key = PROCESS_ERROR_KEY

    return [
        get_process_error(obj_str)
        for obj_str in process_queue_redis.lrange(process_error_key, 0, -1)
    ]


def process_enqueue(
        process_queue_redis: Redis,
        hnd_name: ProcessHandlerId,
        payload: dict) -> None:
    process_queue_key = PROCESS_QUEUE_KEY
    process_hnd = PROCESS_HND_LOOKUP[hnd_name]

    entry = process_entry_to_json(process_hnd, {
        "payload": payload,
        "process": hnd_name,
    })
    process_queue_redis.rpush(
        process_queue_key,
        process_entry_to_redis(entry))
    maybe_adder_thread(process_queue_redis)


def requeue_errors(process_queue_redis: Redis) -> bool:
    process_queue_key = PROCESS_QUEUE_KEY
    process_error_key = PROCESS_ERROR_KEY

    any_enqueued = False
    while True:
        obj_str = process_queue_redis.lpop(process_error_key)
        if obj_str is None:
            break
        error = get_process_error(obj_str)
        process_queue_redis.rpush(
            process_queue_key,
            process_entry_to_redis({
                "payload": error["payload"],
                "process": error["process"],
            }))
        any_enqueued = True
    if any_enqueued:
        maybe_adder_thread(process_queue_redis)
    return any_enqueued


def log_diver(msg: str) -> None:
    print(f"{get_time_str()} QUEUE: {msg}")


def maybe_adder_thread(process_queue_redis: Redis) -> None:
    global PROCESS_THREAD  # pylint: disable=global-statement

    process_queue_key = PROCESS_QUEUE_KEY
    process_error_key = PROCESS_ERROR_KEY
    process_hnd_lookup = PROCESS_HND_LOOKUP

    def get_item() -> ProcessEntryJSON | None:
        res = process_queue_redis.lpop(process_queue_key)
        if res is None:
            return None
        return get_process_entry_json(res)

    def process(
            process_hnd: ProcessHandler[PL], entry: ProcessEntryJSON) -> None:
        log_diver(f"processing {entry['process']}: {entry['payload']}")
        entry_full = process_entry_from_json(process_hnd, entry)
        compute = process_hnd["compute"]
        info = compute(entry_full["payload"])
        log_diver(f"done {entry['payload']}: {info}")

    def run() -> None:
        global PROCESS_THREAD  # pylint: disable=global-statement

        try:
            while th is PROCESS_THREAD:
                with PROCESS_LOCK:
                    entry = PROCESS_COND.wait_for(get_item, 600.0)
                if entry is None:
                    continue
                try:
                    process(process_hnd_lookup[entry["process"]], entry)
                except BaseException:  # pylint: disable=broad-except
                    error_str = traceback.format_exc()
                    error: ProcessError = {
                        "payload": entry["payload"],
                        "process": entry["process"],
                        "error": error_str,
                    }
                    process_queue_redis.rpush(
                        process_error_key,
                        process_error_to_redis(error))
                    log_diver(f"error {entry['payload']}")
        finally:
            with PROCESS_LOCK:
                if th is PROCESS_THREAD:
                    PROCESS_THREAD = None

    with PROCESS_LOCK:
        if PROCESS_THREAD is not None and PROCESS_THREAD.is_alive():
            PROCESS_COND.notify_all()
            return
        th = threading.Thread(target=run, daemon=True)
        PROCESS_THREAD = th
        th.start()
