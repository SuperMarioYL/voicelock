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
         An explicit ``llm`` with no ``VOICELOCK_API_KEY`` configured likewise
         raises ``ValueError`` rather than silently flipping to mock — a valid
         backend must not silently become its opposite. The no-arg/no-env
         auto-select path below is untouched, so default-offline stays mock.
      2. ``VOICELOCK_BACKEND`` env var — an invalid non-empty value (a typo
         like ``moc``) raises ``ValueError`` mirroring the explicit-arg path;
         a non-empty ``llm`` with no key raises the same way; an empty/unset
         value falls through to the key-based default so the default-offline
         behavior is unchanged.
      3. presence of ``VOICELOCK_API_KEY`` → 'llm', else 'mock'

    The no-arg path (``prefer`` is None/empty — i.e. ``--backend`` omitted)
    stays on the env→key resolution so the default-offline behavior is
    unchanged. ``mock`` never requires a key and always works fully offline.
    """
    api_key = os.environ.get(API_KEY_ENV) or None
    base_url = os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL
    model = os.environ.get(MODEL_ENV) or DEFAULT_MODEL

    # True when the backend was named explicitly (a non-empty --backend or a
    # non-empty VOICELOCK_BACKEND). The auto-select path (no prefer, empty/unset
    # env) never sets this, so the llm-no-key raise below cannot fire there and
    # default-offline behavior is unchanged.
    explicit = False

    if prefer is not None and prefer.strip() != "":
        # an explicitly-passed --backend must name a known backend; a typo or
        # unsupported value is a hard error, not a silent fallback to mock/llm.
        kind = prefer.strip().lower()
        if kind not in {"mock", "llm"}:
            raise ValueError(
                f"unknown backend {prefer!r}: must be one of 'mock' or 'llm'"
            )
        explicit = True
    else:
        kind = (os.environ.get(BACKEND_ENV) or "").strip().lower()
        # VOICELOCK_BACKEND is a documented "force a backend" env var, so a
        # non-empty but invalid value (a typo like `moc`, or `qwen`) must be a
        # loud error — mirroring the explicit --backend path — NOT a silent
        # flip to the opposite backend when a key happens to be set. An
        # empty/unset value still falls through to the key-based default so the
        # default-offline behavior is unchanged.
        if kind and kind not in {"mock", "llm"}:
            raise ValueError(
                f"unknown VOICELOCK_BACKEND {kind!r}: must be one of 'mock' or 'llm'"
            )
        if not kind:
            kind = "llm" if api_key else "mock"
        else:
            explicit = True

    if kind == "llm" and not api_key:
        # An EXPLICIT request for the llm backend with no key is the same
        # silent-misconfiguration-of-the-core-rewrite-backend class the
        # v0.3.0/v0.5.0 fixes made loud for unknown values — a valid backend
        # must not silently flip to its opposite, so a user who explicitly
        # asks for LLM rewrites does not silently get mock-quality output.
        # Raise (caught by cli._clean_user_errors → clean red message + exit 1)
        # naming the missing key. The auto-select path (kind = llm-if-key-else-
        # mock) sets mock directly when no key is present and never reaches
        # here, so default-offline behavior is unchanged.
        if explicit:
            raise ValueError(
                f"backend 'llm' requested but {API_KEY_ENV} is not set"
            )
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
