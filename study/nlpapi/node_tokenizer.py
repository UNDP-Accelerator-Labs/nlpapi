from typing import get_args, Literal

from scattermind.system.base import NodeId
from scattermind.system.client.client import ComputeTask
from scattermind.system.graph.graph import Graph
from scattermind.system.graph.node import Node
from scattermind.system.info import DataFormatJSON
from scattermind.system.payload.values import ComputeState
from scattermind.system.queue.queue import QueuePool
from scattermind.system.readonly.access import ReadonlyAccess
from scattermind.system.torch_util import get_system_device, tensor_to_str

# FIXME: add transformer stubs
from transformers import DistilBertTokenizer  # type: ignore


OpName = Literal[
    "add",
    "mul",
]
ALL_OPS: set[OpName] = set(get_args(OpName))


class TokenizerNode(Node):
    def __init__(self, kind: str, graph: Graph, node_id: NodeId) -> None:
        super().__init__(kind, graph, node_id)
        self._tokenizer = None

    def do_is_pure(self, graph: Graph, queue_pool: QueuePool) -> bool:
        return True

    def get_input_format(self) -> DataFormatJSON:
        return {
            "text": ("uint8", [None]),
        }

    def get_output_format(self) -> dict[str, DataFormatJSON]:
        return {
            "out": {
                "input_ids": ("int64", [None]),
            },
        }

    def get_weight(self) -> float:
        return 1.0

    def get_load_cost(self) -> float:
        return 1.0  # TODO

    def do_load(self, roa: ReadonlyAccess) -> None:
        self._tokenizer = DistilBertTokenizer.from_pretrained(
            "distilbert-base-uncased")

    def do_unload(self) -> None:
        self._tokenizer = None

    def expected_output_meta(
            self, state: ComputeState) -> dict[str, tuple[float, int]]:
        tasks = list(state.get_inputs_tasks())
        return {
            "out": (len(tasks), ComputeTask.get_total_byte_size(tasks)),
        }

    def execute_tasks(self, state: ComputeState) -> None:
        assert self._tokenizer is not None
        print("execute tokenizer")
        inputs = state.get_values()
        text = inputs.get_data("text")
        texts = [
            tensor_to_str(row)
            for row in text.iter_values()
        ]
        device = get_system_device()
        res = self._tokenizer(
            texts, return_tensors="pt", padding=True, truncation=True)
        state.push_results(
            "out",
            inputs.get_current_tasks(),
            {
                "input_ids": state.create_masked(
                    res["input_ids"].to(device),
                    res["attention_mask"].to(device)),
            })
