# FIXME: the types are there, though...
import huggingface_hub  # type: ignore
from sentence_transformers import SentenceTransformer  # type: ignore


def get_sentence_transformer(
        model_name: str, cache_dir: str) -> SentenceTransformer:
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
