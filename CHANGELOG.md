# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] - 2026-09-08

Release-traceability fix — a single correctness fix that brings every
secondary version surface back into lockstep with the shipped code and
restores CHANGELOG contiguity. No behavior change to the 去AI味
detect/rewrite/voice-distance pipeline.

### Fixed
- `web/site.json` `content_version` is no longer frozen behind the shipped
  tag. At the v0.7.0 tag the primary version surfaces (VERSION,
  `pyproject.toml` `version`, `src/voicelock/__init__.py` `__version__`, and
  the `voicelock version` CLI output) all read `0.7.0`, but the v0.7.0 tag's
  `web/site.json` still carried `"content_version": "v0.3.0"` — so the live
  site (voicelock.lei6393.com) advertised a v0.3.0 content version while the
  release shipped as v0.7.0. Every `content_version` field in `web/site.json`
  (the top-level field, the `meta.content_version` field, and the
  `footer.tag` version prefix) is now bumped to `v0.8.0` in lockstep with
  every other surface so the site-refresh step's single source of truth tracks
  the shipped release. A past iteration finding holds: a bump that touches only
  VERSION re-opens the drift, so ALL surfaces (VERSION, pyproject, `__init__`,
  CLI var, every `site.json` content_version field) are bumped together every
  release.
- `CHANGELOG.md` is now contiguous and fully link-referenced. It listed
  `## [0.7.0]`, `## [0.6.0]`, then jumped straight to `## [0.4.0]`, omitting a
  `## [0.5.0]` section even though `v0.5.0` is a real shipped tag
  (2026-08-18, three correctness fixes); the bottom link-reference list
  carried `[0.6.0]`, `[0.4.0]`, `[0.3.0]`, `[0.2.0]`, `[0.1.0]` but was missing
  both `[0.5.0]` and `[0.7.0]`, so those headings rendered as literal
  bracket-text rather than release links. A `## [0.5.0] - 2026-08-18` section
  is backfilled between `[0.6.0]` and `[0.4.0]` (documenting the v0.5.0
  fixes: reject bogus `VOICELOCK_BACKEND` env values, count/keep ZWJ-joined
  emoji as one cluster, guard a too-small fingerprint corpus), and the missing
  `[0.5.0]` / `[0.7.0]` link references are restored alongside the new
  `[0.8.0]` reference.

## [0.7.0] - 2026-08-29

Bugfix + feature release — two correctness fixes and one in-scope feature,
further de-risking and enriching the core 去AI味 rewrite + audit UX.

### Fixed
- `_read_source` now raises `FileNotFoundError` for a missing CJK-named file
  with an ASCII extension (e.g. `我的笔记.txt`, `小红书笔记.md`) instead of
  silently treating the filename string as inline text. The v0.3.0 CJK
  exemption in the path-like guard suppressed the file-not-found check for any
  input containing CJK, so `voicelock audit 我的笔记.txt` with a missing file
  silently audited the filename string — the `audit`, `rewrite`, and
  `voice-distance` commands have no secondary guard, so the filename string was
  silently processed with no "file not found" signal. The fix checks for an
  all-ASCII file extension (`.txt`, `.md`, …) and raises even when CJK is
  present in the stem, while preserving the CJK exemption for inline text with
  CJK dot-suffixes (`一句话.好的`) and slash-bearing CJK (`他/她 都可以`).
- `mock._thin_emoji` now uses round-half-up (`int(x + 0.5)`) instead of Python's
  banker's rounding (`round()`) when computing the per-region emoji keep-target.
  `round(0.5)` returned 0 (round-half-to-even), so a 10-char rewritten region
  with `emoji_per_100_chars=5.0` had `target=0` and dropped ALL emoji — while
  an 11-char region kept one (`round(0.55)=1`). This inconsistent boundary
  produced unnatural emoji cadence in the rewritten 正文. Round-half-up makes
  a 0.5 allowance keep one, not zero.

### Added
- `voice_distance_breakdown` function in `voiceprint.py` and a per-dimension
  breakdown table in the `voice-distance` CLI command. The breakdown shows the
  top-3 dimensions where the draft diverges most from the account voice
  (e.g. emoji density, sentence length, punctuation rhythm), each with its
  absolute delta and fractional contribution to the total distance. This
  surfaces the per-dimension comparison data that `voice_distance` already
  computed but discarded, helping the creator understand WHY their draft is
  off-voice — directly supporting the 去AI味 goal. The `audit` command's
  display is unchanged (compact headline score only).

## [0.6.0] - 2026-08-22

Bugfix release — three correctness fixes folded in from the v0.6.0 amendment,
all de-risking the core 去AI味 rewrite UX.

### Fixed
- `count_emoji` now counts a regional-indicator flag emoji (e.g. 🇨🇳) as one
  cluster, not two. A flag is two regional-indicator codepoints (U+1F1E8 then
  U+1F1F3) with no ZWJ joiner, and each indicator sat in `_EMOJI_BASE` (via the
  `\U0001F1E6-\U0001F1FF` range), so the `_EMOJI_CLUSTER` pattern matched each
  indicator as a separate base: `count_emoji` on one flag returned 2. This (a)
  inflated `emoji_per_100_chars` (one flag in a short corpus scored ~11.76
  instead of ~5.88), (b) made the slop detector false-flag a single flag as
  emoji-stacking ×2 (pushing a 姐妹们+flag+闭眼入 sentence's slop score to
  100), and (c) in `mock._thin_emoji` with `target=1` kept only the first
  indicator and dropped the second, so `rewrite` on a flag-bearing slop shell
  returned a lone first regional indicator plus `可以放心买。` — a broken
  lone-indicator render in the rewritten 正文, the same mangle class the
  v0.5.0 ZWJ fix addressed but for flags. A regional-indicator-pair
  alternative is now tried before the single-base path (the shared pattern is
  imported by `backends/mock.py`, so counting and thinning get the fix in one
  place).
- `resolve_backend` now raises `ValueError` when the `llm` backend is
  requested explicitly (`--backend llm` or `VOICELOCK_BACKEND=llm`) with no
  `VOICELOCK_API_KEY` configured, instead of silently flipping to `mock`. The
  fallback only fired for explicit requests (the auto-select path never
  reaches it), so a user who explicitly asks for LLM rewrites silently got
  mock-quality output with only a dim `backend=mock` line as a hint — the same
  silent-misconfiguration-of-the-core-rewrite-backend class the v0.3.0/v0.5.0
  fixes made loud for unknown values. The no-arg/no-env auto-select path
  (`kind = llm-if-key-else-mock`) is untouched, so default-offline behavior is
  unchanged; the CLI surfaces the raise as a clean red message + exit 1.
- The CLI commands now catch the whole `OSError` family from `_read_source`'s
  `read_text()` (not just `FileNotFoundError`), so an existing-but-unreadable
  file (0000 perms → `PermissionError`) exits 1 with a clean red message
  instead of a raw Python traceback. `Path.is_file()` checks file *type*, not
  readability, so an unreadable file passed the check and `read_text` failed;
  the `_clean_user_errors` catch is broadened from
  `(FileNotFoundError, ValueError)` to `(OSError, ValueError)`, completing the
  v0.4.0 clean-error path for the entire `OSError` family
  (`FileNotFoundError`, `PermissionError`, `IsADirectoryError`).

## [0.5.0] - 2026-08-18

Bugfix release — three correctness fixes folded in from the v0.5.0 amendment,
all de-risking the core 去AI味 detect/rewrite/fingerprint pipeline.

### Fixed
- `resolve_backend` now raises `ValueError` on a bogus non-empty
  `VOICELOCK_BACKEND` env value (a typo like `moc`, or `qwen` / `foo`) instead
  of silently flipping to the opposite backend when a key happens to be set.
  With `VOICELOCK_API_KEY` configured, a typo'd `VOICELOCK_BACKEND=moc` would
  otherwise resolve to `llm` and make silent network calls against the user's
  key — the same silent-misconfiguration-of-the-core-rewrite-backend class the
  v0.3.0 fix made loud for explicit `--backend` values. An empty/unset
  `VOICELOCK_BACKEND` still falls through to the key-based default, so the
  default-offline behavior is unchanged.
- `count_emoji` / `mock._thin_emoji` now treat a ZWJ-joined emoji run (e.g.
  the family emoji 👨‍👩‍👧‍👦 = man+ZWJ+woman+ZWJ+girl+ZWJ+boy) as ONE logical
  cluster for both counting and thinning, instead of over-counting it as four
  codepoints and, in `_thin_emoji` with `target=1`, keeping only the first
  pictograph plus dangling `U+200D` joiners — which mangled the rewritten 正文
  with orphaned ZWJ control chars (`👨\u200d\u200d\u200d`). The shared
  `_EMOJI_CLUSTER` pattern now matches a whole ZWJ-joined run as one unit, so
  counting and thinning agree and the logical emoji survives intact.
- The `fingerprint` command now refuses a too-small corpus (`n_posts < 2` or
  `n_chars < 200`) with a clear "语料太少，声线指纹不可靠" message and exit 1,
  instead of silently producing a meaningless ~0.99 voice profile (a one-char
  "好" corpus scored a 爆款体 draft ~0.99). A creator who under-feeds the
  fingerprint gets a loud refusal here instead of silently-deployed noise into
  downstream `audit` / `rewrite` / `voice-distance`.

## [0.4.0] - 2026-08-14

Bugfix release — two correctness fixes folded in from the v0.4.0 amendment,
both de-risking the core 去AI味 rewrite UX for a re-launch.

### Fixed
- `rewrite` now preserves the original paragraph structure of a draft in its
  `after` output. Previously `_reassemble` rebuilt the after-text by joining
  `split_sentences(text)` with `""`, and `split_sentences` strips each sentence
  and filters empties — so every `\n` / `\n\n` paragraph separator and
  inter-sentence whitespace was discarded, even for a clean draft with zero
  slop regions (a 3-paragraph clean draft returned `slop_before==
  slop_after==0.0`, `per_region==[]`, yet `before != after` because the
  blank-line paragraph breaks were gone). The shipped 改写后正文 Panel and the
  before/after diff therefore mangled a 小红书 creator's paragraph structure
  for any multi-paragraph draft — the common 正文 case. `_reassemble` now
  locates each (stripped) sentence's span in the original text and rebuilds by
  copying the original gap text between sentence spans verbatim, substituting
  only the rewritten sentences by index; the no-rewrite path is byte-identical
  to the original text (`after == before` for a clean draft).
- The CLI commands now catch the `FileNotFoundError` / `ValueError` raised by
  the v0.2/v0.3 fixes and print a clean red message with exit code 1, instead
  of letting them propagate as a raw Rich-rendered Python traceback. The #1
  CLI mistake — `voicelock fingerprint --corpus my-post.txt` with a typo'd
  path — plus bad `--account` (path-traversal-style value) and unknown
  `--backend` values now surface as a clean error, not an unhandled traceback,
  for the non-dev creator audience.

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

[0.8.0]: https://github.com/SuperMarioYL/voicelock/releases/tag/v0.8.0
[0.7.0]: https://github.com/SuperMarioYL/voicelock/releases/tag/v0.7.0
[0.6.0]: https://github.com/SuperMarioYL/voicelock/releases/tag/v0.6.0
[0.5.0]: https://github.com/SuperMarioYL/voicelock/releases/tag/v0.5.0
[0.4.0]: https://github.com/SuperMarioYL/voicelock/releases/tag/v0.4.0
[0.3.0]: https://github.com/SuperMarioYL/voicelock/releases/tag/v0.3.0
[0.2.0]: https://github.com/SuperMarioYL/voicelock/releases/tag/v0.2.0
[0.1.0]: https://github.com/SuperMarioYL/voicelock/releases/tag/v0.1.0
