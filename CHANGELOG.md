# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-08-07

Bugfix release — three correctness fixes folded in from the v0.3.0 amendment.

### Fixed
- `voice_distance` / `voice_consistency` now return maximal distance (1.0) and
  zero consistency for an empty or whitespace-only draft, instead of a
  meaningless ~0.67 positive score that fell out of comparing against an
  all-zero signature vector (`[0.0]*8`). This stops `rewrite` of a pure 爆款体
  shell whose regions all drop to empty from reporting a fake
  `voice_consistency_after=0.67`, and keeps `audit` / `voice-distance` honest on
  empty drafts.
- `_read_source` no longer over-rejects single-line CJK inline drafts that merely
  contain a slash or a dot-suffix (a date like `2026/07/06 总结`, a gender slash
  `他/她 都可以`, or `一句话.好的`) as a missing file. Only path-like inputs
  with **no CJK** now raise `FileNotFoundError`; the `Path(...).is_file()`
  short-circuit stays first so genuine CJK-named files still read correctly.
- `resolve_backend` now raises `ValueError` on an explicit but unknown
  `--backend` value (a typo like `moc`, or `foo` / `qwen`) instead of silently
  falling back to `mock` / `llm`. The no-arg path (`--backend` omitted) keeps the
  existing env→key resolution, so the default-offline behavior is unchanged.

## [0.2.0] - 2026-08-02

Bugfix release (previously shipped without a changelog entry or a version bump).

### Fixed
- ASCII `!` exclamation bombing (`好货!!!!闭眼入`) is now flagged by the
  感叹号轰炸 rule (`r"[!！]{2,}"`), mirroring the ASCII+full-width 问号轰炸 rule.
- `account_id` is validated at the `voice_path` boundary against
  `[A-Za-z0-9_-]+`, so a path-traversal value like `--account ../../etc/passwd`
  cannot escape `~/.voicelock` via save/load_profile.
- A typo'd or missing `--corpus` file path now raises `FileNotFoundError` instead
  of being silently fingerprinted as the filename string.

### Changed
- License adopted as Apache-2.0 across LICENSE, metadata, and README badge.

## [0.1.0] - 2026-07-06

First public release — offline-first CLI, no API key required.

### Added
- `voicelock fingerprint --corpus my-posts.txt` — learn a per-account
  **voice fingerprint** (`VoiceProfile`) from your own 发布历史 corpus and save
  it as an owned asset at `~/.voicelock/voice.yaml`.
- `voicelock voice-distance draft.txt` — score how close a draft is to your
  account voice (0..1 consistency).
- `voicelock audit draft.txt` — flag sentence-level **爆款体 / homogeneity**
  slop regions and print a 0..100 slop score with per-region reasons.
- `voicelock rewrite draft.txt` — the regenerate-slop-region loop: rewrite each
  flagged region **in your own voice**, re-check it, and print a before/after
  diff with `slop_before → slop_after` and voice-consistency.
- Two backends behind one interface: `mock` (offline, deterministic, lexical —
  the zero-config default) and `llm` (OpenAI-compatible 国产模型: qwen / doubao /
  kimi / glm via `VOICELOCK_API_KEY` + `VOICELOCK_BASE_URL`).
- Bilingual README (zh-primary + English sibling), animated hero/atlas SVGs,
  and a rendered demo GIF.

[0.3.0]: https://github.com/SuperMarioYL/voicelock/releases/tag/v0.3.0
[0.2.0]: https://github.com/SuperMarioYL/voicelock/releases/tag/v0.2.0
[0.1.0]: https://github.com/SuperMarioYL/voicelock/releases/tag/v0.1.0
