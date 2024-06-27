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
import pickle
from typing import Literal, TypedDict

from llama_cpp import ChatCompletionRequestMessage, Llama, LlamaState
from scattermind.system.io import open_readb, open_reads, open_writeb

from nlpapi.default_prompts import SYSTEM_PROMPTS


Role = Literal["assistant", "user"]
FullRole = Literal["system"] | Role


ROLE_ASSISTANT: Literal["assistant"] = "assistant"
ROLE_USER: Literal["user"] = "user"
ROLE_SYSTEM: Literal["system"] = "system"


VisibleMessage = TypedDict('VisibleMessage', {
    "role": Role,
    "content": str,
})


STATE_FILE = "state.pkl"
MSGS_FILE = "msgs.json"
SYS_PROMPT_FILE = "system_prompt.txt"


def load_state(model: Llama, cache_dir: str) -> bool:
    state_file = os.path.join(cache_dir, STATE_FILE)
    if not os.path.exists(state_file):
        return False
    with open_readb(state_file) as state_in:
        llama_state: LlamaState = pickle.load(state_in)
        model.load_state(llama_state)
    return True


def save_state(model: Llama, cache_dir: str) -> None:
    state_file = os.path.join(cache_dir, STATE_FILE)
    with open_writeb(state_file) as state_out:
        llama_state: LlamaState = model.save_state()
        pickle.dump(llama_state, state_out)


def append_new_message(
        messages: list[ChatCompletionRequestMessage],
        *,
        text: str,
        role: FullRole) -> None:
    if messages:
        last_msg = messages[-1]
        if last_msg["role"] == role and last_msg["content"] == text:
            return
    msg: ChatCompletionRequestMessage
    if role == ROLE_USER:
        msg = {
            "role": ROLE_USER,
            "content": text,
        }
    elif role == ROLE_ASSISTANT:
        msg = {
            "role": ROLE_ASSISTANT,
            "content": text,
        }
    elif role == ROLE_SYSTEM:
        msg = {
            "role": ROLE_SYSTEM,
            "content": text,
        }
    else:
        raise ValueError(f"invalid {role=}")
    messages.append(msg)


def load_system_prompt(
        *,
        cache_dir: str,
        system_prompt_key: str) -> list[ChatCompletionRequestMessage]:
    sys_prompt_file = os.path.join(cache_dir, SYS_PROMPT_FILE)
    if os.path.exists(sys_prompt_file):
        with open_reads(sys_prompt_file) as sys_in:
            system_prompt: str = sys_in.read().strip()
    else:
        system_prompt = SYSTEM_PROMPTS[system_prompt_key]
    messages: list[ChatCompletionRequestMessage] = [
        {
            "role": ROLE_SYSTEM,
            "content": system_prompt,
        },
    ]
    return messages
