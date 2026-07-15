from __future__ import annotations

import os

from langchain_ollama import ChatOllama


DEFAULT_OLLAMA_MODEL = "llama3.2"


def build_ollama_chat_model(
    model: str | None = None,
    temperature: float = 0.0,
    validate_model_on_init: bool = False,
) -> ChatOllama:
    """
    Build a deterministic Ollama-backed chat model for downstream MEDAGENT-X agents.

    The Quality Gate Agent should remain rule-based and should not call this model.
    This helper exists for later agents such as Retrieval, Disease Reasoning, and Judge.
    """
    selected_model = model or os.getenv("MEDAGENT_X_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)

    return ChatOllama(
        model=selected_model,
        temperature=temperature,
        validate_model_on_init=validate_model_on_init,
    )