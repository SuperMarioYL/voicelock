# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/SuperMarioYL/voicelock/releases/tag/v0.1.0
