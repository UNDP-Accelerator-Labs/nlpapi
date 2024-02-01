import json
import time

from scattermind.api.api import ScattermindAPI
from scattermind.api.loader import load_api


def load_config() -> ScattermindAPI:
    with open("config.json", "rb") as fin:
        config_obj = json.load(fin)
    return load_api(config_obj)


def run() -> None:
    smind = load_config()
    with open("graph.json", "rb") as fin:
        graph_def_obj = json.load(fin)
    smind.load_graph(graph_def_obj)
    real_start = time.monotonic()
    task_id_0 = smind.enqueue_task({
        "text": "abc",
    })
    print(f"enqueued {task_id_0}")
    task_id_1 = smind.enqueue_task({
        "text": "hallo",
    })
    print(f"enqueued {task_id_1}")
    for tid, resp in smind.wait_for([task_id_0, task_id_1], timeout=60.0):
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
            print(result["embed"])


if __name__ == "__main__":
    run()
