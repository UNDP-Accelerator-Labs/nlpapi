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
"""CLI for testing model setups."""
import argparse
import json
import os
import sys
import time
from typing import TypedDict

import pandas as pd
from scattermind.api.api import InputTypes, ScattermindAPI
from scattermind.api.loader import load_api
from scattermind.system.base import TaskId
from scattermind.system.names import GNamespace
from scattermind.system.torch_util import tensor_to_str
from scattermind.system.util import first

from app.system.prep.clean import normalize_text
from app.system.prep.snippify import snippify_text


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
    """
    Parse command line arguments.

    Returns:
        argparse.Namespace: The arguments.
    """
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
        "--system-prompt-key",
        type=str,
        help="The system prompt key for llama.")
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
    """
    Load the scattermind API.

    Args:
        config_fname (str): The scattermind config file.

    Returns:
        ScattermindAPI: The scattermind API.
    """
    with open(config_fname, "rb") as fin:
        config_obj = json.load(fin)
    return load_api(config_obj)


def load_graph(
        smind: ScattermindAPI,
        graph_fname: str) -> tuple[GNamespace, str, list[str]]:
    """
    Load a model.

    Args:
        smind (ScattermindAPI): The scattermind API.
        graph_fname (str): The graph file.

    Returns:
        tuple[GNamespace, str, list[str]]: The namespace, input field, and
            output fields.
    """
    with open(graph_fname, "rb") as fin:
        graph_def_obj = json.load(fin)
    ns = smind.load_graph(graph_def_obj)
    inputs = list(smind.main_inputs(ns))
    outputs = list(smind.main_outputs(ns))
    if len(inputs) == 1:
        return ns, inputs[0], outputs
    return ns, "prompt", ["response"]


# GEMMA_FOLDER = "study/mdata/gemma2b/"


# def get_token_count(prompts: list[str]) -> list[int]:
#     start_time = time.monotonic()
#     token_fn = tokenizer.Tokenizer(
#         os.path.join(GEMMA_FOLDER, "tokenizer.model"))
#     prompt_tokens = [token_fn.encode(prompt) for prompt in prompts]
#     res = [len(p) for p in prompt_tokens]
#     duration = time.monotonic() - start_time
#     print(f"tokenization time: {duration}s")
#     return res


def run() -> None:
    """Run the process."""
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

    # ./run.sh
    # python -m nlpapi --config study/config.json --graph
    # study/graphs/graph_llama.json --input
    # 'today we are baking a chocolate cake'
    # --system-prompt-key 'verify_circular_economy' --output -
    print(sys.argv)
    args = parse_args()
    system_prompt_key = args.system_prompt_key
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
    ns, input_field, output_fields = load_graph(smind, graph_fname)

    def from_str(ix: int, text: str) -> JSONPad:
        content = normalize_text(text)
        print(f"reduced length of article from {len(text)} to {len(content)}")
        return {
            "id": ix,
            "is_public": True,
            "title": content,
            "content": "",
        }

    # direct_in: bool
    if input_fname is None:
        pads: JSONPads = {
            "pads": [from_str(-1, input_str)],
        }
        # direct_in = True
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
            # direct_in = True
        elif input_fname.endswith(".json"):
            with open(input_fname, "rb") as pin:
                pads = json.load(pin)
            # direct_in = False
        else:
            with open(input_fname, "r", encoding="utf-8") as fin:
                pads = {
                    "pads": [from_str(-1, fin.read())],
                }
            # direct_in = True

    # if direct_in:
    #     counts = get_token_count([cp["title"] for cp in pads["pads"]])
    #     print(f"input token counts: {counts}")
    real_start = time.monotonic()
    pad_lookup: dict[TaskId, Pad] = {}

    def add_snippet(pad_id: int, pad_public: bool, text: str) -> None:
        if not text.strip():
            return
        obj: dict[str, InputTypes] = {
            input_field: text,
        }
        if system_prompt_key is not None:
            obj["system_prompt_key"] = system_prompt_key
        task_id = smind.enqueue_task(ns, obj)
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

    columns = ["id", "is_public", input_field, *output_fields]
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
            curpad = pad_lookup[tid]
            res = {
                "id": [curpad["id"]],
                "is_public": [curpad["is_public"]],
                input_field: [
                    first(snippify_text(
                        curpad["text"],
                        chunk_size=100,
                        chunk_padding=10))[0],
                ],
            }
            for output_field in output_fields:
                if output_field in ("text", "tags", "response"):
                    output = tensor_to_str(result[output_field])
                else:
                    output = f"{list(result[output_field].cpu().tolist())}"
                res[output_field] = output
            if is_stdout:
                print(json.dumps(res, indent=2, sort_keys=True))
                out_strs.append(output)
            else:
                pd.DataFrame(res, columns=columns).to_csv(
                    output_fname, mode="a", index=False, header=False)
    if out_strs:
        # tc_out = get_token_count(out_strs)
        # print(f"output token count: {tc_out}")
        print(f"last ready: {last_ready}s")
        print(f"max real: {max_real_time}s")
        print(f"avg: {avg_real_time}s/task")
        print(f"first ready: {first_ready}s")
        print(f"min real: {min_real_time}s")


if __name__ == "__main__":
    run()
