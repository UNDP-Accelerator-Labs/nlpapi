import argparse
import json
import os
import sys
import time
from typing import TypedDict

import pandas as pd
from gemma import tokenizer
from scattermind.api.api import ScattermindAPI
from scattermind.api.loader import load_api
from scattermind.system.base import TaskId
from scattermind.system.names import GNamespace
from scattermind.system.torch_util import tensor_to_str


Pad = TypedDict('Pad', {
    "id": int,
    "text": str,
    "is_public": bool,
})
JSONPad = TypedDict('JSONPad', {
    "id": int,
    "is_public": bool,
    "title": str,
    "content": str,
})
JSONPads = TypedDict('JSONPads', {
    "pads": list[JSONPad],
})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run scattermind of a batch of data.")
    parser.add_argument(
        "--graph",
        type=str,
        help="The scattermind graph file.")
    parser.add_argument(
        "--input",
        type=str,
        help=(
            "The input or input file if it starts with @. If @ is a folder "
            "all files ending in '.txt' are passed as individual prompts."))
    parser.add_argument(
        "--output",
        type=str,
        help="The output file or '-' for stdout.")
    parser.add_argument(
        "--config",
        default="config.json",
        type=str,
        help="The scattermind configuration file.")
    return parser.parse_args()


def load_config(config_fname: str) -> ScattermindAPI:
    with open(config_fname, "rb") as fin:
        config_obj = json.load(fin)
    return load_api(config_obj)


def load_graph(
        smind: ScattermindAPI,
        graph_fname: str) -> tuple[GNamespace, str, str]:
    with open(graph_fname, "rb") as fin:
        graph_def_obj = json.load(fin)
    ns = smind.load_graph(graph_def_obj)
    inputs = list(smind.main_inputs(ns))
    outputs = list(smind.main_outputs(ns))
    if len(inputs) != 1:
        raise ValueError(f"invalid graph inputs: {inputs}")
    if len(outputs) != 1:
        raise ValueError(f"invalid graph outputs: {outputs}")
    return ns, inputs[0], outputs[0]


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


def run() -> None:
    # ./run.sh
    # python -m nlpapi --config study/config.json --graph
    # study/graphs/graph_tags.json --input @sm_pads.json --output tags.csv

    # ./run.sh
    # python -m nlpapi --config study/config.json --graph
    # study/graphs/graph_embed.json --input @sm_pads.json --output out.csv

    # ./run.sh
    # python -m nlpapi --config study/config.json --graph
    # study/graphs/graph_gemma.json --input 'tell me about the highest
    # mountain in the world' --output -
    print(sys.argv)
    args = parse_args()
    graph_fname = args.graph
    input_str = args.input
    if input_str.startswith("@"):
        input_fname: str | None = input_str[1:]
    else:
        input_fname = None
    output_fname = args.output
    is_stdout = output_fname == "-"
    config_fname = args.config
    smind = load_config(config_fname)
    ns, input_field, output_field = load_graph(smind, graph_fname)

    def from_str(ix: int, text: str) -> JSONPad:
        return {
            "id": ix,
            "is_public": True,
            "title": text,
            "content": "",
        }

    direct_in: bool
    if input_fname is None:
        pads: JSONPads = {
            "pads": [from_str(-1, input_str)],
        }
        direct_in = True
    else:
        if os.path.isdir(input_fname):
            pad_list: list[JSONPad] = []
            for fix, fname in enumerate(os.listdir(input_fname)):
                if not fname.endswith(".txt"):
                    continue
                read_fname = os.path.join(input_fname, fname)
                if not os.path.isfile(read_fname):
                    continue
                with open(read_fname, "r", encoding="utf-8") as fin:
                    pad_list.append(from_str(fix, fin.read()))
            pads = {
                "pads": pad_list,
            }
            direct_in = True
        elif input_fname.endswith(".json"):
            with open(input_fname, "rb") as pin:
                pads = json.load(pin)
            direct_in = False
        else:
            with open(input_fname, "r", encoding="utf-8") as fin:
                pads = {
                    "pads": [from_str(-1, fin.read())],
                }
            direct_in = True

    if direct_in:
        counts = get_token_count([cp["title"] for cp in pads["pads"]])
        print(f"input token counts: {counts}")
    real_start = time.monotonic()
    pad_lookup: dict[TaskId, Pad] = {}

    def add_snippet(pad_id: int, pad_public: bool, text: str) -> None:
        if not text.strip():
            return
        task_id = smind.enqueue_task(
            ns,
            {
                input_field: text,
            })
        pad_lookup[task_id] = {
            "id": pad_id,
            "is_public": pad_public,
            "text": text,
        }
        print(f"enqueued {pad_id}: {task_id}")

    chunk_size = 600
    for pad in pads["pads"]:
        pad_id = int(pad["id"])
        pad_public = bool(pad["is_public"])
        title = f"{pad['title']}"
        add_snippet(pad_id, pad_public, title)
        content = f"{pad['content']}"
        pos = 0
        while pos < len(content):
            cur = content[pos:pos + chunk_size]
            if len(cur) < chunk_size:
                add_snippet(pad_id, pad_public, cur)
                break
            rpos = cur.rfind(" ")
            if rpos > 0:
                small = cur[0:rpos]
                add_snippet(pad_id, pad_public, small)
                spos = small.rfind(" ")
                if spos > 0:
                    pos += spos
                else:
                    pos += len(small)
            else:
                pos += len(cur)

    columns = ["id", "is_public", input_field, output_field]
    if not is_stdout and not os.path.exists(output_fname):
        pd.DataFrame([], columns=columns).to_csv(
            output_fname, index=False, header=True)
    count = 0
    out_strs = []
    first_ready = None
    last_ready = None
    min_real_time = None
    max_real_time = None
    avg_real_time = None
    for tid, resp in smind.wait_for(list(pad_lookup.keys()), timeout=None):
        count += 1
        status = resp["status"]
        duration = resp["duration"]
        real_time = time.monotonic() - real_start
        retries = resp["retries"]
        print(
            f"{tid} status: {status} "
            f"time: {duration}s real: {real_time}s retries: {retries} "
            f"task count: {count} avg real: {real_time / count}s/task")
        if first_ready is None or first_ready > duration:
            first_ready = duration
        if last_ready is None or last_ready < duration:
            last_ready = duration
        if min_real_time is None or min_real_time > real_time:
            min_real_time = real_time
        if max_real_time is None or max_real_time < real_time:
            max_real_time = real_time
        if avg_real_time is None or avg_real_time < real_time / count:
            avg_real_time = real_time / count
        if resp["error"] is not None:
            error = resp["error"]
            print(f"{error['code']} ({error['ctx']}): {error['message']}")
            print("\n".join(error["traceback"]))
        result = resp["result"]
        if result is not None:
            if output_field in ("text", "tags"):
                output = tensor_to_str(result[output_field])
            else:
                output = f"{list(result[output_field].cpu().tolist())}"
            curpad = pad_lookup[tid]
            res = {
                "id": [curpad["id"]],
                "is_public": [curpad["is_public"]],
                input_field: [curpad["text"]],
                output_field: [output],
            }
            if is_stdout:
                print(json.dumps(res, indent=2, sort_keys=True))
                out_strs.append(output)
            else:
                pd.DataFrame(res, columns=columns).to_csv(
                    output_fname, mode="a", index=False, header=False)
    if out_strs:
        tc_out = get_token_count(out_strs)
        print(f"output token count: {tc_out}")
        print(f"last ready: {last_ready}s")
        print(f"max real: {max_real_time}s")
        print(f"avg: {avg_real_time}s/task")
        print(f"first ready: {first_ready}s")
        print(f"min real: {min_real_time}s")


if __name__ == "__main__":
    run()
