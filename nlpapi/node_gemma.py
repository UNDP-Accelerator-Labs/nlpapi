import contextlib
import os
import threading
from collections.abc import Iterator

import torch
from gemma.config import get_config_for_2b, get_config_for_7b
from gemma.model import GemmaForCausalLM
from scattermind.system.base import NodeId
from scattermind.system.client.client import ComputeTask
from scattermind.system.graph.graph import Graph
from scattermind.system.graph.node import Node
from scattermind.system.info import DataFormatJSON
from scattermind.system.payload.values import ComputeState
from scattermind.system.queue.queue import QueuePool
from scattermind.system.readonly.access import ReadonlyAccess
from scattermind.system.torch_util import (
    get_system_device,
    str_to_tensor,
    tensor_to_str,
)


# model config
VARIANT = "7b-it-quant"
MODEL_DIR = "study/mdata/gemma/"


# prompt helpers
# USER_CHAT_TEMPLATE = r"<start_of_turn>user\n{prompt}<end_of_turn>\n"
# MODEL_CHAT_TEMPLATE = "<start_of_turn>model\n{prompt}<end_of_turn>\n"
# MODEL_START = "<start_of_turn>model\n"


@contextlib.contextmanager
def _set_default_tensor_type(dtype: torch.dtype) -> Iterator[None]:
    """
    Sets the default torch dtype to the given dtype.

    Args:
        dtype (torch.dtype): The dtype.
    """
    torch.set_default_dtype(dtype)
    yield
    torch.set_default_dtype(torch.float)


LOCK = threading.RLock()


class EmbedModelNode(Node):
    def __init__(self, kind: str, graph: Graph, node_id: NodeId) -> None:
        super().__init__(kind, graph, node_id)
        self._model: None = None

    def do_is_pure(self, graph: Graph, queue_pool: QueuePool) -> bool:
        return True

    def get_input_format(self) -> DataFormatJSON:
        return {
            "text": ("uint8", [None]),
        }

    def get_output_format(self) -> dict[str, DataFormatJSON]:
        return {
            "out": {
                "text": ("uint8", [None]),
            },
        }

    def get_weight(self) -> float:
        return 1.0

    def get_load_cost(self) -> float:
        return 1.0  # TODO

    def do_load(self, roa: ReadonlyAccess) -> None:
        with LOCK:
            # Model Config.
            model_config = \
                get_config_for_2b() if "2b" in VARIANT else get_config_for_7b()
            model_config.tokenizer = os.path.join(
                MODEL_DIR, "tokenizer.model")
            model_config.quant = "quant" in VARIANT

            # Model.
            device = get_system_device()
            with _set_default_tensor_type(model_config.get_dtype()):
                model = GemmaForCausalLM(model_config)
                ckpt_path = os.path.join(MODEL_DIR, f"gemma-{VARIANT}.ckpt")
                model.load_weights(ckpt_path)
                self._model = model.to(device).eval()

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
        maxlen = self.get_arg("maxlen").get("int")
        inputs = state.get_values()
        model = self._model
        texts = [
            tensor_to_str(val)
            # USER_CHAT_TEMPLATE.format(tensor_to_str(val)) + MODEL_START
            for val in inputs.get_data("text").iter_values()
        ]
        outs = model.generate(
            texts,
            device=get_system_device(),
            output_len=maxlen)
        for task, keywords in zip(inputs.get_current_tasks(), outs):
            state.push_results(
                "out",
                [task],
                {
                    "text": state.create_single(str_to_tensor(f"{keywords}")),
                })
        print("execute model done")