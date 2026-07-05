"""Configuration + on-disk paths for voicelock.

Offline-first: nothing here reaches the network. The LLM backend is selected
purely by environment variables; with no key set, the default backend is the
offline deterministic ``mock``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

APP_DIR_ENV = "VOICELOCK_HOME"
API_KEY_ENV = "VOICELOCK_API_KEY"
BASE_URL_ENV = "VOICELOCK_BASE_URL"
MODEL_ENV = "VOICELOCK_MODEL"
BACKEND_ENV = "VOICELOCK_BACKEND"

DEFAULT_MODEL = "qwen-plus"
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def app_dir() -> Path:
    """Return the voicelock home dir (``~/.voicelock`` by default)."""
    root = os.environ.get(APP_DIR_ENV)
    base = Path(root) if root else Path.home() / ".voicelock"
    base.mkdir(parents=True, exist_ok=True)
    return base


def voice_path(account_id: str = "default") -> Path:
    """Path of the stored VoiceProfile for an account."""
    if account_id == "default":
        return app_dir() / "voice.yaml"
    return app_dir() / f"voice.{account_id}.yaml"


def config_path() -> Path:
    return app_dir() / "config.yaml"


@dataclass
class BackendConfig:
    """Resolved backend selection.

    ``kind`` is 'mock' (offline, deterministic, zero-config) or 'llm'
    (OpenAI-compatible 国产模型 via base_url + key).
    """

    kind: str = "mock"
    api_key: str | None = None
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL

    @property
    def is_llm(self) -> bool:
        return self.kind == "llm"


def resolve_backend(prefer: str | None = None) -> BackendConfig:
    """Resolve which backend to use.

    Precedence:
      1. explicit ``prefer`` argument ('mock' | 'llm')
      2. ``VOICELOCK_BACKEND`` env var
      3. presence of ``VOICELOCK_API_KEY`` → 'llm', else 'mock'

    ``mock`` never requires a key and always works fully offline.
    """
    api_key = os.environ.get(API_KEY_ENV) or None
    base_url = os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL
    model = os.environ.get(MODEL_ENV) or DEFAULT_MODEL

    kind = (prefer or os.environ.get(BACKEND_ENV) or "").strip().lower()
    if kind not in {"mock", "llm"}:
        kind = "llm" if api_key else "mock"

    if kind == "llm" and not api_key:
        # asked for llm but no key — fall back to offline mock rather than crash
        kind = "mock"

    return BackendConfig(kind=kind, api_key=api_key, base_url=base_url, model=model)


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        return {}
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def save_config(data: dict) -> Path:
    p = config_path()
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p
