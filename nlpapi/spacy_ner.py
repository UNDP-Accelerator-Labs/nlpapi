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
import threading
from typing import cast, Literal

import spacy
from scattermind.system.base import GraphId, NodeId
from scattermind.system.client.client import ComputeTask
from scattermind.system.graph.graph import Graph
from scattermind.system.graph.node import Node
from scattermind.system.info import DataFormatJSON
from scattermind.system.payload.values import ComputeState
from scattermind.system.queue.queue import QueuePool
from scattermind.system.readonly.access import ReadonlyAccess
from scattermind.system.torch_util import (
    create_tensor,
    pad_list,
    str_to_tensor,
    tensor_to_str,
)
from spacy.language import Language


LOCK = threading.RLock()


LanguageStr = Literal["en", "xx"]
LANGUAGES: dict[LanguageStr, str] = {
    "en": "en_core_web_sm",
    "xx": "xx_ent_wiki_sm",
}


class SpacyNERNode(Node):
    def __init__(self, kind: str, graph: Graph, node_id: NodeId) -> None:
        super().__init__(kind, graph, node_id)
        self._model: Language | None = None

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
                "ranges": ("int", [2, None]),
                "text": ("uint8", [None, None]),
            },
        }

    def get_weight(self) -> float:
        return 1.0

    def get_load_cost(self) -> float:
        return 1.0  # TODO

    def session_field(self) -> str | None:
        return None

    def do_load(self, roa: ReadonlyAccess) -> None:

        def load_language(language: LanguageStr) -> Language:
            lang = LANGUAGES.get(language)
            if lang is None:
                raise ValueError(
                    f"unknown language ({sorted(LANGUAGES.keys())}): "
                    f"{language}")
            return spacy.load(lang)

        with LOCK:
            self._model = load_language(
                cast(LanguageStr, self.get_arg("lang").get("str")))

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
        entities = self.get_arg("entities").get("set_str")
        print("execute NER model")
        inputs = state.get_values()
        model = self._model
        texts = [
            tensor_to_str(val)
            for val in inputs.get_data("text").iter_values()
        ]
        for task, text in zip(inputs.get_current_tasks(), texts):
            doc = model(text)
            starts = []
            ends = []
            ents = []
            max_len = 0
            for ent in doc.ents:
                if ent.label_ not in entities:
                    continue
                cur_text = str_to_tensor(ent.text)
                ents.append(cur_text)
                if cur_text.shape[0] > max_len:
                    max_len = cur_text.shape[0]
                starts.append(ent.start_char)
                ends.append(ent.end_char)

            if not ents:
                ents.append(str_to_tensor(""))
                starts.append(0)
                ends.append(0)

            range_tensor = create_tensor([starts, ends], dtype="int")
            text_tensor = pad_list(ents, [max_len])

            state.push_results(
                "out",
                [task],
                {
                    "ranges": state.create_single(range_tensor),
                    "text": state.create_single(text_tensor),
                })
        print("execute NER model done")
