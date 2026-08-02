"""Regression tests for the v0.2.0 bugfix release.

Each test pins one of the three folded-in fixes:

  * fix-ascii-exclaim-detect      — ASCII '!!!' bombing is now flagged
  * fix-account-id-path-injection — account_id is sanitized before the path join
  * fix-corpus-file-not-found-silent — a typo'd/missing --corpus file errors

All offline, no API key, no network.
"""

from __future__ import annotations

import pytest

from voicelock.cli import _read_source
from voicelock.config import voice_path
from voicelock.slop_detector import detect


# --------------------------------------------------------------------------- #
# fix-ascii-exclaim-detect
# --------------------------------------------------------------------------- #
def test_ascii_exclaim_bombing_is_detected():
    """r'[!！]{2,}' must flag ASCII '!!!!' too, not just full-width '！！'."""
    result = detect("好货!!!!闭眼入")
    reasons = "；".join(r.reason for r in result.regions)
    assert "感叹号轰炸" in reasons, "ASCII exclamation bombing must be flagged"
    assert result.slop_score > 0


def test_fullwidth_exclaim_bombing_still_detected():
    """The regex change must not regress full-width '！！' detection."""
    result = detect("好货！！！！闭眼入")
    reasons = "；".join(r.reason for r in result.regions)
    assert "感叹号轰炸" in reasons


# --------------------------------------------------------------------------- #
# fix-account-id-path-injection
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "bad",
    [
        "../../etc/passwd",
        "a/b",
        "..",
        "a\\b",
        "a b",
        "",
        "x\x00y",
        "main;rm -rf",
    ],
)
def test_voice_path_rejects_unsafe_account_id(bad, monkeypatch, tmp_path):
    """account_id is validated at the boundary before the path join, so a
    traversal value like `--account ../../etc/passwd` cannot escape the app dir."""
    monkeypatch.setenv("VOICELOCK_HOME", str(tmp_path))
    with pytest.raises(ValueError):
        voice_path(bad)


@pytest.mark.parametrize("good", ["default", "main", "my-account_1", "acct-2"])
def test_voice_path_accepts_safe_account_ids(good, monkeypatch, tmp_path):
    monkeypatch.setenv("VOICELOCK_HOME", str(tmp_path))
    p = voice_path(good)
    # the resolved path must stay inside the (tmp) app dir — no escape
    assert tmp_path in p.parents or p.parent == tmp_path
    if good == "default":
        assert p == tmp_path / "voice.yaml"
    else:
        assert p.name == f"voice.{good}.yaml"


# --------------------------------------------------------------------------- #
# fix-corpus-file-not-found-silent
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("missing", ["does-not-exist.txt", "no/such/dir/posts.md", "./missing.txt"])
def test_read_source_raises_on_missing_pathlike_file(missing):
    """A typo'd/missing --corpus file path must error, not be silently
    fingerprinted as the filename string."""
    with pytest.raises(FileNotFoundError):
        _read_source(missing)


def test_read_source_still_accepts_inline_text():
    # single-line inline text with no path-like markers stays inline
    assert _read_source("好货!!!!闭眼入") == "好货!!!!闭眼入"
    # multi-line inline text stays inline even if it happens to contain a slash
    multiline = "第一篇/笔记\n第二篇笔记"
    assert _read_source(multiline) == multiline


def test_read_source_reads_existing_file(tmp_path):
    f = tmp_path / "posts.txt"
    f.write_text("正文内容", encoding="utf-8")
    assert _read_source(str(f)) == "正文内容"
