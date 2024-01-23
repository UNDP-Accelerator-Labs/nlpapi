import logging
from typing import Literal, TypedDict

import torch
from scattermind.system.base import NodeId
from scattermind.system.client.client import ComputeTask
from scattermind.system.graph.graph import Graph
from scattermind.system.graph.node import Node
from scattermind.system.info import DataFormatJSON
from scattermind.system.payload.values import ComputeState
from scattermind.system.queue.queue import QueuePool
from scattermind.system.readonly.access import ReadonlyAccess
from scattermind.system.torch_util import get_system_device
from torch import nn

# FIXME: add transformer stubs
from transformers import DistilBertModel, modeling_utils  # type: ignore


AggType = Literal["cls", "mean"]
AGG_CLS: AggType = "cls"
AGG_MEAN: AggType = "mean"


ModelConfig = TypedDict('ModelConfig', {
    "agg": AggType,
    "use_cos": bool,
})


class TagModel(nn.Module):
    def __init__(
            self,
            *,
            agg: AggType,
            ignore_pretrained_warning: bool = False) -> None:
        super().__init__()
        logger = modeling_utils.logger
        level = logger.getEffectiveLevel()
        try:
            if ignore_pretrained_warning:
                logger.setLevel(logging.ERROR)
            self._bert = DistilBertModel.from_pretrained(
                "distilbert-base-uncased")
        finally:
            if ignore_pretrained_warning:
                logger.setLevel(level)
        self._agg = agg

    def _get_agg(self, lhs: torch.Tensor) -> torch.Tensor:
        if self._agg == AGG_CLS:
            return lhs[:, 0]
        if self._agg == AGG_MEAN:
            return torch.mean(lhs, dim=1)
        raise ValueError(f"unknown aggregation: {self._agg}")

    def _embed(
            self,
            input_ids: torch.Tensor,
            attention_mask: torch.Tensor) -> torch.Tensor:
        outputs = self._bert(
            input_ids=input_ids, attention_mask=attention_mask)
        out = self._get_agg(outputs.last_hidden_state)
        return out

    def forward(
            self,
            input_ids: torch.Tensor,
            attention_mask: torch.Tensor) -> torch.Tensor:
        return self._embed(
            input_ids=input_ids,
            attention_mask=attention_mask)


def create_model(config: ModelConfig) -> TagModel:
    return TagModel(agg=config["agg"], ignore_pretrained_warning=True)


def batch_dot(batch_a: torch.Tensor, batch_b: torch.Tensor) -> torch.Tensor:
    batch_size = batch_a.shape[0]
    return torch.bmm(
        batch_a.reshape([batch_size, 1, -1]),
        batch_b.reshape([batch_size, -1, 1])).reshape([-1, 1])


class TrainingHarness(nn.Module):
    def __init__(self, model: TagModel, use_cos: bool) -> None:
        super().__init__()
        self._model = model
        self._loss = nn.BCELoss()
        self._cos = nn.CosineSimilarity() if use_cos else None

    def _combine(
            self,
            left_embed: torch.Tensor,
            right_embed: torch.Tensor) -> torch.Tensor:
        if self._cos is None:
            # NOTE: torch.sigmoid would be a bad idea here
            return batch_dot(left_embed, right_embed)
        return self._cos(left_embed, right_embed).reshape([-1, 1])

    def get_model(self) -> TagModel:
        return self._model

    def forward(
            self,
            *,
            left_input_ids: torch.Tensor,
            left_attention_mask: torch.Tensor,
            right_input_ids: torch.Tensor,
            right_attention_mask: torch.Tensor,
            labels: torch.Tensor | None = None,
            ) -> tuple[torch.Tensor, torch.Tensor] | torch.Tensor:
        left_embed = self._model(left_input_ids, left_attention_mask)
        right_embed = self._model(right_input_ids, right_attention_mask)
        preds = self._combine(left_embed, right_embed)
        if labels is None:
            return preds
        probs = torch.hstack([1.0 - preds, preds])
        return preds, self._loss(probs, labels)


class ModelNode(Node):
    def __init__(self, kind: str, graph: Graph, node_id: NodeId) -> None:
        super().__init__(kind, graph, node_id)
        self._harness: TrainingHarness | None = None

    def do_is_pure(self, graph: Graph, queue_pool: QueuePool) -> bool:
        return True

    def get_input_format(self) -> DataFormatJSON:
        return {
            "input_ids": ("int64", [None]),
        }

    def get_output_format(self) -> dict[str, DataFormatJSON]:
        return {
            "out": {
                "embed": ("float32", [768]),
            },
        }

    def get_weight(self) -> float:
        return 1.0

    def get_load_cost(self) -> float:
        return 1.0  # TODO

    def do_load(self, roa: ReadonlyAccess) -> None:
        device = get_system_device()
        model = create_model({
            "agg": "cls",
            "use_cos": True,
        })
        harness = TrainingHarness(model, use_cos=True)
        model_fname = "mdata/v2_model_9.pkl"
        print(f"loading {model_fname}")
        with open(model_fname, "rb") as fin:
            harness.load_state_dict(
                torch.load(fin, map_location=device))
        self._harness = harness.to(device)

    def do_unload(self) -> None:
        self._harness = None

    def expected_output_meta(
            self, state: ComputeState) -> dict[str, tuple[float, int]]:
        tasks = list(state.get_inputs_tasks())
        return {
            "out": (len(tasks), ComputeTask.get_total_byte_size(tasks)),
        }

    def execute_tasks(self, state: ComputeState) -> None:
        assert self._harness is not None
        model = self._harness.get_model()
        model.eval()
        with torch.no_grad():
            inputs = state.get_values()
            input_ids_data = inputs.get_data("input_ids")
            input_ids, attention_mask = input_ids_data.get_masked()
            embeds = model(input_ids, attention_mask)
            state.push_results(
                "out",
                inputs.get_current_tasks(),
                {
                    "embed": state.create_uniform(embeds),
                })
