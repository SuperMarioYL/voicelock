"""爆款体 / homogeneity slop detector (milestone m2).

A lexical rule-set for the homogenized hooks, openers, emoji cadence and
template phrases that 小红书 surfaces penalize. Given a draft it flags
sentence-level slop regions and computes a 0..100 slop score. When a
:class:`VoiceProfile` is supplied, each region's drift from the account voice
(``fingerprint_delta``) reinforces the score.

Everything here is offline and deterministic — the same draft always produces
the same regions and score.
"""

from __future__ import annotations

import re

from .models import AuditResult, SlopRegion, VoiceProfile
from .voiceprint import (
    count_emoji,
    split_sentences,
    voice_consistency,
    voice_distance,
)

# --------------------------------------------------------------------------- #
# Rule library — the homogenized 爆款体 surfaces
# --------------------------------------------------------------------------- #

# Opener-hook templates: the "一眼AI" openings the feed is saturated with.
_OPENER_HOOKS: list[tuple[str, str]] = [
    (r"^姐妹们", "群呼开头（姐妹们）"),
    (r"^家人们", "群呼开头（家人们）"),
    (r"^宝子们", "群呼开头（宝子们）"),
    (r"^集美们", "群呼开头（集美们）"),
    (r"^谁懂", "谁懂系列开头"),
    (r"^真的会谢", "网络烂梗开头"),
    (r"^不是我说", "不是我说系列"),
    (r"^救命", "夸张感叹开头（救命）"),
    (r"^绝了", "夸张感叹开头（绝了）"),
    (r"^手把手教你", "手把手教你套路"),
    (r"^划重点", "划重点套路"),
    (r"^建议收藏", "建议收藏套路"),
    (r"^码住", "码住套路"),
    (r"^吐血整理", "吐血整理套路"),
    (r"^纯干货", "纯干货套路"),
]

# Homogenized template phrases sprinkled through 爆款体 bodies.
_TEMPLATE_PHRASES: list[tuple[str, str]] = [
    (r"绝绝子", "烂大街词（绝绝子）"),
    (r"yyds", "烂大街词（yyds）"),
    (r"谁不爱", "反问套路（谁不爱）"),
    (r"谁懂啊?", "谁懂套路"),
    (r"我真的会哭", "会哭套路"),
    (r"真的绝了", "真的绝了套路"),
    (r"无限回购", "无限回购套路"),
    (r"闭眼入", "闭眼入套路"),
    (r"人手一个", "人手一个套路"),
    (r"错过血亏", "错过血亏套路"),
    (r"一整个爱住", "一整个X住句式"),
    (r"直接封神", "直接封神套路"),
    (r"泰裤辣", "网络烂梗（泰裤辣）"),
    (r"啊啊啊+", "情绪拉满（啊啊啊）"),
    (r"[!！]{2,}", "感叹号轰炸"),
    (r"\?{2,}|？{2,}", "问号轰炸"),
    (r"(?:干货|收藏|码住|抄作业){1}.{0,4}(?:合集|清单|攻略)", "干货合集套路"),
]

# emoji cadence: 小红书 爆款体 tends to over-stud each line with emoji.
_EMOJI_PER_SENT_SOFT = 2.0    # start penalizing above this
_EMOJI_PER_SENT_HARD = 4.0    # saturated at this

# Sentence-length regularity: 爆款体 lines are relentlessly short + uniform.
_SHORT_SENT_CHARS = 10

_COMPILED_OPENERS = [(re.compile(p), why) for p, why in _OPENER_HOOKS]
_COMPILED_PHRASES = [(re.compile(p), why) for p, why in _TEMPLATE_PHRASES]


def _region_score(reasons: list[str], emoji_n: int, sent_len: int) -> float:
    """Combine per-sentence signals into a 0..100 region score."""
    score = 0.0
    # opener/template hits are the strongest 爆款体 signal
    score += 42.0 * min(2, sum(1 for r in reasons if not r.startswith("emoji")))
    # emoji cadence
    if emoji_n >= _EMOJI_PER_SENT_HARD:
        score += 28.0
    elif emoji_n >= _EMOJI_PER_SENT_SOFT:
        score += 16.0
    # ultra-short punchy line (template rhythm)
    if 0 < sent_len <= _SHORT_SENT_CHARS and reasons:
        score += 10.0
    return min(100.0, score)


def detect(text: str, profile: VoiceProfile | None = None) -> AuditResult:
    """Detect 爆款体 slop regions in a draft.

    Returns an :class:`AuditResult` with an overall 0..100 slop score, the
    flagged sentence regions, and (if a profile is given) the voice-consistency.
    """
    sentences = split_sentences(text)
    regions: list[SlopRegion] = []

    for idx, sent in enumerate(sentences):
        reasons: list[str] = []
        slop_types: list[str] = []

        # opener hooks (only meaningful at the head of the sentence)
        for rx, why in _COMPILED_OPENERS:
            if rx.search(sent):
                reasons.append(why)
                slop_types.append("opener_hook")
                break

        # template phrases anywhere in the sentence
        for rx, why in _COMPILED_PHRASES:
            if rx.search(sent):
                reasons.append(why)
                slop_types.append("homogenized_phrase")

        emoji_n = count_emoji(sent)
        if emoji_n >= _EMOJI_PER_SENT_SOFT:
            reasons.append(f"emoji 堆叠 ×{emoji_n}")
            slop_types.append("emoji_cadence")

        if not reasons:
            continue

        sent_len = len(re.sub(r"\s+", "", sent))
        r_score = _region_score(reasons, emoji_n, sent_len)

        # fingerprint drift reinforces the score (region that also sounds
        # nothing like the account voice is more likely genuine slop)
        fp_delta = 0.0
        if profile is not None:
            fp_delta = voice_distance(profile, sent)
            r_score = min(100.0, r_score + 20.0 * fp_delta)

        slop_type = _dominant(slop_types)
        regions.append(
            SlopRegion(
                sentence_idx=idx,
                text=sent,
                slop_type=slop_type,
                score=r_score,
                reason="；".join(reasons),
                fingerprint_delta=fp_delta,
            )
        )

    slop_score = _aggregate_score(regions, len(sentences))
    vc = voice_consistency(profile, text) if profile is not None else None
    return AuditResult(slop_score=slop_score, regions=regions, voice_consistency=vc)


def slop_score(text: str, profile: VoiceProfile | None = None) -> float:
    """Convenience wrapper: just the 0..100 overall slop score."""
    return detect(text, profile).slop_score


def _dominant(slop_types: list[str]) -> str:
    if not slop_types:
        return "homogenized_phrase"
    # opener_hook is the most salient label when present
    order = ["opener_hook", "homogenized_phrase", "emoji_cadence"]
    for t in order:
        if t in slop_types:
            return t
    return slop_types[0]


def _aggregate_score(regions: list[SlopRegion], n_sentences: int) -> float:
    """Aggregate region scores into a document-level 0..100 slop score.

    Blends coverage (how much of the draft is flagged) with intensity (how bad
    the flagged bits are) so a short all-爆款体 draft and a long mostly-clean one
    both land where a creator would expect.
    """
    if not regions or n_sentences <= 0:
        return 0.0
    coverage = len(regions) / n_sentences               # 0..1
    intensity = sum(r.score for r in regions) / (len(regions) * 100.0)  # 0..1
    # weight intensity higher; coverage stops one flagged line from maxing it
    raw = 100.0 * (0.35 * coverage + 0.65 * intensity)
    # a draft with several flagged regions should read clearly "high slop"
    boost = min(15.0, 3.0 * len(regions))
    return round(min(100.0, raw + boost), 2)
