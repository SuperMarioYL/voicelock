"""Regression tests for the v0.5.0 bugfix release.

Each test pins one of the three folded-in milestones:

  * fix-env-backend-silent-invalid   — a bogus non-empty VOICELOCK_BACKEND env
                                       value raises instead of silently flipping
                                       to the opposite backend when a key is set
  * fix-emoji-zwj-mangle             — a ZWJ-joined emoji run (👨‍👩‍👧‍👦) is one
                                       cluster for both counting (voiceprint) and
                                       thinning (mock backend), so it is no longer
                                       over-counted (4) or mangled into orphaned
                                       U+200D control chars in the rewritten 正文
  * guard-tiny-corpus-fingerprint    — the fingerprint command refuses a too-small
                                       corpus (n_posts < 2 or n_chars < 200)
                                       instead of silently producing a meaningless
                                       ~0.99 voice profile

All offline, no API key, no network.
"""

from __future__ import annotations

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
from voicelock.voiceprint import count_emoji

# The ZWJ family emoji 👨‍👩‍👧‍👦 built from explicit escapes (man+ZWJ+woman+ZWJ+
# girl+ZWJ+boy) so the test source carries no invisible U+200D chars that an
# editor could silently mangle.
FAMILY = "👨\u200d👩\u200d👧\u200d👦"
SKIN = "👨\U0001F3FB\u200d👩\U0001F3FF"  # man+light-skin+ZWJ+woman+dark-skin


# --------------------------------------------------------------------------- #
# fix-env-backend-silent-invalid
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _clean_voicelock_env(monkeypatch):
    """Strip every VOICELOCK_* env var so backend resolution is deterministic and
    does not leak the host's real key/url/backend into the assertions."""
    for var in (API_KEY_ENV, BACKEND_ENV, BASE_URL_ENV, MODEL_ENV):
        monkeypatch.delenv(var, raising=False)


@pytest.mark.parametrize("bad", ["moc", "foo", "qwen", "mok", "bogus"])
def test_env_invalid_backend_raises_without_key(bad, monkeypatch):
    """A bogus non-empty VOICELOCK_BACKEND (no key set) must raise, not silently
    fall back to mock."""
    monkeypatch.setenv(BACKEND_ENV, bad)
    with pytest.raises(ValueError, match="unknown VOICELOCK_BACKEND"):
        resolve_backend(None)


def test_env_invalid_backend_raises_with_key_not_silent_flip(monkeypatch):
    """The critical verified case: with VOICELOCK_API_KEY set, a typo'd
    VOICELOCK_BACKEND=moc must raise — NOT silently resolve to 'llm' (silent
    network calls against the user's key). Without the fix it returned llm."""
    monkeypatch.setenv(API_KEY_ENV, "sk-test")
    monkeypatch.setenv(BACKEND_ENV, "moc")
    with pytest.raises(ValueError, match="unknown VOICELOCK_BACKEND"):
        resolve_backend(None)


def test_env_invalid_backend_with_whitespace_case_raises(monkeypatch):
    """A value like ' MoC ' is stripped+lowered to 'moc' → still raises; the
    message names the cleaned value so the user can see what was wrong."""
    monkeypatch.setenv(BACKEND_ENV, " MoC ")
    with pytest.raises(ValueError, match="moc"):
        resolve_backend(None)


def test_env_empty_falls_through_to_default_offline(monkeypatch):
    """An empty VOICELOCK_BACKEND ('') is treated as 'not set' — it must NOT
    raise (it falls through to the key-based default), so the default-offline
    behavior is unchanged."""
    monkeypatch.setenv(BACKEND_ENV, "")
    cfg = resolve_backend(None)
    assert cfg.kind == "mock"


def test_env_unset_falls_through_to_default_offline():
    """No VOICELOCK_BACKEND at all → mock (default-offline), no raise."""
    cfg = resolve_backend(None)
    assert cfg.kind == "mock"


def test_env_valid_backend_resolves(monkeypatch):
    """Valid env values resolve as before: 'mock' (any case) stays mock; 'llm'
    with a key stays llm."""
    monkeypatch.setenv(BACKEND_ENV, "MOCK")
    assert resolve_backend(None).kind == "mock"

    monkeypatch.setenv(BACKEND_ENV, "llm")
    monkeypatch.setenv(API_KEY_ENV, "sk-test")
    assert resolve_backend(None).kind == "llm"


def test_explicit_arg_still_takes_precedence_over_env(monkeypatch):
    """An explicit --backend (prefer) still wins over a bogus env value (the env
    value is never read when prefer is a valid backend), preserving v0.3.0."""
    monkeypatch.setenv(BACKEND_ENV, "qwen")
    assert resolve_backend("mock").kind == "mock"


# --------------------------------------------------------------------------- #
# fix-emoji-zwj-mangle
# --------------------------------------------------------------------------- #
def test_count_emoji_zwj_family_is_one_cluster():
    """👨‍👩‍👧‍👦 is ONE logical emoji → count_emoji returns 1, not 4 (the
    codepoint-level over-count that inflated the emoji_cadence slop signal)."""
    assert count_emoji(FAMILY) == 1


def test_count_emoji_zwj_family_plus_separate_emoji():
    """A ZWJ cluster followed by a separate emoji counts as 2, not 5."""
    assert count_emoji(FAMILY + "🎉") == 2


def test_count_emoji_skin_tone_zwj_is_one_cluster():
    """A skin-toned ZWJ couple (man+skin+ZWJ+woman+skin) is one cluster."""
    assert count_emoji(SKIN) == 1


def test_count_emoji_single_and_runs_unchanged():
    """Non-ZWJ emoji counting must not regress: one emoji = 1, a run of three
    distinct emoji = 3."""
    assert count_emoji("😭") == 1
    assert count_emoji("😭😭😭") == 3
    assert count_emoji("今天去了咖啡馆") == 0


def test_thin_emoji_keeps_whole_zwj_cluster():
    """With the default target=1 (no profile), a ZWJ cluster is kept INTACT —
    not split into one pictograph plus orphaned U+200D joiners."""
    out = MockBackend()._thin_emoji("a" + FAMILY + "b", None)
    # the whole logical emoji is preserved
    assert FAMILY in out
    # no doubled ZWJ (the mangle signature: 👨\u200d\u200d\u200d)
    assert "\u200d\u200d" not in out


def test_thin_emoji_drops_whole_zwj_cluster_no_orphans():
    """When the account cadence target is 0, a ZWJ cluster is dropped as ONE
    unit — no pictograph kept with dangling U+200D control chars left behind."""
    zero_cadence = VoiceProfile(account_id="t", emoji_per_100_chars=0.0)
    out = MockBackend()._thin_emoji("a" + FAMILY + "b", zero_cadence)
    # the whole cluster is gone
    assert FAMILY not in out
    # and NO orphaned ZWJ control char remains (the verified mangle left 👨\u200d\u200d\u200d)
    assert "\u200d" not in out


def test_rewrite_region_no_mangled_zwj_orphans():
    """rewrite_region on a 爆款体 shell containing a family emoji must not emit
    orphaned U+200D control chars. Without the fix it returned
    '👨\\u200d\\u200d\\u200d可以放心买。'; with the fix the cluster is kept whole."""
    out = MockBackend().rewrite_region("姐妹们！！！" + FAMILY + "闭眼入")
    # the verified mangle produced doubled ZWJ; the fix must not
    assert "\u200d\u200d" not in out
    # the whole logical emoji survives intact (target=1 keeps it)
    assert FAMILY in out


# --------------------------------------------------------------------------- #
# guard-tiny-corpus-fingerprint
# --------------------------------------------------------------------------- #
runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_voicelock_home(tmp_path, monkeypatch):
    """Isolate the CLI from the host's real ~/.voicelock + any leaked
    VOICELOCK_* env so the fingerprint command is deterministic."""
    monkeypatch.setenv("VOICELOCK_HOME", str(tmp_path))
    for var in (API_KEY_ENV, BACKEND_ENV, BASE_URL_ENV, MODEL_ENV):
        monkeypatch.delenv(var, raising=False)


# An adequate corpus (≥2 posts, ≥200 non-whitespace chars) that clears the guard.
ADEQUATE_CORPUS = (
    "今天去了家门口新开的咖啡馆，坐了一下午。豆子是耶加雪菲，酸度很干净，配他家的核桃可颂刚好。"
    "店里人不多，适合带本书慢慢待着，下午的光线透过玻璃落在木桌上，翻几页书再喝一口，确实舒服。"
    "老板说他每周只烘一锅，卖完就关门，这种节奏在城里很少见。\n\n"
    "周末把阳台的绿萝换了个大一点的盆。根系已经绕满了旧盆，换完浇透水，叶子第二天就精神了。"
    "养植物这件事，急不得，慢慢来反而长得好，根扎稳了叶子自然就绿，浇水也不用太勤快。"
)


def test_fingerprint_single_char_corpus_refuses():
    """A single-character corpus ('好') yields a meaningless ~0.99 profile; the
    guard must refuse (exit 1) with a clear message, not silently save it."""
    result = runner.invoke(app, ["fingerprint", "--corpus", "好"])
    assert result.exit_code == 1
    assert not isinstance(result.exception, (FileNotFoundError, ValueError))
    assert "语料太少" in result.output
    assert "声线指纹不可靠" in result.output


def test_fingerprint_single_short_post_refuses():
    """A 1-post 9-char corpus is too small (n_posts < 2); the guard refuses."""
    result = runner.invoke(app, ["fingerprint", "--corpus", "今天写了一点正文。"])
    assert result.exit_code == 1
    assert "语料太少" in result.output


def test_fingerprint_two_post_short_chars_refuses():
    """Two posts but <200 chars total — the n_chars floor fires even though
    n_posts >= 2, so the guard still refuses (a 2-post ~20-char corpus is still
    statistically meaningless)."""
    two_post_short = "今天去了咖啡馆，坐了一下午。\n\n周末换了绿萝的盆。"
    result = runner.invoke(app, ["fingerprint", "--corpus", two_post_short])
    assert result.exit_code == 1
    assert "语料太少" in result.output


def test_fingerprint_adequate_corpus_succeeds():
    """An adequate corpus (≥2 posts, ≥200 chars) clears the guard, saves the
    profile, and exits 0 — the guard must not over-fire on real input."""
    result = runner.invoke(app, ["fingerprint", "--corpus", ADEQUATE_CORPUS])
    assert result.exit_code == 0
    assert "声线指纹已保存" in result.output
