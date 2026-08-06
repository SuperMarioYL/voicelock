"""Configuration + on-disk paths for voicelock.

Offline-first: nothing here reaches the network. The LLM backend is selected
purely by environment variables; with no key set, the default backend is the
offline deterministic ``mock``.
"""

from __future__ import annotations

import os
import re
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

# Safe account-id slug: rejects path separators, '..', null bytes, spaces, etc.
# so `--account "../../etc/passwd"` cannot escape the app dir via voice_path.
_ACCOUNT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def app_dir() -> Path:
    """Return the voicelock home dir (``~/.voicelock`` by default)."""
    root = os.environ.get(APP_DIR_ENV)
    base = Path(root) if root else Path.home() / ".voicelock"
    base.mkdir(parents=True, exist_ok=True)
    return base


def voice_path(account_id: str = "default") -> Path:
    """Path of the stored VoiceProfile for an account.

    ``account_id`` is validated against ``[A-Za-z0-9_-]+`` at this boundary so
    a path-traversal value (``../../etc/passwd``, slashes, null bytes, ...)
    cannot escape ``~/.voicelock`` via save/load_profile. Invalid ids raise
    ``ValueError`` with a clear message.
    """
    if not _ACCOUNT_ID_RE.match(account_id):
        raise ValueError(
            f"invalid account_id {account_id!r}: must match [A-Za-z0-9_-]+ "
            "(no path separators, '..', or null bytes)"
        )
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
      1. explicit ``prefer`` argument ('mock' | 'llm') — an explicit but
         unknown value (a typo like ``moc``, or ``foo``) raises ``ValueError``
         rather than silently falling back, so a mis-typed ``--backend`` is a
         loud config error, not a silent misconfiguration of the rewrite core.
      2. ``VOICELOCK_BACKEND`` env var
      3. presence of ``VOICELOCK_API_KEY`` → 'llm', else 'mock'

    The no-arg path (``prefer`` is None/empty — i.e. ``--backend`` omitted)
    stays on the env→key resolution so the default-offline behavior is
    unchanged. ``mock`` never requires a key and always works fully offline.
    """
    api_key = os.environ.get(API_KEY_ENV) or None
    base_url = os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL
    model = os.environ.get(MODEL_ENV) or DEFAULT_MODEL

    if prefer is not None and prefer.strip() != "":
        # an explicitly-passed --backend must name a known backend; a typo or
        # unsupported value is a hard error, not a silent fallback to mock/llm.
        kind = prefer.strip().lower()
        if kind not in {"mock", "llm"}:
            raise ValueError(
                f"unknown backend {prefer!r}: must be one of 'mock' or 'llm'"
            )
    else:
        kind = (os.environ.get(BACKEND_ENV) or "").strip().lower()
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
