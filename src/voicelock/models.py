"""Core data model for voicelock.

The central primitive is :class:`VoiceProfile` — a per-account voice
fingerprint learned from the creator's own 发布历史 (published-note history).
It is a structured statistical signature, an *owned asset*, that the rewriter
conditions on and re-checks against. Everything else in this file are the small
value objects the pipeline passes around.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


# --------------------------------------------------------------------------- #
# Distributions
# --------------------------------------------------------------------------- #
@dataclass
class Dist:
    """A tiny 1-D distribution summary (mean / std / p90)."""

    mean: float = 0.0
    std: float = 0.0
    p90: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {"mean": round(self.mean, 4), "std": round(self.std, 4), "p90": round(self.p90, 4)}

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "Dist":
        d = d or {}
        return cls(
            mean=float(d.get("mean", 0.0)),
            std=float(d.get("std", 0.0)),
            p90=float(d.get("p90", 0.0)),
        )


# --------------------------------------------------------------------------- #
# Voice fingerprint
# --------------------------------------------------------------------------- #
@dataclass
class VoiceProfile:
    """The account-voice fingerprint — a learned, owned voice asset.

    Learned from the creator's own corpus of past 笔记. It is deliberately a
    *statistical* signature (not an opaque embedding) so a creator can read it,
    trust it, and version it as an asset they own.
    """

    account_id: str = "default"
    n_posts: int = 0
    n_chars: int = 0

    lexical_diversity: float = 0.0          # type-token ratio over jieba tokens
    sentence_length: Dist = field(default_factory=Dist)   # chars / sentence
    emoji_per_100_chars: float = 0.0        # emoji cadence
    exclaim_ratio: float = 0.0              # ！ per sentence
    question_ratio: float = 0.0             # ？ per sentence
    wave_ratio: float = 0.0                 # ～ per sentence
    ellipsis_ratio: float = 0.0             # …/。。。 per sentence

    opener_hooks: list[str] = field(default_factory=list)     # real opening patterns
    high_freq_tokens: list[str] = field(default_factory=list) # signature words

    signature_vec: list[float] = field(default_factory=list)  # composite for voice-distance

    version: int = 1

    # -- serialization ----------------------------------------------------- #
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sentence_length"] = self.sentence_length.to_dict()
        # keep floats compact
        for k in (
            "lexical_diversity",
            "emoji_per_100_chars",
            "exclaim_ratio",
            "question_ratio",
            "wave_ratio",
            "ellipsis_ratio",
        ):
            d[k] = round(float(d[k]), 4)
        d["signature_vec"] = [round(float(x), 5) for x in self.signature_vec]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "VoiceProfile":
        d = dict(d or {})
        d["sentence_length"] = Dist.from_dict(d.get("sentence_length"))
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        clean = {k: v for k, v in d.items() if k in known}
        return cls(**clean)


# --------------------------------------------------------------------------- #
# Slop
# --------------------------------------------------------------------------- #
@dataclass
class SlopRegion:
    """One flagged 爆款体 / homogeneity region inside a draft."""

    sentence_idx: int
    text: str
    slop_type: str          # e.g. opener_hook | emoji_cadence | homogenized_phrase | punctuation
    score: float            # 0..100 for this region
    reason: str = ""        # human-readable why-it-was-flagged
    fingerprint_delta: float = 0.0  # how far this region drifts from the account voice

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["score"] = round(float(self.score), 2)
        d["fingerprint_delta"] = round(float(self.fingerprint_delta), 4)
        return d


@dataclass
class AuditResult:
    """Result of auditing a draft: an overall slop score + the flagged regions."""

    slop_score: float                       # 0..100 overall
    regions: list[SlopRegion] = field(default_factory=list)
    voice_consistency: float | None = None  # 0..1 vs the profile (None if no profile)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slop_score": round(float(self.slop_score), 2),
            "voice_consistency": (
                None if self.voice_consistency is None else round(float(self.voice_consistency), 4)
            ),
            "regions": [r.to_dict() for r in self.regions],
        }


@dataclass
class RewriteResult:
    """End-to-end rewrite output: before/after + the score deltas."""

    before: str
    after: str
    slop_before: float
    slop_after: float
    voice_consistency_after: float | None
    iterations: int
    per_region: list[dict[str, Any]] = field(default_factory=list)
    backend: str = "mock"

    def to_dict(self) -> dict[str, Any]:
        return {
            "before": self.before,
            "after": self.after,
            "slop_before": round(float(self.slop_before), 2),
            "slop_after": round(float(self.slop_after), 2),
            "voice_consistency_after": (
                None
                if self.voice_consistency_after is None
                else round(float(self.voice_consistency_after), 4)
            ),
            "iterations": self.iterations,
            "backend": self.backend,
            "per_region": self.per_region,
        }
