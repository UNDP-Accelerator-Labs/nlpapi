import json
import time

import torch
from scattermind.system.client.loader import load_client_pool
from scattermind.system.config.config import Config
from scattermind.system.logger.loader import load_event_listener
from scattermind.system.logger.log import EventStream
from scattermind.system.payload.loader import load_store
from scattermind.system.payload.values import TaskValueContainer
from scattermind.system.queue.loader import load_queue_pool
from scattermind.system.queue.strategy.loader import (
    load_node_strategy,
    load_queue_strategy,
)
from scattermind.system.readonly.loader import load_readonly_access


def load_config() -> Config:
    with open("config.json", "rb") as fin:
        config_obj = json.load(fin)
    config = Config()
    logger = EventStream()
    logger_obj = config_obj["logger"]
    for listener_def in logger_obj["listeners"]:
        logger.add_listener(
            load_event_listener(listener_def, logger_obj["disable_events"]))
    config.set_logger(logger)
    config.set_data_store(load_store(config_obj["data_store"]))
    config.set_queue_pool(load_queue_pool(config_obj["queue_pool"]))
    config.set_client_pool(load_client_pool(config_obj["client_pool"]))
    strategy_obj = config_obj["strategy"]
    config.set_node_strategy(load_node_strategy(strategy_obj["node"]))
    config.set_queue_strategy(load_queue_strategy(strategy_obj["queue"]))
    config.set_readonly_access(
        load_readonly_access(config_obj["readonly_access"]))
    return config


def run() -> None:
    config = load_config()
    with open("graph.json", "rb") as fin:
        graph_def_obj = json.load(fin)
    config.load_graph(graph_def_obj)
    real_start = time.monotonic()
    task_id = config.enqueue(TaskValueContainer({
        "value": torch.tensor([[0, 1], [2, 3]]),
    }))
    print(f"enqueued {task_id}")
    for tid, resp in config.wait_for([task_id]):
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
            print(result["value"])


if __name__ == "__main__":
    run()
