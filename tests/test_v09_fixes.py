"""Regression tests for the v0.9.0 release.

Pins fix-inline-text-enametoolong: _read_source's file-existence probe is
best-effort. On Linux, ``Path.is_file()`` on a name whose single component
exceeds NAME_MAX (255 bytes) raises ``OSError``/``ENAMETOOLONG`` instead of
returning False (pathlib only ignores ENOENT/ENOTDIR/EBADF/ELOOP; macOS raises
ENOENT, which IS ignored — exactly why the suite passed locally while GitHub
CI (ubuntu) failed on every push since v0.5.0). The probe crashing turned any
pasted draft/corpus longer than ~85 CJK chars into
"错误：[Errno 36] File name too long" + exit 1 on fingerprint / audit /
rewrite / voice-distance.

All offline, no API key, no network.
"""

from __future__ import annotations

import errno
from pathlib import Path

import pytest
from typer.testing import CliRunner

from voicelock.cli import _read_source, app
from voicelock.config import API_KEY_ENV, BACKEND_ENV, BASE_URL_ENV, MODEL_ENV

runner = CliRunner()

# > NAME_MAX (255 bytes) of UTF-8: a single-line inline draft whose stat()
# probe Linux refuses with ENAMETOOLONG (macOS raises ENOENT, ignored).
LONG_INLINE_DRAFT = (
    "今天去了家门口新开的咖啡馆，坐了一下午，豆子是耶加雪菲，酸度很干净，配他家的核桃可颂刚好，"
    "店里人不多，适合带一本书慢慢待着，下午的光线透过玻璃落在木桌上，翻几页书再喝一口，确实舒服，"
    "老板人也好，临走还送了一小杯新豆的手冲让我试试，回甘很明显，周末还会再来。"
)


@pytest.fixture(autouse=True)
def _isolated_voicelock_env(tmp_path, monkeypatch):
    monkeypatch.setenv("VOICELOCK_HOME", str(tmp_path))
    for var in (API_KEY_ENV, BACKEND_ENV, BASE_URL_ENV, MODEL_ENV):
        monkeypatch.delenv(var, raising=False)


# --------------------------------------------------------------------------- #
# fix-inline-text-enametoolong
# --------------------------------------------------------------------------- #
def test_read_source_probe_oserror_is_treated_as_not_a_file(monkeypatch):
    """The existence probe must be best-effort: an OSError raised by
    Path.is_file() (the Linux ENAMETOOLONG behavior for >255-byte inline text)
    is treated as 'not a file' and the input is returned as inline content.
    Fails on the pre-fix source on EVERY platform (the probe's OSError
    propagated out of _read_source)."""
    assert len(LONG_INLINE_DRAFT.encode("utf-8")) > 255

    def _probe_raises(self, *, follow_symlinks=True):
        raise OSError(errno.ENAMETOOLONG, "File name too long")

    monkeypatch.setattr(Path, "is_file", _probe_raises)
    assert _read_source(LONG_INLINE_DRAFT) == LONG_INLINE_DRAFT


def test_fingerprint_accepts_long_inline_corpus():
    """The v0.5.0 corpus-adequacy tests feed a >255-byte inline corpus; on Linux
    the pre-fix probe crashed with '错误：[Errno 36] File name too long' and
    exited 1 (CI red since v0.5.0). An adequate long inline corpus must
    fingerprint and save with exit 0 (test_v05/test_v07 pin the same path)."""
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
    assert len(corpus.encode("utf-8")) > 255
    result = runner.invoke(app, ["fingerprint", "--corpus", corpus])
    assert result.exit_code == 0, f"fingerprint failed: {result.output}"
    assert "声线指纹已保存" in result.output


def test_audit_accepts_long_single_line_inline_draft():
    """A >255-byte SINGLE-LINE inline CJK draft (no newline, no ASCII suffix)
    is inline content: audit must score it, not crash with 'File name too
    long' (the pre-fix Linux behavior)."""
    result = runner.invoke(app, ["audit", LONG_INLINE_DRAFT])
    assert result.exit_code == 0, f"audit failed: {result.output}"
    assert "slop 分数" in result.output


def test_missing_ascii_path_still_raises_after_probe_guard():
    """The FileNotFoundError contract is untouched: a short missing ASCII path
    still raises (the probe guard only swallows probe ERRORS, not a False
    result)."""
    with pytest.raises(FileNotFoundError, match="找不到文件"):
        _read_source("my-posts.txt")
