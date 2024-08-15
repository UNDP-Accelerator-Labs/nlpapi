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
"""Utilities for downloading huggingface models."""
# FIXME: the types are there, though...
import huggingface_hub  # type: ignore
from sentence_transformers import SentenceTransformer  # type: ignore


def get_sentence_transformer(
        model_name: str, cache_dir: str) -> SentenceTransformer:
    """
    Loads a sentence transformer model.

    Args:
        model_name (str): The model name.
        cache_dir (str): The cache dir.

    Returns:
        SentenceTransformer: The model.
    """
    if "/" in model_name:
        hname = model_name
    else:
        hname = f"sentence-transformers/{model_name}"

    # FIXME: hack to download subfolder files
    huggingface_hub.hf_hub_download(
        hname,
        "config.json",
        subfolder="1_Pooling",
        cache_dir=cache_dir)

    return SentenceTransformer(model_name, cache_folder=cache_dir)
