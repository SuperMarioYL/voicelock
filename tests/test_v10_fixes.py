"""Regression tests for the v0.10.0 release.

Pins three fixes found on the shipped v0.9.0 tree:

* ``fix-rich-markup-user-text`` — creator text must never be parsed as Rich
  markup. A draft containing a Rich-style closing tag (``[/b]``) raised
  ``MarkupError`` inside the renderer, i.e. a raw traceback with exit 1 past the
  clean-error handler; a valid opening tag (``[bold]``) was silently consumed, so
  the creator's literal brackets vanished from the audit table and the 改写后正文
  panel. The ``_clean_user_errors`` message embeds the bad path/account too.
* ``fix-rewrite-missing-profile-notice`` — ``rewrite`` promises an in-your-voice
  rewrite but used to run with ``profile=None`` silently when no fingerprint was
  stored, presenting a default-style de-slop as voice-conditioned output.
* ``fix-version-drift-readme-demo-results`` / ``guard-version-surface-lockstep``
  are covered by ``tests/test_version_consistency.py``.

All offline, no API key, no network.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from voicelock.cli import app
from voicelock.config import API_KEY_ENV, BACKEND_ENV, BASE_URL_ENV, MODEL_ENV

runner = CliRunner()

# A draft with a bracket sequence Rich reads as a closing style tag: the crash
# trigger (MarkupError: closing tag '[/b]' ... doesn't match any open tag).
DRAFT_CLOSING_TAG = "姐妹们！！！[/b]闭眼入不踩雷"

# A draft with a matched, valid pair of Rich style tags: pre-fix these were
# consumed as styling, so the literal brackets disappeared from the output.
DRAFT_OPENING_TAG = "姐妹们！！！[bold]闭眼入[/bold]不踩雷"

# Enough corpus for the fingerprint adequacy guard (>= 2 posts / 200 chars).
ADEQUATE_CORPUS = (
    "今天去了一家新开的咖啡馆，环境真的很不错，装修很有格调，适合周末放松。"
    "老板很热情，手冲咖啡的味道很特别，用的是埃塞俄比亚的豆子，香气浓郁。"
    "店里还有几只猫，很亲人，适合喜欢小动物的朋友去打卡拍照。"
    "总之是一次很愉快的体验，下次还会再来试试他们家的冷萃和拿铁。\n\n"
    "上周去了一家新开的书店，在老城区的巷子里，门面不大但布置得很用心。"
    "书种类不少，文学历史哲学都有，价格也比网上便宜一点，还能现场翻阅。"
    "店主是个退休的老先生，很健谈，给我推荐了好几本不错的书。"
    "我在那里待了一整个下午，买了一本汪曾祺的散文集，很满足。"
)


@pytest.fixture(autouse=True)
def _isolated_voicelock_env(tmp_path, monkeypatch):
    monkeypatch.setenv("VOICELOCK_HOME", str(tmp_path))
    for var in (API_KEY_ENV, BACKEND_ENV, BASE_URL_ENV, MODEL_ENV):
        monkeypatch.delenv(var, raising=False)


# --------------------------------------------------------------------------- #
# fix-rich-markup-user-text
# --------------------------------------------------------------------------- #
def test_audit_renders_a_closing_style_tag_instead_of_crashing():
    """Pre-fix: ``MarkupError: closing tag '[/b]' ... doesn't match any open tag``
    propagated out of Rich and exited 1 with a traceback, because the audit cell
    interpolated the sentence into ``[red]{text}[/red]`` (cli.py:290)."""
    result = runner.invoke(app, ["audit", DRAFT_CLOSING_TAG])
    assert result.exit_code == 0, f"audit crashed: {result.output}"
    assert "MarkupError" not in result.output
    # the creator's literal characters survive into the rendered table
    assert "[/b]" in result.output


def test_rewrite_renders_a_closing_style_tag_instead_of_crashing():
    """Same crash on the rewrite path (before/after rows + 改写后正文 Panel)."""
    result = runner.invoke(
        app, ["rewrite", DRAFT_CLOSING_TAG, "--backend", "mock"]
    )
    assert result.exit_code == 0, f"rewrite crashed: {result.output}"
    assert "MarkupError" not in result.output
    assert "[/b]" in result.output


def test_rewrite_keeps_literal_opening_style_tags():
    """Pre-fix the matched ``[bold]``/``[/bold]`` pair was consumed as styling, so
    the literal bracket characters were missing from the displayed draft."""
    result = runner.invoke(
        app, ["rewrite", DRAFT_OPENING_TAG, "--backend", "mock"]
    )
    assert result.exit_code == 0, f"rewrite crashed: {result.output}"
    assert "[bold]" in result.output
    assert "[/bold]" in result.output


def test_clean_error_message_escapes_user_supplied_path():
    """The clean-error path embeds the offending path in its message; pre-fix
    ``audit '[/b].txt'`` raised MarkupError *inside* the error handler instead of
    printing the '找不到文件' message."""
    result = runner.invoke(app, ["audit", "[/b].txt"])
    assert result.exit_code == 1
    assert "找不到文件" in result.output
    assert "MarkupError" not in result.output
    assert "[/b].txt" in result.output


def test_fingerprint_table_escapes_corpus_openers():
    """Corpus-derived cells (开头习惯 / 签名高频词) are creator text too: a post
    beginning with a Rich style tag must be shown literally, not consumed."""
    corpus = "\n\n".join(f"[bold]{post}" for post in ADEQUATE_CORPUS.split("\n\n"))
    result = runner.invoke(app, ["fingerprint", "--corpus", corpus])
    assert result.exit_code == 0, f"fingerprint failed: {result.output}"
    assert "[bold]" in result.output


# --------------------------------------------------------------------------- #
# fix-rewrite-missing-profile-notice
# --------------------------------------------------------------------------- #
def test_rewrite_warns_when_no_fingerprint_exists():
    """No stored profile: the rewrite still runs (documented default-style path)
    but must say so — pre-fix the output was indistinguishable from a
    voice-conditioned rewrite apart from a missing 声线一致性 number."""
    result = runner.invoke(
        app, ["rewrite", DRAFT_CLOSING_TAG, "--backend", "mock"]
    )
    assert result.exit_code == 0, result.output
    assert "未找到声线指纹" in result.output
    assert "voicelock fingerprint" in result.output


def test_rewrite_is_quiet_when_a_fingerprint_exists():
    """The notice must not fire when the profile exists (no new noise on the
    normal path)."""
    saved = runner.invoke(app, ["fingerprint", "--corpus", ADEQUATE_CORPUS])
    assert saved.exit_code == 0, saved.output

    result = runner.invoke(
        app, ["rewrite", DRAFT_CLOSING_TAG, "--backend", "mock"]
    )
    assert result.exit_code == 0, result.output
    assert "未找到声线指纹" not in result.output
    assert "声线一致性" in result.output
