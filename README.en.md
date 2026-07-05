<div align="right"><sub><b>English</b>&nbsp;&nbsp;⇄&nbsp;&nbsp;<a href="./README.md">简体中文</a></sub></div>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/hero-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="./assets/hero-light.svg">
    <img src="./assets/hero-light.svg" width="880" alt="voicelock — anti-slop taste for 小红书 正文">
  </picture>
</p>

<p align="center"><sub>Rewrite the AI-copilot 爆款体 ("obviously-AI") body text back into your own account voice.</sub></p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT"></a>
  <a href="https://github.com/SuperMarioYL/voicelock/releases"><img src="https://img.shields.io/github/v/release/SuperMarioYL/voicelock" alt="release"></a>
  <a href="https://github.com/SuperMarioYL/voicelock/actions/workflows/ci.yml"><img src="https://github.com/SuperMarioYL/voicelock/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.12-3776AB.svg" alt="Python 3.12">
  <img src="https://img.shields.io/badge/anti--slop-taste-5E5CE6.svg" alt="anti-slop taste">
  <img src="https://img.shields.io/badge/offline-mock%20backend-10A37F.svg" alt="offline mock backend">
</p>

**Your AI copilot's 小红书 body text reads as 爆款体 — the homogenized "obviously-AI" template (group-address openers, hype words, exclamation bombing) the platform 限流s (throttles); voicelock learns your account-voice fingerprint from your own past posts, detects those 爆款体 regions, and rewrites them sentence-by-sentence back into your voice.**

`voicelock` is **anti-slop taste** for 小红书 图文 creators. It is *not* another one-shot "prompt the AI to write like me" — it turns your voice into an **asset you own** (a statistical signature learned from your own past 笔记), then runs a *detect → rewrite-in-voice → re-check* loop to un-slop 爆款体 body text back into your own register. It rides the **anti-slop taste** wave that [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) (57k★, "stops the AI from generating boring, generic slop") lit on the developer side — and adds the half it lacks: the **小红书 正文** surface + a **per-account voice fingerprint**. Offline by default (`mock` backend, zero API key); switch to qwen/doubao/kimi/glm when you want higher-quality rewrites.

<h2><img src="https://api.iconify.design/tabler:topology-star-3.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> Architecture</h2>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/atlas-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="./assets/atlas-light.svg">
    <img src="./assets/atlas-light.svg" width="880" alt="Architecture: post history → voice fingerprint → 爆款体 detection → rewrite-in-voice → un-slopped body text">
  </picture>
</p>

One CLI process, offline-first, no network in the default path:

- **post history → voice fingerprint**: `voiceprint` tokenizes with jieba and derives lexical diversity, sentence-length distribution, emoji cadence, punctuation rhythm, opener habits, and signature words from your OWN past posts into a readable, versionable `VoiceProfile` (stored at `~/.voicelock/voice.yaml`).
- **爆款体 detection**: `slop_detector` runs a lexical rule-set for the homogenized 小红书 openers / template phrases / emoji studding / punctuation bombing, flags sentence-level slop regions, and scores 0–100.
- **rewrite-in-voice**: `rewriter` runs a *rewrite → re-check* loop per flagged region, with either the `mock` (offline lexical) or `llm` (OpenAI-compatible 国产模型) backend, re-checking each rewrite and iterating if it isn't clean enough.

<h2><img src="https://api.iconify.design/tabler:rocket.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> Install & Quickstart</h2>

Cold clone to first visible result in three commands, fully offline, no API key:

```bash
pip install voicelock                                    # or: uvx voicelock (zero-install trial)
voicelock fingerprint --corpus examples/my-posts.txt     # learn a voice fingerprint from your own posts
voicelock rewrite examples/draft.txt                     # rewrite an AI draft back into your voice
```

<details><summary>sample output (rewrite)</summary>

```
╭──────────────── voicelock rewrite ────────────────╮
│ slop  100 → 0   backend=mock   voice-consistency 0.95 │
╰────────────────────────────────────────────────────╯
before   这家咖啡馆真的绝绝子😭😭😭
after    这家咖啡馆真的很不错。
slop     65 → 0  (homogenized_phrase, ×1)
...
╭──────────── rewritten body (去AI味) ────────────╮
│ 这家咖啡馆真的很不错。非常好很顶。三步找到宝  │
│ 藏咖啡馆，建议收藏码住。值得看看，可以放心买  │
│ 不踩雷。                                        │
╰────────────────────────────────────────────────╯
```
</details>

<h2><img src="https://api.iconify.design/tabler:terminal-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> Usage</h2>

Four subcommands cover the whole *build asset → detect → rewrite* flow (see [`examples/`](./examples)):

```bash
# 1. learn the voice fingerprint once, then reuse it — multi-account supported
voicelock fingerprint --corpus my-posts.txt --account main

# 2. just score how "you" a draft sounds (0..1 consistency, higher = more you)
voicelock voice-distance draft.txt --account main

# 3. detect only: flag 爆款体 regions + slop score
voicelock audit draft.txt --account main

# 4. rewrite each region in your voice: before/after diff + slop delta
voicelock rewrite draft.txt --account main
```

Switch to a 国产模型 backend (higher-quality rewrites) by setting three env vars; with no key it auto-falls-back to the offline `mock`:

```bash
export VOICELOCK_API_KEY=sk-...
export VOICELOCK_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1   # qwen example
export VOICELOCK_MODEL=qwen-plus                                             # or doubao / kimi / glm
voicelock rewrite draft.txt --backend llm
```

> Privacy: voicelock only processes **your own pasted/exported public notes** — no scraping, no auto-posting, no session login. Your voice fingerprint stays local; it is an asset you own.

<h2><img src="https://api.iconify.design/tabler:photo.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> Demo</h2>

A 爆款体 draft (slop 87) rewritten sentence-by-sentence back into the account voice, score falling to 12, voice-consistency filling up:

![demo](./assets/demo.gif)

<h2><img src="https://api.iconify.design/tabler:git-compare.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> vs taste-skill</h2>

voicelock is downstream of the same **anti-slop taste** demand as [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill), aimed at a different surface. Honest comparison — taste-skill is genuinely better where it's built for:

| | voicelock | [taste-skill](https://github.com/Leonxlnx/taste-skill) |
|---|:---:|:---:|
| Anti-slop framing | ✓ | ✓ (named the primitive) |
| Surface | 小红书 正文 (creator body text) | coding-agent / dev output |
| Per-account **voice fingerprint** (owned asset) | ✓ | — (reusable taste prompt) |
| 爆款体 (CN-platform) classifier | ✓ | — |
| Detect → rewrite → **re-check loop** | ✓ | — |
| Ecosystem, distribution, star base | new | ✓ 57k★, huge reach |

taste-skill owns the developer anti-slop surface and its distribution dwarfs ours; voicelock builds the 小红书 正文 half it doesn't cover.

<h2><img src="https://api.iconify.design/tabler:adjustments.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> Configuration</h2>

Everything is env-var driven; zero-config and offline by default:

| variable | type | default | meaning |
|---|---|---|---|
| `VOICELOCK_BACKEND` | `mock` \| `llm` | `llm` if a key is set, else `mock` | force a backend |
| `VOICELOCK_API_KEY` | string | *(empty)* | 国产模型 API key; empty → offline mock |
| `VOICELOCK_BASE_URL` | url | dashscope-compatible endpoint | OpenAI-compatible base_url (qwen/doubao/kimi/glm) |
| `VOICELOCK_MODEL` | string | `qwen-plus` | model name |
| `VOICELOCK_HOME` | path | `~/.voicelock` | where the voice fingerprint + config live |

<h2><img src="https://api.iconify.design/tabler:map-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> Roadmap</h2>

- [x] **m1** account-voice fingerprint (`VoiceProfile`) + voice-consistency distance scorer (offline)
- [x] **m2** 爆款体 / homogeneity detection: sentence-level slop regions + before/after slop score
- [x] **m3** rewrite-in-voice loop (mock + llm backends + re-check) + CLI + animated demo
- [ ] richer 爆款体 rule library + user-customizable rule sets
- [ ] visual voice-fingerprint report (export SVG/HTML)
- [ ] hosted no-code tier (non-dev creators) + MCN multi-account team plan (see Pricing)

<h2><img src="https://api.iconify.design/tabler:coin.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> Pricing</h2>

**The v0.1 CLI is free and open source** — it is the demand proof and the foundation the hosted tier builds on, with no paywalled feature.

The real monetization lives in the hosted tier (the same `voiceprint`/`slop_detector`/`rewriter` wrapped as a no-code service):

| tier | for | planned price | what you get |
|---|---|---|---|
| CLI (this repo) | devs / indie creators comfortable in a terminal | free OSS | all v0.1 features, offline mock |
| Solo (hosted) | non-dev creators | ¥19 / mo | cloud voice fingerprint + rewrite quota, no CLI |
| MCN team | multi-account PGC / MCN studios | ¥99 / account / mo | per-account voice + team quota + cross-account consistency dashboard |

> Prices are planned figures: 小红书 MCN tools commonly run ¥hundreds–thousands/mo, so the team plan is set at ¥99/account/mo to land the first few. The hosted tier is post-MVP; this repo ships the asset + loop it wraps.

<h2><img src="https://api.iconify.design/tabler:license.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> License & Contributing</h2>

[MIT](./LICENSE). Issues and PRs welcome — especially new 爆款体 rules and sample voices from different accounts. File one at [Issues](https://github.com/SuperMarioYL/voicelock/issues).

## Share this

```
voicelock — anti-slop taste for 小红书 正文. Learns your account-voice fingerprint
from your own posts and rewrites AI drafts in your voice. Offline, no API key.
https://github.com/SuperMarioYL/voicelock
```

<p align="center"><sub><a href="./LICENSE">MIT</a> © 2026 SuperMarioYL</sub></p>
