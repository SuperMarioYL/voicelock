"""Offline, deterministic, lexical rewrite backend — the zero-config default.

No API key, no network. It rewrites a flagged 爆款体 region by mechanically
stripping the homogenized shell (group-address openers, template phrases, emoji
studding, punctuation bombing) and gently reshaping toward the account voice.

It is intentionally simple and predictable — good enough to make the before/after
demo land offline, and a deterministic fixture the tests can rely on. The ``llm``
backend produces higher-quality rewrites when a key is configured.
"""

from __future__ import annotations

import re

from ..config import BackendConfig
from ..models import VoiceProfile
from ..voiceprint import _EMOJI_CLUSTER

# openers to drop entirely (group-address / hook templates)
_DROP_OPENERS = [
    "姐妹们", "家人们", "宝子们", "集美们", "姐妹",
    "手把手教你", "划重点", "建议收藏", "码住", "吐血整理", "纯干货",
    "谁懂", "真的会谢", "不是我说",
]

# template phrases → plainer substitutions (or removal)
_PHRASE_SUBS: list[tuple[str, str]] = [
    (r"绝绝子", "很不错"),
    (r"yyds", "很顶"),
    (r"真的绝了", "确实好"),
    (r"绝了", "挺好"),
    (r"救命", ""),
    (r"泰裤辣", "很棒"),
    (r"无限回购", "会一直买"),
    (r"闭眼入", "可以放心买"),
    (r"直接封神", "非常好"),
    (r"一整个爱住", "很喜欢"),
    (r"人手一个", "推荐一个"),
    (r"错过血亏", "值得看看"),
    (r"我真的会哭", "挺打动我的"),
    (r"我真的会谢", ""),
    (r"谁不爱[呢啊]?", "我挺喜欢的"),
    (r"谁懂[啊呀]?", "说真的"),
    (r"啊啊啊+", ""),
]


class MockBackend:
    """The offline lexical rewriter."""

    name = "mock"

    def __init__(self, cfg: BackendConfig | None = None) -> None:
        self.cfg = cfg

    # -- interface --------------------------------------------------------- #
    def rewrite_region(self, text: str, profile: VoiceProfile | None = None) -> str:
        """Rewrite a flagged region in the account voice.

        May return an empty string when the region was a pure 爆款体 shell (e.g.
        a bare ``姐妹们！！！`` group-address hook) that carries no real content —
        the rewriter drops such regions entirely, which is the correct 去AI味 move.
        """
        out = text

        # 1. drop group-address / hook openers at the head (incl. trailing bombing
        #    and the dangling particle 啊/呀/哦 that often trails them)
        for op in _DROP_OPENERS:
            out = re.sub(rf"^{re.escape(op)}[啊呀哦呢吧，,、。\s!！?？~～…]*", "", out)
        # a second pass catches a stacked opener like 谁懂啊家人们 → drop 家人们 too
        for op in _DROP_OPENERS:
            out = re.sub(rf"^{re.escape(op)}[啊呀哦呢吧，,、。\s!！?？~～…]*", "", out)

        # 2. substitute / remove template phrases
        for pat, repl in _PHRASE_SUBS:
            out = re.sub(pat, repl, out)

        # 3. de-bomb punctuation: !!! -> 。, ??? -> ？
        out = re.sub(r"[!！]{2,}", "。", out)
        out = re.sub(r"[?？]{2,}", "？", out)
        out = re.sub(r"[~～]{2,}", "", out)

        # 4. thin out emoji studding toward the account's cadence
        out = self._thin_emoji(out, profile)

        # 5. tidy whitespace / dangling separators
        out = re.sub(r"\s{2,}", " ", out).strip()
        out = re.sub(r"^[，,。、\s]+", "", out)
        out = re.sub(r"[，,、]\s*$", "。", out)

        # if nothing but shell remained, the region is pure slop → drop it
        residual = _EMOJI_CLUSTER.sub("", out)
        residual = re.sub(r"[。！？!?…～~，,、\s]", "", residual)
        if not residual:
            return ""

        # ensure it ends on a terminator so sentence-splitting stays sane
        if out and out[-1] not in "。！？!?…":
            out += "。"
        return out

    # -- helpers ----------------------------------------------------------- #
    def _thin_emoji(self, text: str, profile: VoiceProfile | None) -> str:
        """Reduce emoji to roughly the account cadence (default: at most one cluster).

        A ZWJ-joined sequence (👨‍👩‍👧‍👦) is one logical emoji, so a whole cluster is
        kept or dropped as a single unit — iterating per codepoint would keep
        only the first pictograph plus the dangling U+200D joiners and drop the
        other members, leaving orphaned ZWJ control chars mangled into the
        rewritten 正文 (e.g. ``👨\\u200d\\u200d\\u200d``). Gap text between
        clusters is preserved verbatim.
        """
        target = 1
        if profile is not None:
            chars = max(1, len(re.sub(r"\s+", "", text)))
            allowed = round(profile.emoji_per_100_chars / 100.0 * chars)
            target = max(0, min(2, allowed))

        kept = 0
        out: list[str] = []
        last = 0
        for m in _EMOJI_CLUSTER.finditer(text):
            out.append(text[last:m.start()])  # preserve gap text between clusters
            if kept < target:
                out.append(m.group())
                kept += 1
            last = m.end()
        out.append(text[last:])
        return "".join(out)
