import argparse
import json
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pandas as pd
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from scattermind.api.api import ScattermindAPI
from scattermind.api.loader import load_api
from scattermind.system.names import GNamespace


FILE_PROTOCOL = "file://"


EMBED_SIZE = 384  # 768


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reads or writes from/to the vector db.")
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="The input file.")
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="The query.")
    parser.add_argument(
        "--name",
        type=str,
        help=(
            "The collection name. Must end in "
            "':dot', ':cos', ':euc', or ':man'."))
    parser.add_argument(
        "--db",
        type=str,
        help=(
            "The db connection string or filename "
            f"if it starts with {FILE_PROTOCOL}"))
    parser.add_argument(
        "--graph",
        type=str,
        default=None,
        help="The scattermind graph file.")
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


@contextmanager
def timing(name: str) -> Iterator[None]:
    start_time = time.monotonic()
    try:
        yield
    finally:
        duration = time.monotonic() - start_time
        print(f"{name} took {duration}s")


def run() -> None:
    # python -m vecdb --input out.csv --name test:dot --db file://vec.db

    # ./run.sh
    # python -m vecdb --name test:dot --db file://vec.db
    # --config study/config.json --graph study/graphs/graph_embed.json
    # --query 'circular economy'
    args = parse_args()
    input_file = args.input
    query = args.query
    if (input_file is None) == (query is None):
        raise ValueError("only one for --input or --query can be used at once")
    name = f"{args.name}"
    db_str = f"{args.db}"
    graph = args.graph
    config = args.config
    db: QdrantClient
    with timing("loading db"):
        if db_str.startswith(FILE_PROTOCOL):
            print(f"loading db file: {db_str.removeprefix(FILE_PROTOCOL)}")
            db = QdrantClient(path=db_str.removeprefix(FILE_PROTOCOL))
        else:
            print(f"loading db: {db_str}")
            db = QdrantClient(db_str)
    if input_file is not None:
        if name.endswith(":dot"):
            distance: Distance = Distance.DOT
        elif name.endswith(":cos"):
            distance = Distance.COSINE
        elif name.endswith(":euc"):
            distance = Distance.EUCLID
        elif name.endswith(":man"):
            distance = Distance.MANHATTAN
        else:
            raise ValueError(f"invalid name: {name}")
        db.recreate_collection(
            collection_name=name,
            vectors_config=VectorParams(size=EMBED_SIZE, distance=distance))
        for chunk in pd.read_csv(input_file, chunksize=100):
            # id,is_public,text,embed
            db.upsert(
                collection_name=name,
                points=[
                    PointStruct(
                        id=idx,  # right now row id but should be sth better
                        vector=json.loads(row["embed"]),
                        payload={
                            "id": row["id"],  # this id is not unique
                            "is_public": row["is_public"],
                            "text": row["text"],
                        })
                    for idx, row in chunk.iterrows()
                ])
    elif query is not None:
        if config is None or graph is None:
            raise ValueError("config and graph must be set for query")
        with timing("load config and graph"):
            smind = load_config(config)
            ns, input_field, output_field = load_graph(smind, graph)
        with timing("query"):
            real_start = time.monotonic()
            task_id = smind.enqueue_task(
                ns,
                {
                    input_field: query,
                })
            print(f"enqueued {task_id}: {query}")

            for tid, resp in smind.wait_for([task_id], timeout=None):
                status = resp["status"]
                duration = resp["duration"]
                real_time = time.monotonic() - real_start
                retries = resp["retries"]
                print(
                    f"{tid} status: {status} "
                    f"time: {duration}s real: {real_time}s retries: {retries}")
                if resp["error"] is not None:
                    error = resp["error"]
                    print(
                        f"{error['code']} "
                        f"({error['ctx']}): "
                        f"{error['message']}")
                    print("\n".join(error["traceback"]))
                result = resp["result"]
                if result is not None:
                    output = list(result[output_field].cpu().tolist())
                    hits = db.search(
                        collection_name=name,
                        query_vector=output,
                        limit=10)
                    print("results:")
                    for ix, hit in enumerate(hits):
                        print(f"hit {ix}: {hit}")


if __name__ == "__main__":
    run()
