import json
import os
import re
import time
import traceback
import unicodedata
from collections.abc import Iterable
from html import unescape
from typing import cast, Literal, TypedDict, TypeVar

import redis as redis_lib
from gemma import tokenizer
from redipy import Redis, RedisConfig
from scattermind.api.api import ScattermindAPI
from scattermind.api.loader import load_api
from scattermind.system.base import TaskId
from scattermind.system.config.loader import ConfigJSON
from scattermind.system.names import GNamespace
from scattermind.system.torch_util import tensor_to_str

from app.system.config import Config


T = TypeVar('T')


PseudoRedisName = Literal["rmain", "rdata", "rcache", "rbody", "rworker"]


QueueStat = TypedDict('QueueStat', {
    "id": str,
    "name": str,
    "queue_length": int,
    "listeners": int,
})


def get_redis(
        config_fname: str,
        *,
        redis_name: PseudoRedisName,
        overwrite_prefix: str | None) -> Redis:
    with open(config_fname, "rb") as fin:
        config_obj = cast(ConfigJSON, json.load(fin))
    if redis_name == "rmain":
        if config_obj["client_pool"]["name"] != "redis":
            raise ValueError(
                "client_pool is not redis: "
                f"{config_obj['client_pool']['name']}")
        cfg: RedisConfig = config_obj["client_pool"]["cfg"]
    elif redis_name == "rcache":
        if config_obj["graph_cache"]["name"] != "redis":
            raise ValueError(
                "graph_cache is not redis: "
                f"{config_obj['graph_cache']['name']}")
        cfg = config_obj["graph_cache"]["cfg"]
    elif redis_name == "rbody":
        if config_obj["data_store"]["name"] != "redis":
            raise ValueError(
                "data_store is not redis: "
                f"{config_obj['data_store']['name']}")
        cfg = config_obj["data_store"]["cfg"]
    elif redis_name == "rdata":
        if config_obj["queue_pool"]["name"] != "redis":
            raise ValueError(
                "queue_pool is not redis: "
                f"{config_obj['queue_pool']['name']}")
        cfg = config_obj["queue_pool"]["cfg"]
    elif redis_name == "rworker":
        if config_obj["executor_manager"]["name"] != "redis":
            raise ValueError(
                "executor_manager is not redis: "
                f"{config_obj['executor_manager']['name']}")
        cfg = config_obj["executor_manager"]["cfg"]
    else:
        raise ValueError(f"invalid redis_name: {redis_name}")
    if overwrite_prefix:
        old_prefix = cfg.get("prefix")
        if not old_prefix or old_prefix == overwrite_prefix:
            raise ValueError(
                f"cannot overwrite prefix {old_prefix} "
                f"with {overwrite_prefix}")
        cfg["prefix"] = overwrite_prefix
    return Redis(cfg=cfg)


def clear_redis(config_fname: str, redis_name: PseudoRedisName) -> None:
    redis = get_redis(
        config_fname, redis_name=redis_name, overwrite_prefix=None)
    redis.flushall()


def load_smind(config_fname: str) -> ScattermindAPI:
    with open(config_fname, "rb") as fin:
        config_obj = json.load(fin)
    return load_api(config_obj)


def load_graph(
        config: Config,
        smind: ScattermindAPI,
        graph_fname: str) -> tuple[GNamespace, str, str, int | None]:
    with open(os.path.join(config["graphs"], graph_fname), "rb") as fin:
        graph_def_obj = json.load(fin)
    ns = smind.load_graph(graph_def_obj)
    inputs = list(smind.main_inputs(ns))
    outputs = list(smind.main_outputs(ns))
    if len(inputs) != 1:
        raise ValueError(f"invalid graph inputs: {inputs}")
    if len(outputs) != 1:
        raise ValueError(f"invalid graph outputs: {outputs}")
    _, embed_shape = smind.output_format(ns, outputs[0])
    if len(embed_shape) != 1:
        raise ValueError(f"invalid graph output shape: {embed_shape}")
    return ns, inputs[0], outputs[0], embed_shape[0]


def get_queue_stats(smind: ScattermindAPI) -> list[QueueStat]:
    try:
        return [
            {
                "id": stat["id"].to_parseable(),
                "name": stat["name"].get(),
                "queue_length": stat["queue_length"],
                "listeners": stat["listeners"],
            }
            for stat in smind.get_queue_stats()
        ]
    except redis_lib.ConnectionError:
        print(traceback.format_exc())
        return []


GEMMA_FOLDER = "study/mdata/gemma2b/"


def get_token_count(prompts: list[str]) -> list[int]:
    start_time = time.monotonic()
    token_fn = tokenizer.Tokenizer(
        os.path.join(GEMMA_FOLDER, "tokenizer.model"))
    prompt_tokens = [token_fn.encode(prompt) for prompt in prompts]
    res = [len(p) for p in prompt_tokens]
    duration = time.monotonic() - start_time
    print(f"tokenization time: {duration}s")
    return res


def clean(text: str) -> str:
    text = text.strip()
    while True:
        prev_text = text
        text = unescape(text)
        if prev_text == text:
            break
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"\n\n+", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\n\n+", "\n\n", text)
    return text


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?\s*>", "\n", text.strip())
    text = re.sub(r"<(?:\"[^\"]*\"['\"]*|'[^']*'['\"]*|[^'\">])+>", "", text)
    return text


def normalize_text(text: str) -> str:
    return clean(strip_html(text))


def snippify_text(
        text: str, *, chunk_size: int, chunk_padding: int) -> Iterable[str]:
    pos = 0
    content = text.strip()
    if not content:
        return
    while pos < len(content):
        cur = content[pos:pos + chunk_size]
        if len(cur) < chunk_size:
            cur = cur.strip()
            if cur:
                yield cur
            break
        cur = cur.strip()
        rpos = cur.rfind(" ", 0, -chunk_padding)
        if rpos > 0:
            small = cur[0:rpos].strip()
            if small:
                yield small
            spos = small.rfind(" ")
            if spos > 0:
                pos += spos
            else:
                pos += len(small)
        else:
            yield cur
            pos += len(cur)


def get_text_results_immediate(
        texts: list[str],
        *,
        smind: ScattermindAPI,
        ns: GNamespace,
        input_field: str,
        output_field: str,
        output_sample: T) -> list[T | None]:
    if not texts:
        return []
    lookup: dict[TaskId, int] = {}
    for ix, text in enumerate(texts):
        task_id = smind.enqueue_task(
            ns,
            {
                input_field: text,
            })
        print(f"enqueue task {task_id} ({len(text)})")
        lookup[task_id] = ix
    sent_tasks = list(lookup.keys())
    res: dict[int, T] = {}
    tids: list[TaskId] = []
    success = False
    try:
        for tid, resp in smind.wait_for(sent_tasks, timeout=300):
            if resp["error"] is not None:
                error = resp["error"]
                print(f"{error['code']} ({error['ctx']}): {error['message']}")
                print("\n".join(error["traceback"]))
            result = resp["result"]
            if result is not None:
                if output_field in ("text", "tags"):
                    output: T = cast(T, tensor_to_str(result[output_field]))
                else:
                    output = cast(T, list(result[output_field].cpu().tolist()))
                if not isinstance(output, type(output_sample)):
                    raise ValueError(
                        "output does not match sample. "
                        f"output={output} sample={output_sample} "
                        f"{type(output)}<:{type(output_sample)}")
                curix = lookup[tid]
                res[curix] = output
            print(
                f"retrieved task {tid} ({resp['ns']}) {resp['status']} "
                f"{resp['duration']}s retry={resp['retries']}")
            tids.append(tid)
        success = True
    finally:
        tasks = tids if success else sent_tasks
        for tid in tasks:
            smind.clear_task(tid)
    return [res.get(ix, None) for ix in range(len(texts))]
