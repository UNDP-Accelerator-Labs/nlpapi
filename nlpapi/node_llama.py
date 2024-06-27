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
import os
from typing import cast

import llama_cpp
from llama_cpp import CreateChatCompletionStreamResponse, Llama
from scattermind.system.base import GraphId, NodeId
from scattermind.system.graph.graph import Graph
from scattermind.system.graph.node import Node
from scattermind.system.info import DataFormatJSON, STRING_INFO
from scattermind.system.payload.values import ComputeState
from scattermind.system.queue.queue import QueuePool
from scattermind.system.readonly.access import ReadonlyAccess
from scattermind.system.torch_util import str_to_tensor, tensor_to_str

from nlpapi.default_prompts import PROMPT_REMINDER
from nlpapi.llama import (
    append_new_message,
    load_system_prompt,
    ROLE_ASSISTANT,
    ROLE_SYSTEM,
    ROLE_USER,
)


class LlamaNode(Node):
    def __init__(self, kind: str, graph: Graph, node_id: NodeId) -> None:
        super().__init__(kind, graph, node_id)
        self._model: Llama | None = None
        self._cache_dir: str | None = None

    def do_is_pure(
            self,
            graph: Graph,
            queue_pool: QueuePool,
            pure_cache: dict[GraphId, bool]) -> bool:
        return False

    def get_input_format(self) -> DataFormatJSON:
        return {
            "prompt": STRING_INFO,
            "system_prompt_key": STRING_INFO,
        }

    def get_output_format(self) -> dict[str, DataFormatJSON]:
        return {
            "out": {
                "response": STRING_INFO,
            },
        }

    def get_weight(self) -> float:
        return 1.0

    def get_load_cost(self) -> float:
        return 1.0  # TODO

    def batch_size(self) -> int | None:
        return 1

    def session_field(self) -> str | None:
        return None

    def do_load(self, roa: ReadonlyAccess) -> None:
        lib = os.getenv("LLAMA_CPP_LIB")
        lib_exists = False if lib is None else os.path.exists(lib)
        print(f"LLAMA_CPP_LIB is {lib} {lib_exists=}")
        self._model = Llama(
            model_path=self.get_arg("model_path").get("str"),
            n_ctx=30000,
            n_gpu_layers=33,
            # n_threads=6,
            # n_batch=521,
            seed=123,
            # flash_attn=True,
            verbose=True)
        self._cache_dir = roa.get_scratchspace(self)

    def do_unload(self) -> None:
        self._model = None
        self._cache_dir = None

    def expected_output_meta(
            self, state: ComputeState) -> dict[str, tuple[float, int]]:
        tasks = list(state.get_inputs_tasks())
        return {
            "out": (len(tasks), len(tasks) * 500),
        }

    def _execute_prompt(
            self,
            model: Llama,
            prompt: str,
            *,
            system_prompt_key: str,
            cache_dir: str) -> str:
        # FIXME: maybe use state
        # if not load_state(model, cache_dir):
        set_seed = True
        add_reminder = True
        if set_seed:
            model.set_seed(123)
        messages = load_system_prompt(
            cache_dir=cache_dir,
            system_prompt_key=system_prompt_key)
        print(f"SYSTEM PROMPT:\n\n\"\"\"{messages[0]['content']}\"\"\"\n")
        if prompt:
            append_new_message(messages, text=prompt, role=ROLE_USER)
        if add_reminder:
            append_new_message(
                messages, text=PROMPT_REMINDER, role=ROLE_SYSTEM)
        response: list[str] = []

        try:
            for out in model.create_chat_completion(
                    messages, max_tokens=None, stream=True):
                resp = cast(CreateChatCompletionStreamResponse, out)
                delta = resp["choices"][0]["delta"]
                content: str | None = cast(str, delta.get("content", ""))
                if not content:
                    continue
                response.append(content)
        except EOFError:
            pass
        full_response = "".join(response)
        messages.append(
            {
                "role": ROLE_ASSISTANT,
                "content": full_response,
            })

        # FIXME: use state
        # save_state(model, cache_dir)
        return full_response

    def execute_tasks(self, state: ComputeState) -> None:
        assert self._model is not None
        assert self._cache_dir is not None
        model = self._model
        cache_dir = self._cache_dir
        inputs = state.get_values()
        prompts = inputs.get_data("prompt")
        system_prompt_keys = inputs.get_data("system_prompt_key")
        tasks = inputs.get_current_tasks()

        model.set_cache(llama_cpp.llama_cache.LlamaDiskCache(
            os.path.join(cache_dir, self.get_id().to_parseable())))
        for prompt, system_prompt_key, task in zip(
                prompts.iter_values(),
                system_prompt_keys.iter_values(),
                tasks):
            prompt_str = tensor_to_str(prompt)
            system_prompt_key_str = tensor_to_str(system_prompt_key)
            response_str = self._execute_prompt(
                model,
                prompt_str.strip(),
                system_prompt_key=system_prompt_key_str.strip(),
                cache_dir=cache_dir)
            response = str_to_tensor(response_str)
            state.push_results(
                "out",
                [task],
                {
                    "response": state.create_single(response),
                })
