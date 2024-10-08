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
"""Model for text embedding."""
import threading

from scattermind.system.base import GraphId, NodeId
from scattermind.system.client.client import ComputeTask
from scattermind.system.graph.graph import Graph
from scattermind.system.graph.node import Node
from scattermind.system.info import DataFormatJSON
from scattermind.system.payload.values import ComputeState
from scattermind.system.queue.queue import QueuePool
from scattermind.system.readonly.access import ReadonlyAccess
from scattermind.system.torch_util import create_tensor, tensor_to_str
from sentence_transformers import SentenceTransformer  # type: ignore

from nlpapi.util import get_sentence_transformer


LOCK = threading.RLock()


class EmbedModelNode(Node):
    """
    The model uses a sentence transformer to create embeddings from a text.

    Args:
        Node (_type_): _description_
    """
    def __init__(self, kind: str, graph: Graph, node_id: NodeId) -> None:
        super().__init__(kind, graph, node_id)
        self._model: SentenceTransformer | None = None

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
                "embed": ("float32", [384]),
            },
        }

    def get_weight(self) -> float:
        return 1.0

    def get_load_cost(self) -> float:
        return 1.0  # TODO

    def session_field(self) -> str | None:
        return None

    def do_load(self, roa: ReadonlyAccess) -> None:
        with LOCK:
            model_name = self.get_arg("model").get(
                "str", "multi-qa-MiniLM-L6-cos-v1")
            cache_dir = roa.get_scratchspace(self)
            self._model = get_sentence_transformer(model_name, cache_dir)

    def do_unload(self) -> None:
        self._model = None

    def expected_output_meta(
            self, state: ComputeState) -> dict[str, tuple[float, int]]:
        tasks = list(state.get_inputs_tasks())
        return {
            "out": (len(tasks), ComputeTask.get_total_byte_size(tasks)),
        }

    def execute_tasks(self, state: ComputeState) -> None:
        assert self._model is not None
        print("execute model")
        inputs = state.get_values()
        model = self._model
        texts = [
            tensor_to_str(val)
            for val in inputs.get_data("text").iter_values()
        ]
        embeds = create_tensor(model.encode(texts), dtype="float32")
        state.push_results(
            "out",
            inputs.get_current_tasks(),
            {
                "embed": state.create_uniform(embeds),
            })
        print("execute model done")
