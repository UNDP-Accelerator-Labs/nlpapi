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
"""Tagging model using KeyBERT."""
import re
import threading

# FIXME: the types are there, though...
from keybert import KeyBERT  # type: ignore


try:
    from nltk import pos_tag, word_tokenize  # type: ignore
except ModuleNotFoundError:
    # NOTE: need to make sure the symbols are there
    pos_tag = None  # pylint: disable=invalid-name
    word_tokenize = None  # pylint: disable=invalid-name
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
    str_to_tensor,
    tensor_to_str,
)

from nlpapi.util import get_sentence_transformer


REMOVE_NUMS = re.compile(r"\d+")
EMAIL = re.compile(r"\S+@\S+")
FULL_URL = re.compile(r"http[s]?\S+", flags=re.IGNORECASE)
EXCLUDE_TAGS = {"NNP", "NNPS"}


def remove_numbers(text: str) -> str:
    """
    Remove numbers from the text.

    Args:
        text (str): The text.

    Returns:
        str: The transformed text.
    """
    return REMOVE_NUMS.sub("", text)


def remove_proper_nouns(text: str) -> str:
    """
    Remove nouns.

    Args:
        text (str): The text.

    Returns:
        str: The transformed text.
    """
    pos_tags = pos_tag(word_tokenize(text))
    return " ".join((
        word
        for word, pos in pos_tags
        if pos not in EXCLUDE_TAGS))


def remove_emails_and_hyperlinks(text: str) -> str:
    """
    Remove emails and links.

    Args:
        text (str): The text.

    Returns:
        str: The transformed text.
    """
    return FULL_URL.sub("", EMAIL.sub("", text))


LOCK = threading.RLock()


class TagModelNode(Node):
    """Tagging model using KeyBERT."""
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
                "scores": ("float", [None]),
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
                "str", "distilbert-base-nli-mean-tokens")
            #     "str", "all-distilroberta-v1")
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
        print("execute tag model")
        th = self.get_arg("threshold").get("float")
        top_n = self.get_arg("top_n").get("int", 20)
        inputs = state.get_values()
        model = self._model

        def prep(text: str) -> str:
            text = remove_emails_and_hyperlinks(text)
            text = remove_proper_nouns(text)
            text = remove_numbers(text)
            return text

        texts = [
            prep(tensor_to_str(val))
            for val in inputs.get_data("text").iter_values()
        ]
        for task_ix, task in enumerate(inputs.get_current_tasks()):
            keyword_scores = model.extract_keywords(
                texts[task_ix], top_n=top_n)
            keywords: list[str] = []
            scores: list[float] = []
            print(keyword_scores)
            for keyword, score in keyword_scores:
                if score < th:
                    continue
                keywords.append(keyword.replace(",", " "))
                scores.append(score)
            state.push_results(
                "out",
                [task],
                {
                    "tags": state.create_single(
                        str_to_tensor(
                            ",".join(keywords) if keywords else " ")),
                    "scores": state.create_single(
                        create_tensor(scores, dtype="float")),
                })
        print("execute tag model done")
