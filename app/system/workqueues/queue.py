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
"""Processing queues for tasks. Queues are stored in redis."""
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from typing import Any, Generic, Protocol, TypeAlias, TypedDict, TypeVar

from redipy import Redis, RSM_MISSING

from app.misc.util import get_time_str, json_compact_str, json_read_str


PL = TypeVar('PL')
PL_contra = TypeVar('PL_contra', contravariant=True)


class ProcessEnqueue(  # pylint: disable=too-few-public-methods
        Protocol[PL_contra]):
    """Functioin enqueue a task."""
    def __call__(self, process_queue_redis: Redis, payload: PL_contra) -> None:
        """
        Enqueues a task to the processing queue.

        Args:
            process_queue_redis (Redis): The processing queue redis.
            payload (PL_contra): The task payload.
        """


ProcessHandlerId: TypeAlias = str
"""Id for a processing queue handler."""


class ProcessEntry(TypedDict, Generic[PL]):
    """Entry in the processing queue."""
    payload: PL
    """The task payload."""
    process: ProcessHandlerId
    """The handler identifier."""


ProcessEntryJSON = TypedDict('ProcessEntryJSON', {
    "payload": dict[str, str],
    "process": ProcessHandlerId,
})
"""Entry in the processing queue as JSON."""


class ProcessError(ProcessEntryJSON):  # pylint: disable=inherit-non-class
    """Error in the processing queue."""
    error: str
    """The error."""


ProcessQueueStats = TypedDict('ProcessQueueStats', {
    "queue": int,
    "active": list[ProcessEntryJSON],
    "error": int,
})
"""Information about the current status of the processing queue."""


class ProcessHandler(TypedDict, Generic[PL]):
    """Handles tasks in the processing queue."""
    compute: Callable[[PL], Any]
    """Compute the task result."""
    convert_to_json: Callable[[PL], dict[str, str]]
    """Convert the payload to JSON."""
    convert_from_json: Callable[[dict[str, str]], PL]
    """Convert the payload back from JSON."""


PROCESS_LOCK = threading.RLock()
"""The processing queue lock."""
PROCESS_COND = threading.Condition(PROCESS_LOCK)
"""The processing queue notification condition."""
PROCESS_THREAD: threading.Thread | None = None
"""The processing queue processing thread."""
PROCESS_QUEUE_KEY = "process"
"""Redis key for the processing queue tasks."""
PROCESS_ACTIVE_KEY = "active"
"""Redis key for the active tasks in the processing queue."""
PROCESS_ERROR_KEY = "errors"
"""Redis key for errors in the processing queue."""
PROCESS_LOCK_KEY = "lock"
"""Redis key lock for ensuring only one thread is processing the queue."""
HB_TIMEOUT = 60.0  # 1min
"""Heartbeat timeout in seconds."""


PROCESS_HND_LOOKUP: dict[ProcessHandlerId, ProcessHandler] = {}
"""Process handler lookup."""


def process_queue_info(process_queue_redis: Redis) -> ProcessQueueStats:
    """
    Get information about the queue status.

    Args:
        process_queue_redis (Redis): The processing queue redis.

    Returns:
        ProcessQueueStats: The statistics.
    """
    process_queue_key = PROCESS_QUEUE_KEY
    process_active_key = PROCESS_ACTIVE_KEY
    process_error_key = PROCESS_ERROR_KEY

    with process_queue_redis.pipeline() as pipe:
        pipe.llen(process_queue_key)
        pipe.lrange(process_active_key, 0, -1)
        pipe.llen(process_error_key)
        queue_len, actives, error_len = pipe.execute()
    return {
        "queue": queue_len,
        "active": [get_process_entry_json(active) for active in actives],
        "error": error_len,
    }


NS_HND = uuid.UUID("9e7a13e0b1bd4366be1ac97c5f99943f")
"""The UUID namespace for processing handlers."""


def register_process_queue(
        name: str,
        convert_to_json: Callable[[PL], dict[str, str]],
        convert_from_json: Callable[[dict[str, str]], PL],
        compute: Callable[[PL], Any]) -> ProcessEnqueue[PL]:
    """
    Register a processing queue.

    Args:
        name (str): The readable name of the queue.
        convert_to_json (Callable[[PL], dict[str, str]]): Converting a payload
            to JSON.
        convert_from_json (Callable[[dict[str, str]], PL]): Converting a JSON
            to payload.
        compute (Callable[[PL], Any]): Processing a task.

    Returns:
        ProcessEnqueue[PL]: Function to enqueue elements to the queue.
    """
    hnd_name = f"{name}-{uuid.uuid5(NS_HND, name).hex}"
    if hnd_name in PROCESS_HND_LOOKUP:
        raise ValueError(f"cannot register {name} twice!")
    PROCESS_HND_LOOKUP[hnd_name] = {
        "compute": compute,
        "convert_to_json": convert_to_json,
        "convert_from_json": convert_from_json,
    }

    def process_enqueue(
            process_queue_redis: Redis,
            payload: PL) -> None:
        process_queue_key = PROCESS_QUEUE_KEY
        process_hnd = PROCESS_HND_LOOKUP[hnd_name]

        entry = process_entry_to_json(process_hnd, {
            "payload": payload,
            "process": hnd_name,
        })
        process_queue_redis.rpush(
            process_queue_key,
            process_entry_to_redis(entry))
        maybe_process_thread(process_queue_redis)

    return process_enqueue


def process_entry_to_json(
        process_hnd: ProcessHandler[PL],
        entry: ProcessEntry[PL]) -> ProcessEntryJSON:
    """
    Convert a queue entry to JSON.

    Args:
        process_hnd (ProcessHandler[PL]): The processing handler.
        entry (ProcessEntry[PL]): The entry.

    Returns:
        ProcessEntryJSON: The entry as JSON.
    """
    convert_to_json = process_hnd["convert_to_json"]
    return {
        "payload": convert_to_json(entry["payload"]),
        "process": entry["process"],
    }


def process_entry_from_json(
        process_hnd: ProcessHandler[PL],
        entry: ProcessEntryJSON) -> ProcessEntry[PL]:
    """
    Convert a queue entry from JSON.

    Args:
        process_hnd (ProcessHandler[PL]): The processing handler.
        entry (ProcessEntryJSON): The entry as JSON.

    Returns:
        ProcessEntry[PL]: The entry.
    """
    convert_from_json = process_hnd["convert_from_json"]
    return {
        "payload": convert_from_json(entry["payload"]),
        "process": entry["process"],
    }


def process_entry_to_redis(entry: ProcessEntryJSON) -> str:
    """
    Convert a queue entry to redis.

    Args:
        entry (ProcessEntryJSON): The processing queue entry.

    Returns:
        str: The redis value string.
    """
    return json_compact_str(entry)


def process_error_to_redis(error: ProcessError) -> str:
    """
    Convert a queue error to redis.

    Args:
        error (ProcessError): The error.

    Returns:
        str: The redis value string.
    """
    return json_compact_str(error)


def get_process_error(obj_str: str) -> ProcessError:
    """
    Convert a queue error from redis.

    Args:
        obj_str (str): The redis value string.

    Returns:
        ProcessError: The error.
    """
    return json_read_str(obj_str)


def get_process_entry_json(obj_str: str) -> ProcessEntryJSON:
    """
    Convert a queue entry from redis.

    Args:
        obj_str (str): The redis value string.

    Returns:
        ProcessEntryJSON: The entry JSON.
    """
    return json_read_str(obj_str)


def get_process_queue_errors(process_queue_redis: Redis) -> list[ProcessError]:
    """
    Get processing queue errors.

    Args:
        process_queue_redis (Redis): The processing queue redis.

    Returns:
        list[ProcessError]: The errors.
    """
    process_error_key = PROCESS_ERROR_KEY

    return [
        get_process_error(obj_str)
        for obj_str in process_queue_redis.lrange(process_error_key, 0, -1)
    ]


def requeue_errors(process_queue_redis: Redis) -> bool:
    """
    Requeues errors by putting the tasks back to the processing queue.

    Args:
        process_queue_redis (Redis): The processing queue redis.

    Returns:
        bool: Whether any errors were requeued.
    """
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
        maybe_process_thread(process_queue_redis)
    return any_enqueued


def log_process(msg: str) -> None:
    """
    Log information about the processing queue.

    Args:
        msg (str): The message.
    """
    print(f"{get_time_str()} QUEUE: {msg}")


def maybe_process_thread(process_queue_redis: Redis) -> None:
    """
    Start the processing queue processing thread if needed.

    Args:
        process_queue_redis (Redis): The processing queue redis.
    """
    global PROCESS_THREAD  # pylint: disable=global-statement

    process_queue_key = PROCESS_QUEUE_KEY
    process_active_key = PROCESS_ACTIVE_KEY
    process_error_key = PROCESS_ERROR_KEY
    process_lock_key = PROCESS_LOCK_KEY
    process_hnd_lookup = PROCESS_HND_LOOKUP
    hb_timeout = HB_TIMEOUT

    def get_item() -> ProcessEntryJSON | None:
        while True:
            lock_value = process_queue_redis.get_value(process_lock_key)
            if lock_value != process_id:
                return None
            actives = process_queue_redis.lrange(process_active_key, 0, 0)
            if actives:
                return get_process_entry_json(actives[0])
            res = process_queue_redis.lpop(process_queue_key)
            if res is None:
                return None
            process_queue_redis.rpush(process_active_key, res)

    def complete_item() -> None:
        process_queue_redis.lpop(process_active_key)

    def process(
            process_hnd: ProcessHandler[PL], entry: ProcessEntryJSON) -> None:
        log_process(f"processing {entry['process']}: {entry['payload']}")
        entry_full = process_entry_from_json(process_hnd, entry)
        compute = process_hnd["compute"]
        info = compute(entry_full["payload"])
        log_process(f"done {entry['payload']}: {info}")

    def run() -> None:
        global PROCESS_THREAD  # pylint: disable=global-statement

        try:
            while th is PROCESS_THREAD:
                with PROCESS_LOCK:
                    entry = PROCESS_COND.wait_for(get_item, hb_timeout)
                if entry is None:
                    continue
                try:
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
                        log_process(f"error {entry['payload']}")
                finally:
                    complete_item()
        finally:
            with PROCESS_LOCK:
                if th is PROCESS_THREAD:
                    PROCESS_THREAD = None

    def heartbeat() -> None:
        while th is PROCESS_THREAD:
            process_queue_redis.set_value(
                process_lock_key,
                process_id,
                mode=RSM_MISSING,
                expire_in=hb_timeout * 2)
            time.sleep(hb_timeout)

    with PROCESS_LOCK:
        if PROCESS_THREAD is not None and PROCESS_THREAD.is_alive():
            PROCESS_COND.notify_all()
            return
        process_id = uuid.uuid4().hex
        hb = threading.Thread(target=heartbeat, daemon=True)
        th = threading.Thread(target=run, daemon=True)
        PROCESS_THREAD = th
        hb.start()
        th.start()
