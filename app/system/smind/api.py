import json
import os
import re
import time
import unicodedata
from collections.abc import Iterable
from html import unescape
from typing import cast, TypeVar

from gemma import tokenizer
from scattermind.api.api import ScattermindAPI
from scattermind.api.loader import load_api
from scattermind.system.base import TaskId
from scattermind.system.names import GNamespace
from scattermind.system.torch_util import tensor_to_str


T = TypeVar('T')


def load_smind(config_fname: str) -> ScattermindAPI:
    with open(config_fname, "rb") as fin:
        config_obj = json.load(fin)
    return load_api(config_obj)


def load_graph(
        smind: ScattermindAPI,
        graph_fname: str) -> tuple[GNamespace, str, str]:
    with open(graph_fname, "rb") as fin:
        graph_def_obj = json.load(fin)
    ns = smind.load_graph(graph_def_obj)
    inputs = list(smind.main_inputs(ns))
    outputs = list(smind.main_outputs(ns))
    if len(inputs) != 1:
        raise ValueError(f"invalid graph inputs: {inputs}")
    if len(outputs) != 1:
        raise ValueError(f"invalid graph outputs: {outputs}")
    return ns, inputs[0], outputs[0]


GEMMA_FOLDER = "study/mdata/gemma2b/"


def get_token_count(prompts: list[str]) -> list[int]:
    start_time = time.monotonic()
    token_fn = tokenizer.Tokenizer(
        os.path.join(GEMMA_FOLDER, "tokenizer.model"))
    prompt_tokens = [token_fn.encode(prompt) for prompt in prompts]
    res = [len(p) for p in prompt_tokens]
    duration = time.monotonic() - start_time
    print(f"tokenization time: {duration}s")
    return res


def clean(text: str) -> str:
    text = text.strip()
    while True:
        prev_text = text
        text = unescape(text)
        if prev_text == text:
            break
    text = unicodedata.normalize("NFKC", text)
    text = re.sub("\r", "\n", text)
    text = re.sub("\n\n+", "\n", text)
    text = re.sub("\n[ \t]+", "\n", text)
    text = re.sub("[ \t]+", " ", text)
    text = re.sub("\n\n\n+", "\n\n", text)
    return text


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?\s*>", "\n", text.strip())
    text = re.sub(r"<(?:\"[^\"]*\"['\"]*|'[^']*'['\"]*|[^'\">])+>", "", text)
    return text


def normalize_text(text: str) -> str:
    return clean(strip_html(text))


def snippify_text(text: str, chunk_size: int) -> Iterable[str]:
    pos = 0
    content = text.strip()
    while pos < len(content):
        cur = content[pos:pos + chunk_size].strip()
        if len(cur) < chunk_size:
            if cur:
                yield cur
            break
        rpos = cur.rfind(" ")
        if rpos > 0:
            small = cur[0:rpos].strip()
            if small:
                yield small
            spos = small.rfind(" ")
            if spos > 0:
                pos += spos
            else:
                pos += len(small)
        else:
            yield cur
            pos += len(cur)


def get_text_results_immediate(
        texts: list[str],
        *,
        smind: ScattermindAPI,
        ns: GNamespace,
        input_field: str,
        output_field: str,
        output_sample: T) -> list[T | None]:
    lookup: dict[TaskId, int] = {}
    for ix, text in enumerate(texts):
        task_id = smind.enqueue_task(
            ns,
            {
                input_field: text,
            })
        lookup[task_id] = ix
    res: dict[int, T] = {}
    for tid, resp in smind.wait_for(list(lookup.keys()), timeout=None):
        if resp["error"] is not None:
            error = resp["error"]
            print(f"{error['code']} ({error['ctx']}): {error['message']}")
            print("\n".join(error["traceback"]))
        result = resp["result"]
        if result is not None:
            if output_field in ("text", "tags"):
                output: T = cast(T, tensor_to_str(result[output_field]))
            else:
                output = cast(T, list(result[output_field].cpu().tolist()))
            if not isinstance(output, type(output_sample)):
                raise ValueError(
                    "output does not match sample. "
                    f"output={output} sample={output_sample} "
                    f"{type(output)}<:{type(output_sample)}")
            curix = lookup[tid]
            res[curix] = output
    return [res.get(ix, None) for ix in range(len(texts))]
