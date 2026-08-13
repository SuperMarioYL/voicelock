"""Regression tests for the v0.4.0 bugfix release.

Each test pins one of the two folded-in fixes:

  * fix-rewrite-reassemble-drops-paragraphs — _reassemble preserves the original
        gap text (newlines / blank-line paragraph breaks) between sentences
        instead of joining stripped sentences with "", so a multi-paragraph
        draft keeps its paragraph structure in the rewrite output.
  * fix-cli-uncaught-fix-exceptions       — the CLI commands catch the
        FileNotFoundError / ValueError raised by the v0.2/v0.3 fixes and exit
        with a clean [red] message (code 1) instead of a raw Python traceback.

All offline, no API key, no network.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from voicelock.cli import app
from voicelock.config import BackendConfig
from voicelock.rewriter import rewrite
from voicelock.voiceprint import build_profile

# A small calm personal-voice corpus (the creator's OWN past 笔记).
CALM_CORPUS = """\
今天去了家门口新开的咖啡馆，坐了一下午。
豆子是耶加雪菲，酸度很干净，配他家的核桃可颂刚好。

周末把阳台的绿萝换了个大一点的盆。
根系已经绕满了旧盆，换完浇透水，叶子第二天就精神了。
"""


@pytest.fixture
def profile():
    return build_profile(CALM_CORPUS, account_id="tester")


# --------------------------------------------------------------------------- #
# fix-rewrite-reassemble-drops-paragraphs
# --------------------------------------------------------------------------- #
def test_clean_multiparagraph_draft_preserves_paragraph_breaks(profile):
    """A clean 3-paragraph draft (zero slop regions) must keep its blank-line
    paragraph breaks in `after` — `after == before` — instead of the stripped/
    empty-joined version that discarded every `\\n`."""
    draft = (
        "第一段正文，写一点今天的小事。\n\n"
        "第二段正文，换个角度记录。\n\n"
        "第三段正文，收个尾。"
    )
    result = rewrite(draft, profile, backend_cfg=BackendConfig(kind="mock"))

    # sanity: this is a genuinely clean draft (no slop, nothing to rewrite)
    assert result.slop_before == 0.0
    assert result.per_region == []

    # the bug: after lost the "\\n\\n" breaks; fix: after == before
    assert result.after == result.before
    assert "\n\n" in result.after
    # and the three paragraph bodies are all present, in order
    assert result.after.count("\n\n") == 2


def test_rewrite_preserves_paragraph_breaks_around_rewritten_regions(profile):
    """When one slop region is rewritten in a multi-paragraph draft, the
    paragraph breaks around the non-rewritten sentences are still preserved
    verbatim (not flattened into a single run-on line)."""
    # paragraph 1 carries a 爆款体 slop shell; paragraphs 2 and 3 are clean
    draft = (
        "姐妹们！！！这个真的绝绝子。\n\n"
        "第二段是干净的个人记录。\n\n"
        "第三段也是正常正文。"
    )
    result = rewrite(draft, profile, backend_cfg=BackendConfig(kind="mock"))

    # the rewrite did fire on paragraph 1 (something was rewritten)
    assert result.per_region
    # the blank-line paragraph breaks survive the rewrite
    assert "\n\n" in result.after
    # the clean paragraphs are preserved verbatim, gaps intact
    assert "第二段是干净的个人记录。" in result.after
    assert "第三段也是正常正文。" in result.after
    # the rewritten region is not the original 爆款体 shell
    assert "绝绝子" not in result.after
    assert "姐妹们" not in result.after


# --------------------------------------------------------------------------- #
# fix-cli-uncaught-fix-exceptions
# --------------------------------------------------------------------------- #
runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_voicelock_home(tmp_path, monkeypatch):
    """Isolate the CLI from the host's real ~/.voicelock + any leaked
    VOICELOCK_* env so the fingerprint/rewrite commands are deterministic."""
    monkeypatch.setenv("VOICELOCK_HOME", str(tmp_path))
    for var in (
        "VOICELOCK_API_KEY",
        "VOICELOCK_BASE_URL",
        "VOICELOCK_MODEL",
        "VOICELOCK_BACKEND",
    ):
        monkeypatch.delenv(var, raising=False)


def test_fingerprint_missing_corpus_exits_clean_not_traceback():
    """`voicelock fingerprint --corpus no/such/file.txt` (the #1 CLI mistake)
    must exit 1 with a clean message, not surface a FileNotFoundError
    traceback."""
    result = runner.invoke(app, ["fingerprint", "--corpus", "no/such/file.txt"])
    assert result.exit_code == 1
    # the FileNotFoundError must be caught, not propagated as the result exception
    assert not isinstance(result.exception, (FileNotFoundError, ValueError))
    # the message names the missing file so the user knows what to fix
    assert "no/such/file.txt" in result.output


def test_fingerprint_bad_account_exits_clean_not_traceback():
    """A path-traversal-style `--account` makes voice_path raise ValueError; the
    CLI must catch it and exit 1 cleanly, not traceback."""
    result = runner.invoke(
        app,
        [
            "fingerprint",
            "--corpus", "今天写了一点正文。",
            "--account", "../../etc/passwd",
        ],
    )
    assert result.exit_code == 1
    assert not isinstance(result.exception, (FileNotFoundError, ValueError))


def test_rewrite_bad_backend_exits_clean_not_traceback():
    """An unknown `--backend` makes resolve_backend raise ValueError; the CLI
    must catch it and exit 1 cleanly, not traceback."""
    result = runner.invoke(
        app, ["rewrite", "今天写了一点正文。", "--backend", "foo"]
    )
    assert result.exit_code == 1
    assert not isinstance(result.exception, (FileNotFoundError, ValueError))
    assert "foo" in result.output


def test_audit_missing_draft_exits_clean_not_traceback():
    """`voicelock audit <typo'd path>` must also catch FileNotFoundError across
    commands (not just fingerprint) and exit 1 cleanly."""
    result = runner.invoke(app, ["audit", "no/such/draft.md"])
    assert result.exit_code == 1
    assert not isinstance(result.exception, (FileNotFoundError, ValueError))
    assert "no/such/draft.md" in result.output
