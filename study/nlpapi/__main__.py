import argparse
import json
import os
import time
from typing import TypedDict

import pandas as pd
from scattermind.api.api import ScattermindAPI
from scattermind.api.loader import load_api
from scattermind.system.base import TaskId


Pad = TypedDict('Pad', {
    "id": int,
    "text": str,
    "is_public": bool,
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
        help="The input file.")
    parser.add_argument(
        "--output",
        type=str,
        help="The output file.")
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
        graph_fname: str) -> tuple[str, str]:
    with open(graph_fname, "rb") as fin:
        graph_def_obj = json.load(fin)
    smind.load_graph(graph_def_obj)
    inputs = list(smind.main_inputs())
    outputs = list(smind.main_outputs())
    if len(inputs) != 1:
        raise ValueError(f"invalid graph inputs: {inputs}")
    if len(outputs) != 1:
        raise ValueError(f"invalid graph outputs: {outputs}")
    return inputs[0], outputs[0]


def run() -> None:
    args = parse_args()
    graph_fname = args.graph
    input_fname = args.input
    output_fname = args.output
    config_fname = args.config
    smind = load_config(config_fname)
    input_field, output_field = load_graph(smind, graph_fname)
    with open(input_fname, "rb") as pin:
        pads = json.load(pin)
    real_start = time.monotonic()
    pad_lookup: dict[TaskId, Pad] = {}

    def add_snippet(pad_id: int, pad_public: bool, text: str) -> None:
        if not text.strip():
            return
        task_id = smind.enqueue_task({
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
    if not os.path.exists(output_fname):
        pd.DataFrame([], columns=columns).to_csv(
            output_fname, index=False, header=False)
    count = 0
    for tid, resp in smind.wait_for(list(pad_lookup.keys()), timeout=None):
        count += 1
        status = resp["status"]
        duration = resp["duration"]
        real_time = time.monotonic() - real_start
        retries = resp["retries"]
        print(
            f"{tid} status: {status} "
            f"time: {duration}s real: {real_time}s retries: {retries} "
            f"task count: {count} avg real: {real_time / count}")
        if resp["error"] is not None:
            error = resp["error"]
            print(f"{error['code']} ({error['ctx']}): {error['message']}")
            print("\n".join(error["traceback"]))
        result = resp["result"]
        if result is not None:
            output = f"{list(result[output_field].cpu().tolist())}"
            pad = pad_lookup[tid]
            pd.DataFrame({
                "id": [pad["id"]],
                "is_public": [pad["is_public"]],
                input_field: [pad["text"]],
                output_field: [output],
            }, columns=columns).to_csv(
                output_fname, mode="a", index=False, header=False)


if __name__ == "__main__":
    run()
