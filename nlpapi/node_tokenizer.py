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
"""Tokenizer node for the custom tagging model."""
from typing import get_args, Literal

from scattermind.system.base import GraphId, NodeId
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
    """The tokenizer node."""
    def __init__(self, kind: str, graph: Graph, node_id: NodeId) -> None:
        super().__init__(kind, graph, node_id)
        self._tokenizer = None

    def do_is_pure(
            self,
            graph: Graph,
            queue_pool: QueuePool,
            pure_cache: dict[GraphId, bool]) -> bool:
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

    def session_field(self) -> str | None:
        return None

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
        print("execute tokenizer done")
