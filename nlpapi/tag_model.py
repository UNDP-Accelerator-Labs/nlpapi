import threading

# FIXME: the types are there, though...
from keybert import KeyBERT  # type: ignore
from scattermind.system.base import GraphId, NodeId
from scattermind.system.client.client import ComputeTask
from scattermind.system.graph.graph import Graph
from scattermind.system.graph.node import Node
from scattermind.system.info import DataFormatJSON
from scattermind.system.payload.values import ComputeState
from scattermind.system.queue.queue import QueuePool
from scattermind.system.readonly.access import ReadonlyAccess
from scattermind.system.torch_util import str_to_tensor, tensor_to_str

from nlpapi.util import get_sentence_transformer


LOCK = threading.RLock()


class TagModelNode(Node):
    def __init__(self, kind: str, graph: Graph, node_id: NodeId) -> None:
        super().__init__(kind, graph, node_id)
        self._model: KeyBERT | None = None

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
                "tags": ("uint8", [None]),
            },
        }

    def get_weight(self) -> float:
        return 1.0

    def get_load_cost(self) -> float:
        return 1.0  # TODO

    def do_load(self, roa: ReadonlyAccess) -> None:
        with LOCK:
            model_name = self.get_arg("model").get(
                "str", "all-distilroberta-v1")
            cache_dir = roa.get_scratchspace(self)
            model = get_sentence_transformer(model_name, cache_dir)
            self._model = KeyBERT(model)

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
        th = self.get_arg("threshold").get("float")
        inputs = state.get_values()
        model = self._model
        texts = [
            tensor_to_str(val)
            for val in inputs.get_data("text").iter_values()
        ]
        task_keywords = model.extract_keywords(
            texts, keyphrase_ngram_range=(1, 2), threshold=th)
        for task, keywords in zip(inputs.get_current_tasks(), task_keywords):
            state.push_results(
                "out",
                [task],
                {
                    "tags": state.create_single(str_to_tensor(f"{keywords}")),
                })
        print("execute model done")
