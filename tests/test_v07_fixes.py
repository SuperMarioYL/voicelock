"""Regression tests for the v0.7.0 release.

Each test pins one of the three folded-in milestones:

  * fix-read-source-cjk-filename-silent — a missing CJK-named file with an
                                            ASCII extension (.txt/.md) raises
                                            FileNotFoundError instead of being
                                            silently treated as inline text,
                                            while CJK inline text with a CJK
                                            dot-suffix ("一句话.好的") and
                                            slash-bearing CJK ("他/她 都可以")
                                            are still accepted
  * fix-thin-emoji-banker-rounding      — _thin_emoji uses round-half-up so a
                                            0.5 emoji allowance keeps one, not
                                            zero (banker's rounding dropped ALL
                                            emoji from a 10-char region at
                                            cadence 5.0)
  * feature-voice-distance-breakdown    — voice_distance_breakdown returns
                                            per-dimension (label, delta,
                                            contribution) sorted by
                                            contribution, and the CLI shows it

All offline, no API key, no network.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from voicelock.backends.mock import MockBackend
from voicelock.cli import app, _read_source
from voicelock.models import VoiceProfile
from voicelock.voiceprint import voice_distance_breakdown

runner = CliRunner()


# --------------------------------------------------------------------------- #
# shared isolation
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolated_voicelock_env(tmp_path, monkeypatch):
    monkeypatch.setenv("VOICELOCK_HOME", str(tmp_path))
    from voicelock.config import API_KEY_ENV, BACKEND_ENV, BASE_URL_ENV, MODEL_ENV

    for var in (API_KEY_ENV, BACKEND_ENV, BASE_URL_ENV, MODEL_ENV):
        monkeypatch.delenv(var, raising=False)


# --------------------------------------------------------------------------- #
# fix-read-source-cjk-filename-silent
# --------------------------------------------------------------------------- #
def test_missing_cjk_filename_ascii_ext_raises():
    """A missing CJK-named file with an ASCII extension (.txt) must raise
    FileNotFoundError, not be silently returned as the filename string."""
    with pytest.raises(FileNotFoundError, match="找不到文件"):
        _read_source("我的笔记.txt")


def test_missing_cjk_filename_md_ext_raises():
    """Same for .md — any ASCII extension triggers the file-not-found guard."""
    with pytest.raises(FileNotFoundError, match="找不到文件"):
        _read_source("小红书笔记.md")


def test_missing_ascii_filename_still_raises():
    """Regression: an ASCII-named missing file still raises (unchanged)."""
    with pytest.raises(FileNotFoundError, match="找不到文件"):
        _read_source("my-posts.txt")


def test_cjk_inline_with_cjk_dot_suffix_still_accepted():
    """The v0.3.0 fix's CJK exemption still accepts CJK inline text with a
    CJK dot-suffix ("一句话.好的") — the suffix is non-ASCII so it's not a
    real file extension."""
    result = _read_source("一句话.好的")
    assert result == "一句话.好的"


def test_cjk_inline_with_slash_still_accepted():
    """Slash-bearing CJK inline text ("他/她 都可以") is still accepted —
    no ASCII extension means it's not treated as a file path."""
    result = _read_source("他/她 都可以")
    assert result == "他/她 都可以"


def test_cjk_inline_date_with_slash_still_accepted():
    """A date with a slash and CJK ("2026/07/06 总结") is still accepted."""
    result = _read_source("2026/07/06 总结")
    assert result == "2026/07/06 总结"


def test_existing_cjk_named_file_reads_correctly(tmp_path):
    """A genuine CJK-named file that EXISTS is read correctly (is_file()
    short-circuits first)."""
    f = tmp_path / "我的笔记.txt"
    f.write_text("正文内容", encoding="utf-8")
    result = _read_source(str(f))
    assert result == "正文内容"


def test_audit_missing_cjk_file_exits_clean_not_silent():
    """`voicelock audit 我的笔记.txt` with a missing file must exit 1 with a
    clean error, not silently audit the filename string."""
    result = runner.invoke(app, ["audit", "我的笔记.txt"])
    assert result.exit_code == 1
    assert "找不到文件" in result.output


# --------------------------------------------------------------------------- #
# fix-thin-emoji-banker-rounding
# --------------------------------------------------------------------------- #
def test_thin_emoji_half_up_not_banker_rounding():
    """A 10-char region with emoji_per_100=5.0: the expected emoji count is
    0.5. Banker's rounding gave 0 (dropped ALL emoji); round-half-up gives 1
    (keeps one). This is the core regression — adding ONE char no longer
    flips the target from 0 to 1."""
    import re

    emoji = "\U0001F389"
    profile = VoiceProfile(account_id="t", emoji_per_100_chars=5.0)
    text = "一二三四五六七八九" + emoji  # 9 CJK + 1 emoji = 10 non-ws chars
    out = MockBackend()._thin_emoji(text, profile)
    assert emoji in out  # the emoji is KEPT (target=1, not 0)


def test_thin_emoji_zero_cadence_drops_all():
    """Regression: an account with zero emoji cadence still drops all emoji
    (target=0)."""
    emoji = "\U0001F389"
    profile = VoiceProfile(account_id="t", emoji_per_100_chars=0.0)
    out = MockBackend()._thin_emoji("正文" + emoji + "内容", profile)
    assert emoji not in out


def test_thin_emoji_high_cadence_keeps_two():
    """Regression: a high-cadence account (20/100) on a 10-char region keeps
    up to 2 emoji (target=min(2, round(2.0))=2)."""
    emoji = "\U0001F389"
    profile = VoiceProfile(account_id="t", emoji_per_100_chars=20.0)
    text = "一二三" + emoji + emoji + emoji + "四五六"  # 3+3+3 = 9 CJK + 3 emoji
    out = MockBackend()._thin_emoji(text, profile)
    assert out.count(emoji) == 2  # target=2, keeps first 2


# --------------------------------------------------------------------------- #
# feature-voice-distance-breakdown
# --------------------------------------------------------------------------- #
def _build_profile():
    """Build a simple VoiceProfile for breakdown tests."""
    from voicelock.voiceprint import build_profile

    corpus = (
        "今天去了一家新开的咖啡馆，环境真的很不错。\n"
        "老板很热情，手冲咖啡的味道很特别。\n\n"
        "推荐大家去试试，地址在市中心那条老街上。\n"
        "价格也合理，人均五十左右，性价比很高。"
    )
    return build_profile(corpus)


def test_breakdown_returns_sorted_list():
    """voice_distance_breakdown returns a non-empty list of (label, delta,
    contribution) tuples sorted by contribution descending."""
    profile = _build_profile()
    bd = voice_distance_breakdown(profile, "姐妹们！！！闭眼入绝绝子yyds")
    assert len(bd) > 0
    # each entry is a 3-tuple
    for entry in bd:
        assert len(entry) == 3
        label, delta, contrib = entry
        assert isinstance(label, str)
        assert isinstance(delta, float)
        assert isinstance(contrib, float)
    # sorted by contribution descending
    contribs = [e[2] for e in bd]
    assert contribs == sorted(contribs, reverse=True)


def test_breakdown_contributions_sum_to_one():
    """The contributions across all dimensions sum to ~1.0."""
    profile = _build_profile()
    bd = voice_distance_breakdown(profile, "姐妹们！！！闭眼入")
    if bd:
        total = sum(e[2] for e in bd)
        assert abs(total - 1.0) < 0.01


def test_breakdown_empty_draft_returns_empty():
    """An empty/whitespace-only draft returns an empty breakdown (no scorable
    content)."""
    profile = _build_profile()
    assert voice_distance_breakdown(profile, "") == []
    assert voice_distance_breakdown(profile, "   ") == []


def test_breakdown_identical_text_returns_empty():
    """When the draft IS the corpus (distance 0), the breakdown is empty
    (no dimensions are off)."""
    corpus = (
        "今天去了一家新开的咖啡馆，环境真的很不错。\n"
        "老板很热情，手冲咖啡的味道很特别。"
    )
    from voicelock.voiceprint import build_profile

    profile = build_profile(corpus)
    assert voice_distance_breakdown(profile, corpus) == []


def test_voice_distance_cmd_shows_breakdown():
    """The voice-distance CLI command shows the per-dimension breakdown table
    after the score panel (when a profile exists)."""
    # Build a profile first (corpus must pass the ≥2 posts / ≥200 chars guard)
    corpus = (
        "今天去了一家新开的咖啡馆，环境真的很不错，装修很有格调，适合周末放松。"
        "老板很热情，手冲咖啡的味道很特别，用的是埃塞俄比亚的豆子，香气浓郁。"
        "店里还有几只猫，很亲人，适合喜欢小动物的朋友去打卡拍照。"
        "总之是一次很愉快的体验，下次还会再来试试他们家的冷萃和拿铁。\n\n"
        "上周去了一家新开的书店，在老城区的巷子里，门面不大但布置得很用心。"
        "书种类不少，文学历史哲学都有，价格也比网上便宜一点，还能现场翻阅。"
        "店主是个退休的老先生，很健谈，给我推荐了好几本不错的书。"
        "我在那里待了一整个下午，买了一本汪曾祺的散文集，很满足。"
    )
    fp_result = runner.invoke(app, ["fingerprint", "--corpus", corpus])
    assert fp_result.exit_code == 0, f"fingerprint failed: {fp_result.output}"
    # Now run voice-distance on an off-voice draft
    result = runner.invoke(app, ["voice-distance", "姐妹们！！！闭眼入绝绝子"])
    assert result.exit_code == 0
    assert "声线差异分解" in result.output
    assert "维度" in result.output
    assert "占比" in result.output
