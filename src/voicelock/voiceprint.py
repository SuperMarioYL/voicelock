"""Voice fingerprint — build a :class:`VoiceProfile` from a corpus and score any
draft against it.

The fingerprint is deliberately deterministic and offline: the same corpus
always yields the same profile, and scoring never touches the network. This is
the ``m1`` milestone — a creator builds their owned voice asset and can score
any draft against it with zero API key.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

import jieba
import yaml

from .models import Dist, VoiceProfile

# jieba prints an initialization banner to stderr on first cut; silence it so
# CLI output stays clean and deterministic.
jieba.setLogLevel(60)

# --------------------------------------------------------------------------- #
# Text primitives (shared by voiceprint + slop_detector)
# --------------------------------------------------------------------------- #
# Split after a run of terminators (so "！！！" stays attached to its sentence
# instead of fragmenting into empty pieces).
_SENT_SPLIT = re.compile(r"(?<=[。！？!?…])(?=[^。！？!?…])|\n+")
# Emoji + the common 小红书 pictographic/symbol ranges.
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF←-⇿✀-➿]"
)
_CN_TOKEN = re.compile(r"[一-鿿A-Za-z0-9]+")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences on CJK/ASCII terminators and newlines."""
    parts = _SENT_SPLIT.split(text)
    return [s.strip() for s in parts if s and s.strip()]


def tokenize(text: str) -> list[str]:
    """jieba tokenize, keeping only CJK/alnum tokens (drops punctuation/space)."""
    toks = []
    for t in jieba.cut(text, cut_all=False):
        t = t.strip()
        if t and _CN_TOKEN.fullmatch(t):
            toks.append(t)
    return toks


def count_emoji(text: str) -> int:
    return len(_EMOJI.findall(text))


def _dist(values: list[float]) -> Dist:
    if not values:
        return Dist()
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(var)
    ordered = sorted(values)
    # nearest-rank p90 (deterministic)
    idx = min(n - 1, max(0, math.ceil(0.9 * n) - 1))
    p90 = ordered[idx]
    return Dist(mean=mean, std=std, p90=p90)


def _opener(sentence: str, k: int = 6) -> str:
    """First k CJK/alnum-ish chars of a sentence, used as an opener signature."""
    core = re.sub(r"\s+", "", sentence)
    return core[:k]


# 小红书 stop-ish tokens: too generic to be a *signature* word, so we exclude
# them from high_freq_tokens (they'd dominate every account identically).
_GENERIC = {
    "的", "了", "是", "我", "你", "他", "她", "它", "这", "那", "在", "和",
    "就", "都", "也", "还", "有", "个", "们", "一个", "一", "不", "很", "会",
    "把", "被", "给", "上", "下", "到", "去", "来", "说", "啊", "呀", "吧",
    "呢", "哦", "嗯", "但", "而", "与", "或", "着", "过", "得", "对", "从",
}


# --------------------------------------------------------------------------- #
# Fingerprint construction
# --------------------------------------------------------------------------- #
def build_profile(
    corpus: str,
    account_id: str = "default",
    top_openers: int = 8,
    top_tokens: int = 20,
) -> VoiceProfile:
    """Build a :class:`VoiceProfile` from a raw corpus string.

    Posts are separated by blank lines (or the literal ``---`` delimiter). Each
    post's sentences and tokens feed the aggregate statistics.
    """
    posts = _split_posts(corpus)
    all_text = "\n".join(posts)

    sentences: list[str] = []
    for post in posts:
        sentences.extend(split_sentences(post))

    tokens = tokenize(all_text)
    n_chars = sum(len(re.sub(r"\s+", "", p)) for p in posts)

    # lexical diversity: type-token ratio (guard tiny corpora)
    ttr = (len(set(tokens)) / len(tokens)) if tokens else 0.0

    # sentence-length distribution (chars, whitespace-stripped)
    sent_lens = [float(len(re.sub(r"\s+", "", s))) for s in sentences if s]
    sent_dist = _dist(sent_lens)

    # emoji cadence
    n_emoji = count_emoji(all_text)
    emoji_per_100 = (n_emoji / n_chars * 100.0) if n_chars else 0.0

    # punctuation rhythm — per sentence
    n_sent = max(1, len(sentences))
    exclaim = all_text.count("！") + all_text.count("!")
    question = all_text.count("？") + all_text.count("?")
    wave = all_text.count("～") + all_text.count("~")
    ellipsis = all_text.count("…") + all_text.count("...") + all_text.count("。。。")

    # opener hooks — most common sentence openers across the corpus
    openers = Counter(_opener(split_sentences(p)[0]) for p in posts if split_sentences(p))
    opener_hooks = [o for o, _ in openers.most_common(top_openers) if o]

    # signature words — frequent, non-generic tokens
    tok_counts = Counter(t for t in tokens if t not in _GENERIC and len(t) >= 1)
    high_freq = [t for t, _ in tok_counts.most_common(top_tokens)]

    profile = VoiceProfile(
        account_id=account_id,
        n_posts=len(posts),
        n_chars=n_chars,
        lexical_diversity=ttr,
        sentence_length=sent_dist,
        emoji_per_100_chars=emoji_per_100,
        exclaim_ratio=exclaim / n_sent,
        question_ratio=question / n_sent,
        wave_ratio=wave / n_sent,
        ellipsis_ratio=ellipsis / n_sent,
        opener_hooks=opener_hooks,
        high_freq_tokens=high_freq,
    )
    profile.signature_vec = _signature_vec(profile)
    return profile


def _split_posts(corpus: str) -> list[str]:
    # split on blank-line runs or an explicit --- fence
    chunks = re.split(r"\n\s*(?:-{3,}\s*)?\n", corpus.strip())
    posts = [c.strip() for c in chunks if c.strip()]
    return posts or ([corpus.strip()] if corpus.strip() else [])


def _signature_vec(p: VoiceProfile) -> list[float]:
    """A small, normalized composite vector used for voice-distance.

    Each dimension is squashed into roughly 0..1 so that Euclidean distance is
    meaningful without any single axis dominating.
    """
    return [
        _clip01(p.lexical_diversity),
        _clip01(p.sentence_length.mean / 60.0),
        _clip01(p.sentence_length.std / 40.0),
        _clip01(p.emoji_per_100_chars / 12.0),
        _clip01(p.exclaim_ratio / 1.5),
        _clip01(p.question_ratio / 1.5),
        _clip01(p.wave_ratio / 1.5),
        _clip01(p.ellipsis_ratio / 1.5),
    ]


def _clip01(x: float) -> float:
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


# --------------------------------------------------------------------------- #
# Voice-distance scoring
# --------------------------------------------------------------------------- #
def voice_distance(profile: VoiceProfile, text: str) -> float:
    """Return a 0..1 distance between ``text`` and the account voice.

    0.0 = indistinguishable from the account's own voice; 1.0 = maximally off.
    Built by fingerprinting the draft with the same statistics and comparing
    signature vectors (Euclidean, normalized by vector length).

    An empty/whitespace-only draft (or one whose signature is all zeros — no
    scorable content) is maximally off-voice: distance 1.0 (consistency 0.0).
    Without this guard an empty draft still yields ``signature_vec=[0.0]*8``
    (8 elements, all zero), so the truthy-list check below does not fire and
    the distance would compute to ~0.32 (consistency ~0.67) — a meaningless
    positive score for an empty rewrite that poisons audit/rewrite/voice-distance.
    """
    draft = build_profile(text, account_id=profile.account_id)
    a = profile.signature_vec
    b = draft.signature_vec
    if not a or not b:
        return 1.0
    # a degenerate draft (empty/whitespace text, or an all-zero signature_vec
    # from a draft with no scorable content) reads as maximally off-voice.
    if not text.strip() or all(v == 0.0 for v in b):
        return 1.0
    n = min(len(a), len(b))
    ss = sum((a[i] - b[i]) ** 2 for i in range(n))
    dist = math.sqrt(ss / n)  # normalized RMS in [0,1]
    return _clip01(dist)


def voice_consistency(profile: VoiceProfile, text: str) -> float:
    """Convenience: 1 - voice_distance, i.e. a 0..1 "sounds like me" score."""
    return round(1.0 - voice_distance(profile, text), 4)


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def save_profile(profile: VoiceProfile, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(profile.to_dict(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return path


def load_profile(path: Path) -> VoiceProfile:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return VoiceProfile.from_dict(data)
