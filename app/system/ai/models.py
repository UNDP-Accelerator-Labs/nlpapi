import logging
from collections.abc import Callable
from typing import Any, cast, Literal, TypedDict

import numpy as np
import torch
from torch import nn

# FIXME: add transformer stubs
from transformers import (  # type: ignore
    DistilBertModel,
    DistilBertTokenizer,
    modeling_utils,
)

from app.misc.lru import LRU
from app.misc.util import progress


DEFAULT_BATCH_SIZE_EVAL = 16
DEFAULT_BATCH_SIZE_TRAIN = 4


TokenizedInput = TypedDict('TokenizedInput', {
    "text": list[str] | None,
    "input_ids": torch.Tensor,
    "attention_mask": torch.Tensor,
})


Tokenizer = Callable[[list[str], bool], TokenizedInput]


AggType = Literal["cls", "mean"]
AGG_CLS: AggType = "cls"
AGG_MEAN: AggType = "mean"


ModelConfig = TypedDict('ModelConfig', {
    "agg": AggType,
    "use_cos": bool,
})


def batch_dot(batch_a: torch.Tensor, batch_b: torch.Tensor) -> torch.Tensor:
    batch_size = batch_a.shape[0]
    return torch.bmm(
        batch_a.reshape([batch_size, 1, -1]),
        batch_b.reshape([batch_size, -1, 1])).reshape([-1, 1])


def get_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def get_tokenizer() -> Tokenizer:
    tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")
    device = get_device()

    def tokens(texts: list[str], preserve_text: bool) -> TokenizedInput:
        res = tokenizer(
            texts, return_tensors="pt", padding=True, truncation=True)
        obj = {k: v.to(device) for k, v in res.items()}
        obj["text"] = texts if preserve_text else None
        return cast(TokenizedInput, obj)

    return tokens


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
        self._test_lru: LRU[str, torch.Tensor] | None = None

        def cache_hook(*_args: Any, **_kwargs: Any) -> None:
            self.clear_cache()

        self.register_load_state_dict_post_hook(cache_hook)
        self.register_state_dict_pre_hook(cache_hook)

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

    def clear_cache(self) -> None:
        self._test_lru = None

    def forward(
            self,
            x: TokenizedInput) -> torch.Tensor:
        if self.training and self._test_lru is not None:
            self.clear_cache()
        if not self.training:
            if self._test_lru is None:
                self._test_lru = LRU(1000)
            if x["text"] is not None:
                res = []
                for row_ix, text in enumerate(x["text"]):
                    cache_res = self._test_lru.get(text)
                    if cache_res is None:
                        cache_res = self._embed(
                            input_ids=x["input_ids"][[row_ix]],
                            attention_mask=x["attention_mask"][[row_ix]],
                            ).detach()
                        self._test_lru.set(text, cache_res)
                    res.append(torch.clone(cache_res))
                return torch.vstack(res)
        return self._embed(
            input_ids=x["input_ids"],
            attention_mask=x["attention_mask"])


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
            left: TokenizedInput,
            right: TokenizedInput,
            labels: torch.Tensor | None = None,
            ) -> tuple[torch.Tensor, torch.Tensor] | torch.Tensor:
        left_embed = self._model(left)
        right_embed = self._model(right)
        preds = self._combine(left_embed, right_embed)
        if labels is None:
            return preds
        probs = torch.hstack([1.0 - preds, preds])
        return preds, self._loss(probs, labels)


def create_model(config: ModelConfig) -> TagModel:
    return TagModel(agg=config["agg"], ignore_pretrained_warning=True)


def load_model(
        harness: TrainingHarness,
        model_fname: str,
        device: torch.device) -> None:
    print(f"loading {model_fname}")
    with open(model_fname, "rb") as fin:
        harness.load_state_dict(torch.load(fin, map_location=device))


def get_embeds(
        texts: list[str],
        harness: TrainingHarness,
        tokens: Tokenizer,
        *,
        embeds: list[np.ndarray],
        progress_bar: bool) -> None:
    batch_size = DEFAULT_BATCH_SIZE_EVAL
    model = harness.get_model()
    model.eval()
    with torch.no_grad():
        with progress(
                desc="embed", total=len(texts), show=progress_bar) as pbar:
            for chunk_ix in range(0, len(texts), batch_size):
                chunk = texts[chunk_ix:chunk_ix + batch_size]
                if not chunk:
                    continue
                embed = model(tokens(chunk, False))
                embeds.append(embed.numpy(force=True))

                pbar(len(chunk))
