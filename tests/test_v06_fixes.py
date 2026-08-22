"""Regression tests for the v0.6.0 bugfix release.

Each test pins one of the three folded-in milestones:

  * fix-flag-emoji-overcount-mangle — a regional-indicator flag pair (🇨🇳) is one
                                      cluster for both counting (voiceprint) and
                                      thinning (mock backend), so it is no longer
                                      over-counted (2) or mangled into a lone
                                      first regional indicator in the rewritten
                                      正文, and the slop detector no longer
                                      false-flags a single flag as emoji ×2
  * fix-llm-no-key-silent-mock      — an explicit request for the llm backend
                                      (--backend llm or VOICELOCK_BACKEND=llm)
                                      with no VOICELOCK_API_KEY raises instead of
                                      silently flipping to mock; the no-arg/no-env
                                      auto-select path stays mock (default-offline)
  * fix-permission-error-traceback   — an existing-but-unreadable file (0000
                                      perms) exits 1 with a clean red message
                                      instead of a raw PermissionError traceback

All offline, no API key, no network.
"""

from __future__ import annotations

import os

import pytest
from typer.testing import CliRunner

from voicelock.backends.mock import MockBackend
from voicelock.cli import app
from voicelock.config import (
    API_KEY_ENV,
    BACKEND_ENV,
    BASE_URL_ENV,
    MODEL_ENV,
    resolve_backend,
)
from voicelock.models import VoiceProfile
from voicelock.slop_detector import detect
from voicelock.voiceprint import count_emoji

# The CN flag 🇨🇳 and JP flag 🇯🇵 built from explicit regional-indicator
# escapes (two RI codepoints, no ZWJ joiner) so the test source carries no
# invisible flag codepoints an editor could silently mangle. Each flag is
# U+1F1E6-\U0001F1FF-range, which sits inside _EMOJI_BASE — the pre-fix bug.
FLAG_CN = "\U0001F1E8\U0001F1F3"        # regional indicator C + N
FLAG_JP = "\U0001F1EF\U0001F1F5"        # regional indicator J + P
FIRST_RI_CN = "\U0001F1E8"              # the lone first indicator the mangle left
SECOND_RI_CN = "\U0001F1F3"


# --------------------------------------------------------------------------- #
# shared isolation: clean VOICELOCK_* env + a private VOICELOCK_HOME so the
# CLI/config is deterministic and does not touch the host's real ~/.voicelock.
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolated_voicelock_env(tmp_path, monkeypatch):
    monkeypatch.setenv("VOICELOCK_HOME", str(tmp_path))
    for var in (API_KEY_ENV, BACKEND_ENV, BASE_URL_ENV, MODEL_ENV):
        monkeypatch.delenv(var, raising=False)


# --------------------------------------------------------------------------- #
# fix-flag-emoji-overcount-mangle
# --------------------------------------------------------------------------- #
def test_count_emoji_flag_pair_is_one_cluster():
    """A single flag (🇨🇳) is TWO regional-indicator codepoints with no ZWJ
    joiner; each RI matched _EMOJI_BASE separately, so count_emoji returned 2.
    The flag-pair alternative makes the whole flag ONE cluster → count 1."""
    assert count_emoji(FLAG_CN) == 1
    assert count_emoji(FLAG_JP) == 1


def test_count_emoji_flag_plus_separate_emoji():
    """A flag followed by a separate pictograph counts as 2, not 3."""
    assert count_emoji(FLAG_CN + "🎉") == 2


def test_count_emoji_two_flags():
    """Two flags back-to-back count as 2 (one cluster each), not 4."""
    assert count_emoji(FLAG_CN + FLAG_JP) == 2


def test_count_emoji_flag_in_sentence():
    """A single flag embedded in a sentence counts as 1 (was 2 pre-fix, which
    inflated emoji_per_100_chars for a short flag-bearing corpus)."""
    assert count_emoji("今天去了咖啡馆" + FLAG_CN + "坐了一下午") == 1


def test_count_emoji_zwj_still_one_cluster_no_regression():
    """The flag fix must not regress the v0.5.0 ZWJ fix: a ZWJ family is still
    one cluster, and mixing a flag with a ZWJ family counts each as one."""
    family = "👨\u200d👩\u200d👧\u200d👦"
    assert count_emoji(family) == 1
    assert count_emoji(FLAG_CN + family) == 2


def test_thin_emoji_keeps_whole_flag():
    """With the default target=1 (no profile), a flag is kept INTACT — not split
    into a lone first RI plus a dropped second RI (the verified mangle that left
    a broken lone-regional-indicator render in the rewritten 正文)."""
    out = MockBackend()._thin_emoji("a" + FLAG_CN + "b", None)
    # the whole flag survives intact (target=1 keeps it as one cluster)
    assert FLAG_CN in out
    # no lone first indicator without its pair (the mangle signature)
    assert FIRST_RI_CN + "b" not in out.replace(FLAG_CN, "")


def test_thin_emoji_drops_whole_flag_no_lone_ri():
    """When the account cadence target is 0, a flag is dropped as ONE unit —
    no lone first indicator kept behind (the thin path treats the pair as a
    single cluster, mirroring the ZWJ keep/drop-whole behavior)."""
    zero_cadence = VoiceProfile(account_id="t", emoji_per_100_chars=0.0)
    out = MockBackend()._thin_emoji("a" + FLAG_CN + "b", zero_cadence)
    # the whole flag is gone — neither RI is orphaned
    assert FIRST_RI_CN not in out
    assert SECOND_RI_CN not in out


def test_rewrite_region_no_mangled_lone_ri():
    """rewrite_region on a 爆款体 shell containing a flag must not emit a lone
    first regional indicator. Without the fix it returned a lone first-RI plus
    可以放心买。; with the fix the whole flag is kept (target=1)."""
    out = MockBackend().rewrite_region("姐妹们！！！" + FLAG_CN + "闭眼入")
    # the whole flag survives intact (not a lone first RI)
    assert FLAG_CN in out
    assert FIRST_RI_CN + "可以放心买" not in out.replace(FLAG_CN, "")
    # the phrase rewrite still happened
    assert "可以放心买" in out


def test_detect_single_flag_not_false_flagged_as_emoji_stack():
    """A single flag is one cluster, so the slop detector must NOT add the
    'emoji 堆叠 ×2' reason that the pre-fix 2x over-count triggered (which
    pushed a 姐妹们+flag+闭眼入 sentence's slop_score to 100). The sentence
    still flags as 爆款体 via the opener + 闭眼入 phrase — just not for emoji
    stacking, since one emoji is below the soft threshold of 2."""
    result = detect("姐妹们" + FLAG_CN + "闭眼入")
    # still flagged (姐妹们 opener + 闭眼入 template phrase)
    assert result.regions
    # but NOT for emoji stacking — a single flag is one cluster
    for r in result.regions:
        assert "emoji 堆叠" not in r.reason


# --------------------------------------------------------------------------- #
# fix-llm-no-key-silent-mock
# --------------------------------------------------------------------------- #
def test_explicit_llm_no_key_raises(monkeypatch):
    """An explicit --backend llm with no key must raise (naming the missing
    key), not silently resolve to mock. Without the fix it returned mock."""
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    with pytest.raises(ValueError, match=API_KEY_ENV):
        resolve_backend("llm")


def test_explicit_llm_whitespace_no_key_raises(monkeypatch):
    """An explicit --backend ' llm ' (whitespace/case-normalized to llm) with no
    key still raises — the explicit-llm-no-key path is not evaded by padding."""
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    with pytest.raises(ValueError, match=API_KEY_ENV):
        resolve_backend(" llm ")


def test_env_llm_no_key_raises(monkeypatch):
    """VOICELOCK_BACKEND=llm with no key must raise, not silently flip to mock
    (the same silent-misconfig class the v0.3.0/v0.5.0 fixes made loud for
    unknown values)."""
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    monkeypatch.setenv(BACKEND_ENV, "llm")
    with pytest.raises(ValueError, match=API_KEY_ENV):
        resolve_backend(None)


def test_env_llm_whitespace_no_key_raises(monkeypatch):
    """VOICELOCK_BACKEND=' LLM ' (normalized to llm) with no key still raises."""
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    monkeypatch.setenv(BACKEND_ENV, " LLM ")
    with pytest.raises(ValueError, match=API_KEY_ENV):
        resolve_backend(None)


def test_auto_select_no_key_stays_mock_no_raise():
    """CRITICAL: the no-arg/no-env auto-select path (kind = llm-if-key-else-mock)
    must stay mock with NO raise when no key is set — default-offline behavior
    is unchanged. Without a key it resolves to mock directly and never reaches
    the llm-no-key raise."""
    cfg = resolve_backend(None)
    assert cfg.kind == "mock"


def test_auto_select_with_key_is_llm(monkeypatch):
    """Auto-select with a key set (no explicit --backend, no VOICELOCK_BACKEND)
    resolves to llm — the explicit-llm-no-key raise must not fire here."""
    monkeypatch.setenv(API_KEY_ENV, "sk-test")
    cfg = resolve_backend(None)
    assert cfg.kind == "llm"


def test_explicit_llm_with_key_stays_llm(monkeypatch):
    """An explicit --backend llm WITH a key resolves to llm (no raise) — the fix
    only raises when the key is missing, so a correctly-configured llm request
    is unchanged."""
    monkeypatch.setenv(API_KEY_ENV, "sk-test")
    cfg = resolve_backend("llm")
    assert cfg.kind == "llm"


def test_explicit_mock_no_key_stays_mock():
    """An explicit --backend mock never needs a key and stays mock — the fix
    only targets the llm-no-key case, so mock is unchanged."""
    cfg = resolve_backend("mock")
    assert cfg.kind == "mock"


def test_auto_select_empty_env_no_key_stays_mock_no_raise(monkeypatch):
    """An empty VOICELOCK_BACKEND ('') is treated as 'not set' — it must fall
    through to the key-based default (mock, no key) with NO raise, so an empty
    env value does not trip the explicit-llm-no-key path."""
    monkeypatch.setenv(BACKEND_ENV, "")
    cfg = resolve_backend(None)
    assert cfg.kind == "mock"


# --------------------------------------------------------------------------- #
# fix-llm-no-key-silent-mock — CLI surface
# --------------------------------------------------------------------------- #
runner = CliRunner()


def test_rewrite_explicit_llm_no_key_exits_clean_not_traceback():
    """`voicelock rewrite <draft> --backend llm` with no key must exit 1 with a
    clean red message naming the missing key, not surface a raw ValueError
    traceback (the non-dev creator gets a loud misconfig error, not silent mock
    output)."""
    result = runner.invoke(app, ["rewrite", "今天写了一点正文。", "--backend", "llm"])
    assert result.exit_code == 1
    # the ValueError must be caught by _clean_user_errors, not propagated
    assert not isinstance(result.exception, ValueError)
    # the message names the missing key so the user knows what to set
    assert API_KEY_ENV in result.output


# --------------------------------------------------------------------------- #
# fix-permission-error-traceback
# --------------------------------------------------------------------------- #
# A 0000-permission file is unreadable by its owner (read_text raises
# PermissionError); skip under root, which bypasses file perms and would make
# the read succeed (a meaningless pass that would hide a regression).
_perm_skip = pytest.mark.skipif(
    os.geteuid() == 0 if hasattr(os, "geteuid") else False,
    reason="root bypasses 0000 file perms",
)


@_perm_skip
def test_audit_unreadable_file_exits_clean_not_traceback(tmp_path):
    """`voicelock audit <unreadable.md>` must exit 1 with a clean red message,
    not surface a raw PermissionError traceback. is_file() returns True (it
    checks file type, not readability), so read_text raises PermissionError —
    the broadened (OSError, ValueError) catch turns it into a clean exit."""
    f = tmp_path / "unreadable.md"
    f.write_text("正文内容", encoding="utf-8")
    f.chmod(0)
    try:
        result = runner.invoke(app, ["audit", str(f)])
        assert result.exit_code == 1
        # the PermissionError must be caught, not propagated as the exception
        assert not isinstance(result.exception, OSError)
        # a clean red message was printed (not a raw traceback)
        assert "错误" in result.output
        assert "unreadable.md" in result.output
    finally:
        f.chmod(0o600)  # restore so tmp_path teardown can remove the file


@_perm_skip
def test_fingerprint_unreadable_corpus_exits_clean_not_traceback(tmp_path):
    """`voicelock fingerprint --corpus <unreadable.md>` must also catch the
    PermissionError across commands (not just audit) and exit 1 cleanly."""
    f = tmp_path / "unreadable_corpus.md"
    f.write_text("正文内容", encoding="utf-8")
    f.chmod(0)
    try:
        result = runner.invoke(app, ["fingerprint", "--corpus", str(f)])
        assert result.exit_code == 1
        assert not isinstance(result.exception, OSError)
        assert "错误" in result.output
    finally:
        f.chmod(0o600)
