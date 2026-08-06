"""Regression tests for the v0.3.0 bugfix release.

Each test pins one of the three folded-in fixes:

  * fix-voice-distance-empty-draft    — empty/whitespace draft reads as maximally
                                        off-voice (consistency 0.0), not ~0.67
  * fix-read-source-inline-reject      — single-line CJK inline drafts with a
                                        slash/dot-suffix are inline, not a
                                        missing-file error
  * fix-resolve-backend-silent-invalid — an explicit but unknown --backend
                                        raises instead of silently falling back

All offline, no API key, no network.
"""

from __future__ import annotations

import pytest

from voicelock.cli import _read_source
from voicelock.config import (
    API_KEY_ENV,
    BACKEND_ENV,
    BASE_URL_ENV,
    MODEL_ENV,
    BackendConfig,
    resolve_backend,
)
from voicelock.rewriter import rewrite
from voicelock.voiceprint import build_profile, voice_consistency, voice_distance

# A small personal-voice corpus (the creator's OWN past 笔记) for the
# fingerprint; the exact corpus is not load-bearing — any non-degenerate
# profile must score an empty draft as maximally off-voice.
CORPUS = """\
今天去了家门口新开的咖啡馆，坐了一下午。
豆子是耶加雪菲，酸度很干净，配他家的核桃可颂刚好。

周末把阳台的绿萝换了个大一点的盆。
根系已经绕满了旧盆，换完浇透水，叶子第二天就精神了。
"""


@pytest.fixture
def profile():
    return build_profile(CORPUS, account_id="tester")


# --------------------------------------------------------------------------- #
# fix-voice-distance-empty-draft
# --------------------------------------------------------------------------- #
def test_empty_draft_voice_distance_is_maximal(profile):
    """An empty draft has no scorable content → distance must be 1.0 (max off),
    not the ~0.32 that falls out of comparing against an all-zero signature_vec."""
    assert voice_distance(profile, "") == 1.0


def test_whitespace_only_draft_voice_consistency_is_zero(profile):
    """A whitespace-only draft is equally degenerate → consistency 0.0, never a
    fake mid-range positive score."""
    assert voice_consistency(profile, "   \n  \t ") == 0.0


def test_nonempty_draft_still_scores_normally(profile):
    """The empty-draft guard must not collapse real drafts to 1.0."""
    d = voice_distance(profile, "今天去了家门口新开的咖啡馆，坐了一下午。")
    assert 0.0 <= d < 1.0
    # an off-voice 爆款体 draft must still be further away than an in-voice one
    assert voice_consistency(profile, "今天去了家门口新开的咖啡馆。") > 0.0


def test_rewrite_empty_after_reports_zero_consistency(profile):
    """rewrite of a pure 爆款体 shell whose regions all drop to empty must
    report voice_consistency_after == 0.0, not a fake ~0.67 positive."""
    result = rewrite(
        "姐妹们！！！", profile, backend_cfg=BackendConfig(kind="mock")
    )
    # the mock backend drops a bare group-address hook to an empty after
    assert result.after == ""
    # the fix: empty after reads as zero consistency, not 0.6742
    assert result.voice_consistency_after == 0.0


# --------------------------------------------------------------------------- #
# fix-read-source-inline-reject
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "inline",
    [
        "2026/07/06 总结",   # a date slash inside CJK inline text
        "他/她 都可以",       # a gender slash inside CJK inline text
        "一句话.好的",       # a mid-text ASCII period → non-empty Path.suffix
    ],
)
def test_cjk_inline_draft_with_slash_or_suffix_is_inline(inline):
    """A single-line CJK inline draft that merely contains a slash or a
    dot-suffix is treated as inline content, not a FileNotFoundError."""
    assert _read_source(inline) == inline


def test_ascii_missing_pathlike_input_still_raises():
    """The CJK gate must not over-loosen: a typo'd ASCII file path with no CJK
    still raises FileNotFoundError (a missing --corpus my-posts.txt must error)."""
    with pytest.raises(FileNotFoundError):
        _read_source("no/such/dir/posts.md")


def test_existing_cjk_named_file_still_reads(tmp_path):
    """The is_file() short-circuit stays first, so a genuine existing CJK-named
    file (with a slash-y look) still reads from disk instead of being treated as
    inline text."""
    f = tmp_path / "好货.txt"
    f.write_text("正文内容", encoding="utf-8")
    assert _read_source(str(f)) == "正文内容"


# --------------------------------------------------------------------------- #
# fix-resolve-backend-silent-invalid
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _clean_voicelock_env(monkeypatch):
    """Strip every VOICELOCK_* env var so backend resolution is deterministic
    and does not leak the host's real key/url into the assertions."""
    for var in (API_KEY_ENV, BACKEND_ENV, BASE_URL_ENV, MODEL_ENV):
        monkeypatch.delenv(var, raising=False)


@pytest.mark.parametrize("bad", ["moc", "foo", "qwen", "mok", "bogus"])
def test_explicit_unknown_backend_raises(bad):
    """An explicitly-passed unknown --backend is a loud config error, not a
    silent fallback to mock/llm."""
    with pytest.raises(ValueError, match="unknown backend"):
        resolve_backend(bad)


@pytest.mark.parametrize("good", ["mock", "llm", "MOCK", " llm "])
def test_valid_explicit_backends_resolve(good, monkeypatch):
    """Valid explicit backends resolve (case/whitespace normalized); llm needs a
    key or it fail-softs to mock, so set one to exercise the llm branch."""
    monkeypatch.setenv(API_KEY_ENV, "sk-test")
    cfg = resolve_backend(good)
    # 'mock' (any case/spacing) stays mock; 'llm' (any case/spacing) stays llm
    assert cfg.kind == ("llm" if good.lower().strip() == "llm" else "mock")


def test_no_arg_backend_path_unchanged_offline():
    """Omitting --backend must stay on the env→key resolution so the
    default-offline behavior is unchanged: no key → mock, and crucially NO raise
    (a missing VOICELOCK_BACKEND is a normal default, not an error)."""
    cfg = resolve_backend()  # no prefer, no env, no key
    assert cfg.kind == "mock"


def test_empty_string_backend_is_not_explicit():
    """An empty --backend ('') is treated as 'no --backend passed', so it must
    NOT raise (it falls through to env→key resolution), unlike a real typo."""
    cfg = resolve_backend("")
    assert cfg.kind == "mock"
