"""Comparison modes for user evaluation: a model, one instruction, nothing else.

The product's own path (``TriageAgent``) retrieves passages, lets the base
model decide inside ``TriageDecision``, and checks the result. The two modes
here exist so evaluators can set that path beside its alternatives:

- **Model A**: the unadapted base model, reached through OpenRouter.
- **Model B**: the fine-tuned adapter on the local vLLM server.

Both get the same fixed system instruction and the conversation so far. They
get no retrieved passages, no warning-sign rules and no knowledge base, and
nothing they say is checked, cited or given an urgency level. Their replies
are a measurement, not guidance; the route labels them as such in what it
stores. **Model C** is the product's own path and is not built here.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import openai
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from herhealth_backend.triage.agent import Message
from herhealth_backend.triage.chain import ReasoningUnavailable, _invoke
from herhealth_backend.triage.language import detect_language

__all__ = [
    "COMPARISON_INSTRUCTION",
    "COMPARISON_MAX_TOKENS",
    "COMPARISON_TIMEOUT_SECONDS",
    "MODEL_A",
    "MODEL_B",
    "MODEL_C",
    "MODEL_LABELS",
    "OPENROUTER_URL",
    "PlainChatResponder",
    "build_openrouter_chat_model",
]

MODEL_A = "model_a"
MODEL_B = "model_b"
MODEL_C = "model_c"

#: What an evaluator sees. Deliberately says nothing about what each one is,
#: so a preference between them is not a preference between descriptions.
MODEL_LABELS = {MODEL_A: "Model A", MODEL_B: "Model B", MODEL_C: "Model C"}

#: The instruction every row of the adapter's training corpus carried, word
#: for word (see CLAUDE.md, "The fine-tuned model"). Model B is therefore
#: asked exactly what it was trained to do, and Model A is asked the same.
COMPARISON_INSTRUCTION = (
    "You are a supportive women's-health information assistant. Answer the "
    "patient's question clearly and safely, and recommend seeing a clinician "
    "for diagnosis or treatment decisions."
)

COMPARISON_MAX_TOKENS = 900
#: One call, no retry, so it may use most of the route's 150 s turn budget.
#: A free answer from the adapter took 22 s and 32 s in two live calls and
#: ran past the 50 s per-call limit of the product's own path in a third.
COMPARISON_TIMEOUT_SECONDS = 120.0

OPENROUTER_URL = "https://openrouter.ai/api/v1"

_THINKING = re.compile(r"<think>.*?</think>", re.DOTALL)


def build_openrouter_chat_model(*, model: str, api_key: str) -> Any:
    """The base model through OpenRouter, for Model A only."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        base_url=OPENROUTER_URL,
        api_key=api_key,
        temperature=0,
        max_tokens=COMPARISON_MAX_TOKENS,
        timeout=COMPARISON_TIMEOUT_SECONDS,
        max_retries=0,
        # The same choice as the local server: no thinking block.
        extra_body={"reasoning": {"enabled": False}},
    )


@dataclass(frozen=True)
class PlainChatResponder:
    """One model answering the conversation under the fixed instruction."""

    chat: Any
    name: str

    def reply(self, history: Sequence[Message]) -> str:
        # The one addition to the fixed instruction: the language to answer in,
        # the same line of reasoning the product's own path applies.
        language = detect_language(m.content for m in history if m.role == "user")
        instruction = COMPARISON_INSTRUCTION
        if language is not None:
            instruction = f"{instruction} She is writing in {language}; answer in {language}."
        messages: list[BaseMessage] = [SystemMessage(content=instruction)]
        for message in history:
            kind = AIMessage if message.role == "assistant" else HumanMessage
            messages.append(kind(content=message.content))
        try:
            text = _invoke(self.chat, messages, what="comparison")
        except openai.APITimeoutError as error:
            raise ReasoningUnavailable(f"{self.name} did not answer in time") from error
        if not isinstance(text, str):
            raise ReasoningUnavailable(f"{self.name} returned no text")
        text = _THINKING.sub("", text).strip()
        if not text:
            raise ReasoningUnavailable(f"{self.name} returned an empty reply")
        return text
