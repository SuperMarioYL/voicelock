"""OpenAI-compatible 国产模型 rewrite backend (qwen / doubao / kimi / glm).

Selected only when ``VOICELOCK_API_KEY`` is set. Uses the ``openai`` SDK against
a configurable ``base_url`` so any OpenAI-compatible endpoint works:

    export VOICELOCK_API_KEY=sk-...
    export VOICELOCK_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
    export VOICELOCK_MODEL=qwen-plus

If a call fails for any reason it fails soft — returning the original region text
unchanged — so a flaky network never crashes the rewrite loop. The CLI still
prefers the offline ``mock`` backend by default (no key needed).
"""

from __future__ import annotations

from ..config import BackendConfig
from ..models import VoiceProfile
from ..prompts import SYSTEM_PROMPT, build_rewrite_prompt


class LLMBackend:
    """Rewrite via an OpenAI-compatible chat completion endpoint."""

    name = "llm"

    def __init__(self, cfg: BackendConfig) -> None:
        self.cfg = cfg
        self._client = None  # lazily constructed on first use

    def _client_or_none(self):
        if self._client is not None:
            return self._client
        if not self.cfg.api_key:
            return None
        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.cfg.api_key, base_url=self.cfg.base_url)
        except Exception:
            self._client = None
        return self._client

    def rewrite_region(self, text: str, profile: VoiceProfile | None = None) -> str:
        client = self._client_or_none()
        if client is None:
            return text  # fail soft — no usable client

        try:
            resp = client.chat.completions.create(
                model=self.cfg.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_rewrite_prompt(text, profile)},
                ],
                temperature=0.7,
                max_tokens=256,
            )
            out = (resp.choices[0].message.content or "").strip()
        except Exception:
            return text  # fail soft — keep the loop alive offline/on error

        # strip stray quoting the model sometimes adds
        out = out.strip().strip("「」“”\"'`").strip()
        return out or text
