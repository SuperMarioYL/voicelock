"""Rewrite backends.

Two backends share one interface (``rewrite_region(text, profile) -> str``):

* ``mock``  — offline, deterministic, lexical. No API key. The zero-config default.
* ``llm``   — OpenAI-compatible 国产模型 (qwen / doubao / kimi / glm) via base_url + key.
"""

from __future__ import annotations

from ..config import BackendConfig
from .mock import MockBackend


def get_backend(cfg: BackendConfig):
    """Return an instantiated backend for the resolved config."""
    if cfg.is_llm:
        from .llm import LLMBackend  # imported lazily so mock never needs openai at runtime

        return LLMBackend(cfg)
    return MockBackend(cfg)


__all__ = ["get_backend", "MockBackend"]
