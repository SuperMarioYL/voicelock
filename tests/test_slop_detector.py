"""Tests for the 爆款体 slop detector + rewrite loop (milestones m2, m3).

All offline, mock backend only — no API key, no network.
"""

from __future__ import annotations

from voicelock.backends.mock import MockBackend
from voicelock.config import BackendConfig
from voicelock.rewriter import rewrite
from voicelock.slop_detector import detect, slop_score
from voicelock.voiceprint import build_profile

# Homogeneous 爆款体 draft — the "一眼AI" template the feed penalizes.
SLOP_DRAFT = (
    "姐妹们！！！这个方法真的绝绝子😭😭😭\n"
    "谁懂啊家人们直接封神yyds！！！\n"
    "手把手教你三步搞定，建议收藏码住🔥🔥🔥\n"
    "错过血亏，闭眼入不踩雷～～～"
)

# Varied, personal-voice draft — same topic, no 爆款体 shell.
VARIED_DRAFT = (
    "分享一个我最近在用的小方法，挺顺手的。\n"
    "大概分三步，我把过程记在下面，方便自己以后复看。\n"
    "试了两周，效果比我想的稳定，成本也不高。\n"
    "如果你也在找类似的思路，可以参考一下。"
)

# The creator's own calm corpus, for the fingerprint.
CORPUS = """\
今天整理了书桌，把常用的几样东西固定了位置。
东西少了反而更好找，心情也清爽。

周末试了个新菜谱，番茄牛腩，炖了两个小时。
汤汁收得刚好，米饭配它能吃两碗。
"""


def test_homogeneous_scores_higher_than_varied():
    slop = slop_score(SLOP_DRAFT)
    clean = slop_score(VARIED_DRAFT)
    assert slop > clean
    # the 爆款体 draft should land clearly in "high slop" territory
    assert slop >= 50
    # the varied personal draft should be low
    assert clean < 25


def test_flagging_returns_sentence_spans():
    result = detect(SLOP_DRAFT)
    assert result.regions, "expected 爆款体 regions to be flagged"
    # every region points at a real sentence index and carries a reason
    for r in result.regions:
        assert isinstance(r.sentence_idx, int)
        assert r.sentence_idx >= 0
        assert r.text.strip()
        assert r.reason.strip()
        assert 0.0 <= r.score <= 100.0
        assert r.slop_type in {"opener_hook", "homogenized_phrase", "emoji_cadence"}
    # at least the group-address opener + a template phrase were caught
    types = {r.slop_type for r in result.regions}
    assert "opener_hook" in types or "homogenized_phrase" in types


def test_varied_draft_flags_few_or_no_regions():
    result = detect(VARIED_DRAFT)
    # a clean personal draft should flag far fewer regions than the slop draft
    slop_regions = detect(SLOP_DRAFT).regions
    assert len(result.regions) < len(slop_regions)


def test_mock_backend_reduces_region_slop():
    backend = MockBackend(BackendConfig(kind="mock"))
    # a content-bearing 爆款体 region (not a pure opener shell) gets rewritten
    # to non-empty, lower-slop text
    region = next(
        r for r in detect(SLOP_DRAFT).regions if "闭眼入" in r.text
    )
    rewritten = backend.rewrite_region(region.text)
    assert rewritten and rewritten != region.text
    new_score = max((r.score for r in detect(rewritten).regions), default=0.0)
    assert new_score < region.score


def test_mock_backend_drops_pure_opener_shell():
    backend = MockBackend(BackendConfig(kind="mock"))
    # a bare group-address hook carries no content — the correct 去AI味 move is
    # to drop it entirely (empty rewrite)
    assert backend.rewrite_region("姐妹们！！！") == ""


def test_before_after_score_drops_after_rewrite():
    profile = build_profile(CORPUS, account_id="tester")
    result = rewrite(SLOP_DRAFT, profile, backend_cfg=BackendConfig(kind="mock"))
    # the whole point: slop goes down after the in-voice rewrite loop
    assert result.slop_after < result.slop_before
    assert result.backend == "mock"
    assert result.before.strip()
    assert result.after.strip()
    # voice consistency is reported when a profile is supplied
    assert result.voice_consistency_after is not None
    assert 0.0 <= result.voice_consistency_after <= 1.0
    # per-region diffs are recorded
    assert result.per_region
    for r in result.per_region:
        assert r["region_slop_after"] <= r["region_slop_before"]


def test_rewrite_without_profile_still_works():
    result = rewrite(SLOP_DRAFT, profile=None, backend_cfg=BackendConfig(kind="mock"))
    assert result.slop_after < result.slop_before
    assert result.voice_consistency_after is None
