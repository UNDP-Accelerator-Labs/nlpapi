# import contextlib
# import os
# import threading
# import time
# from collections.abc import Iterator

# import torch

# # gemma is not in the requirements anymore
# from gemma.config import get_config_for_2b, get_config_for_7b
# from gemma.model import GemmaForCausalLM
# from scattermind.system.base import GraphId, NodeId
# from scattermind.system.client.client import ComputeTask
# from scattermind.system.graph.graph import Graph
# from scattermind.system.graph.node import Node
# from scattermind.system.info import DataFormatJSON
# from scattermind.system.payload.values import ComputeState
# from scattermind.system.queue.queue import QueuePool
# from scattermind.system.readonly.access import ReadonlyAccess
# from scattermind.system.torch_util import (
#     get_system_device,
#     str_to_tensor,
#     tensor_to_str,
# )


# # prompt helpers
# USER_CHAT_TEMPLATE = r"<start_of_turn>user\n{prompt}<end_of_turn>\n"
# MODEL_CHAT_TEMPLATE = r"<start_of_turn>model\n{prompt}<end_of_turn>\n"
# MODEL_START = r"<start_of_turn>model\n"


# @contextlib.contextmanager
# def set_default_tensor_type(dtype: torch.dtype | None) -> Iterator[None]:
#     """
#     Sets the default torch dtype to the given dtype.

#     Args:
#         dtype (torch.dtype): The dtype.
#     """
#     torch.set_default_dtype(dtype)
#     yield
#     torch.set_default_dtype(torch.float)


# LOCK = threading.RLock()


# class GemmaModelNode(Node):
#     def __init__(self, kind: str, graph: Graph, node_id: NodeId) -> None:
#         super().__init__(kind, graph, node_id)
#         self._model: GemmaForCausalLM | None = None

#     def do_is_pure(
#             self,
#             graph: Graph,
#             queue_pool: QueuePool,
#             pure_cache: dict[GraphId, bool]) -> bool:
#         return True

#     def get_input_format(self) -> DataFormatJSON:
#         return {
#             "text": ("uint8", [None]),
#         }

#     def get_output_format(self) -> dict[str, DataFormatJSON]:
#         return {
#             "out": {
#                 "text": ("uint8", [None]),
#             },
#         }

#     def get_weight(self) -> float:
#         return 1.0

#     def get_load_cost(self) -> float:
#         return 1.0  # TODO

#     def _load_model(self) -> GemmaForCausalLM:
#         model_folder = self.get_arg("folder").get("str")
#         variant = self.get_arg("variant").get("str")
#         # Model Config.
#         model_config = \
#             get_config_for_2b() if "2b" in variant else get_config_for_7b()
#         model_config.tokenizer = os.path.join(
#             model_folder, "tokenizer.model")
#         model_config.quant = "quant" in variant

#         # Model.
#         device = get_system_device()
#         with set_default_tensor_type(model_config.get_dtype()):
#             model = GemmaForCausalLM(model_config)
#             ckpt_path = os.path.join(model_folder, f"gemma-{variant}.ckpt")
#             model.load_weights(ckpt_path)
#             return model.to(device).eval()

#     def do_load(self, roa: ReadonlyAccess) -> None:
#         with LOCK:
#             print("load gemma")
#             start_load = time.monotonic()
#             self._model = self._load_model()
#             print(f"load gemma took {time.monotonic() - start_load}s")

#     def do_unload(self) -> None:
#         with LOCK:
#             self._model = None

#     def expected_output_meta(
#             self, state: ComputeState) -> dict[str, tuple[float, int]]:
#         tasks = list(state.get_inputs_tasks())
#         return {
#             "out": (len(tasks), ComputeTask.get_total_byte_size(tasks)),
#         }

#     def execute_tasks(self, state: ComputeState) -> None:
#         assert self._model is not None
#         model = self._model
#         print("execute gemma")
#         use_template = self.get_arg("use_template").get("bool", False)
#         maxlen = self.get_arg("maxlen").get("int")
#         inputs = state.get_values()

#         def convert(val: torch.Tensor) -> str:
#             text = tensor_to_str(val)
#             if use_template:
#                 return (
#                     f"{USER_CHAT_TEMPLATE.format(prompt=text)}{MODEL_START}")
#             return text

#         texts = [
#             convert(val)
#             for val in inputs.get_data("text").iter_values()
#         ]

#         batch_size = self.get_arg("batch_size").get("int", len(texts))

#         outs: list[str] = []
#         with LOCK:
#             start_exec = time.monotonic()
#             for pos in range(0, len(texts), batch_size):
#                 outs.extend(model.generate(
#                     texts[pos:pos + batch_size],
#                     device=get_system_device(),
#                     output_len=maxlen))
#             print(f"execute gemma took {time.monotonic() - start_exec}s")
#         for task, out in zip(inputs.get_current_tasks(), outs):
#             state.push_results(
#                 "out",
#                 [task],
#                 {
#                     "text": state.create_single(str_to_tensor(out)),
#                 })
#         print("execute gemma done")
