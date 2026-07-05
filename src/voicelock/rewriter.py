"""In-voice rewrite loop (milestone m3).

The regenerate-slop-region loop: detect 爆款体 regions → regenerate each flagged
sentence *in the account voice* via the selected backend → re-check the rewritten
region → keep the best of the two → recompute the document slop score and
voice-consistency. Returns a :class:`RewriteResult` carrying before/after and the
score deltas the demo shows.
"""

from __future__ import annotations

from .backends import get_backend
from .config import BackendConfig, resolve_backend
from .models import RewriteResult, VoiceProfile
from .slop_detector import detect
from .voiceprint import split_sentences, voice_consistency


def rewrite(
    text: str,
    profile: VoiceProfile | None = None,
    backend_cfg: BackendConfig | None = None,
    max_iters: int = 2,
) -> RewriteResult:
    """Run the regenerate-slop-region loop over ``text``.

    Args:
        text: the AI-generated draft.
        profile: the account-voice fingerprint to rewrite toward (optional).
        backend_cfg: which backend to use; resolved from env if omitted.
        max_iters: max regenerate attempts per flagged region (re-check loop).
    """
    cfg = backend_cfg or resolve_backend()
    backend = get_backend(cfg)

    audit = detect(text, profile)
    slop_before = audit.slop_score

    sentences = split_sentences(text)
    # map sentence_idx -> rewritten sentence
    rewritten: dict[int, str] = {}
    per_region: list[dict] = []

    for region in audit.regions:
        original = region.text
        best = original
        best_score = region.score
        iters = 0

        for _ in range(max(1, max_iters)):
            iters += 1
            candidate = backend.rewrite_region(best, profile)
            if candidate == best:
                break  # backend made no further change (e.g. llm fail-soft)
            if candidate == "":
                # region was a pure 爆款体 shell — dropping it scores as clean
                best, best_score = "", 0.0
                break
            cand_regions = detect(candidate, profile).regions
            cand_score = max((r.score for r in cand_regions), default=0.0)
            if cand_score < best_score:
                best, best_score = candidate, cand_score
            if best_score <= 5.0:
                break  # clean enough, stop early

        if best != original:
            rewritten[region.sentence_idx] = best
        per_region.append(
            {
                "sentence_idx": region.sentence_idx,
                "slop_type": region.slop_type,
                "before": original,
                "after": best,
                "region_slop_before": round(region.score, 2),
                "region_slop_after": round(best_score, 2),
                "iterations": iters,
            }
        )

    after = _reassemble(sentences, rewritten)

    audit_after = detect(after, profile)
    slop_after = audit_after.slop_score
    vc_after = voice_consistency(profile, after) if profile is not None else None

    return RewriteResult(
        before=text.strip(),
        after=after,
        slop_before=slop_before,
        slop_after=slop_after,
        voice_consistency_after=vc_after,
        iterations=sum(r["iterations"] for r in per_region),
        per_region=per_region,
        backend=backend.name,
    )


def _reassemble(sentences: list[str], rewritten: dict[int, str]) -> str:
    """Rebuild the draft, swapping in rewritten sentences by index."""
    out: list[str] = []
    for i, s in enumerate(sentences):
        out.append(rewritten.get(i, s))
    # sentences already carry their own terminators from split; join tightly
    return "".join(out).strip()
