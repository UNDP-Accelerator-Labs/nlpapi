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


def load_config() -> ScattermindAPI:
    with open("config.json", "rb") as fin:
        config_obj = json.load(fin)
    return load_api(config_obj)


def run() -> None:
    smind = load_config()
    with open("graph.json", "rb") as fin:
        graph_def_obj = json.load(fin)
    smind.load_graph(graph_def_obj)
    with open("sm_pads.json", "r", encoding="utf-8") as pin:
        pads = json.load(pin)
    real_start = time.monotonic()
    pad_lookup: dict[TaskId, Pad] = {}

    def add_snippet(pad_id: int, pad_public: bool, text: str) -> None:
        if not text.strip():
            return
        task_id = smind.enqueue_task({
            "text": text,
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

    out_file = "out.csv"
    columns = ["id", "is_public", "text", "embed"]
    if not os.path.exists(out_file):
        pd.DataFrame([], columns=columns).to_csv(out_file, index=False)
    for tid, resp in smind.wait_for(list(pad_lookup.keys()), timeout=60.0):
        status = resp["status"]
        duration = resp["duration"]
        real_time = time.monotonic() - real_start
        retries = resp["retries"]
        print(
            f"{tid} status: {status} "
            f"time: {duration}s real: {real_time}s retries: {retries}")
        if resp["error"] is not None:
            error = resp["error"]
            print(f"{error['code']} ({error['ctx']}): {error['message']}")
            print("\n".join(error["traceback"]))
        result = resp["result"]
        if result is not None:
            embed = f"{list(result['embed'].cpu().tolist())}"
            pad = pad_lookup[tid]
            pd.DataFrame({
                "id": [pad["id"]],
                "is_public": [pad["is_public"]],
                "text": [pad["text"]],
                "embed": [embed],
            }, columns=columns).to_csv(out_file, mode="a", index=False)


if __name__ == "__main__":
    run()
