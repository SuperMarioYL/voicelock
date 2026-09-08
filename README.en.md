**English** | [简体中文](README.md)

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/presentation/hero-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/presentation/hero-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/presentation/hero-dark.svg">
  <img src="assets/presentation/hero-light.svg" width="1000" alt="Extract readable writing features from past posts, flag formulaic phrases and punctuation clusters, then rewrite and recheck individual sentences.">
</picture>

**Extract readable writing features from past posts, flag formulaic phrases and punctuation clusters, then rewrite and recheck individual sentences.**

`v0.7.0` · `Python 3.12+` · [Apache-2.0](LICENSE)

[Website](https://voicelock.lei6393.com) · [Demo record](docs/demo-results.json)

## Why use it

Exaggerated openings, repeated trendy phrases and dense emoji can differ from your usual writing. voicelock turns past posts into a statistical profile so you can inspect specific differences and flagged sentences. Voice here means writing features, not recorded speech or voice cloning.

## Architecture

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/presentation/architecture-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/presentation/architecture-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/presentation/architecture-dark.svg">
  <img src="assets/presentation/architecture-light.svg" width="1000" alt="voiceprint uses jieba and text statistics to build VoiceProfile. slop_detector identifies sentence-level rule matches, and rewriter calls the selected backend, rechecks each candidate and keeps a lower-scoring version. The mock backend performs lexical substitutions; llm uses a configured OpenAI-compatible service. Reassembly preserves paragraph gaps.">
</picture>

voiceprint uses jieba and text statistics to build VoiceProfile. slop_detector identifies sentence-level rule matches, and rewriter calls the selected backend, rechecks each candidate and keeps a lower-scoring version. The mock backend performs lexical substitutions; llm uses a configured OpenAI-compatible service. Reassembly preserves paragraph gaps.

Source entry points: [src/voicelock/cli.py](src/voicelock/cli.py) · [src/voicelock/config.py](src/voicelock/config.py) · [src/voicelock/voiceprint.py](src/voicelock/voiceprint.py) · [src/voicelock/slop_detector.py](src/voicelock/slop_detector.py) · [src/voicelock/rewriter.py](src/voicelock/rewriter.py) · [src/voicelock/backends/mock.py](src/voicelock/backends/mock.py) · [src/voicelock/models.py](src/voicelock/models.py)

## Install

Requires Python 3.12+ and uv. The example explicitly selects mock lexical rewriting, so an existing model key does not enable service calls.

```bash
git clone https://github.com/SuperMarioYL/voicelock.git
cd voicelock
uv venv --python 3.12
uv pip install --python .venv/bin/python -e .
```

## Quickstart

Inputs are the repository’s four synthetic posts and draft. The script builds a profile, performs offline lexical rewrites and rechecks. Scores measure current rule matches, not human-rated quality, AI-authorship probability or platform distribution.

```bash
.venv/bin/python examples/presentation-demo.py
```

Complete inputs and execution steps are included in the commands above and the [demo record](docs/demo-results.json).

## Usage

```bash
.venv/bin/voicelock fingerprint --corpus examples/my-posts.txt --account example
.venv/bin/voicelock voice-distance examples/draft.txt --account example
.venv/bin/voicelock audit examples/draft.txt --account example
.venv/bin/voicelock rewrite examples/draft.txt --account example --backend mock
```
Separate posts with blank lines. The CLI requires at least two posts and 200 characters; that is a minimum input check, not a statistical-quality guarantee. `--iters` controls attempts per flagged region.

## Recorded demo

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/presentation/process-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/presentation/process-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/presentation/process-dark.svg">
  <img src="assets/presentation/process-light.svg" width="1000" alt="Inputs are the repository’s four synthetic posts and draft. The script builds a profile, performs offline lexical rewrites and rechecks. Scores measure current rule matches, not human-rated quality, AI-authorship probability or platform distribution.">
</picture>

### Inspect the actual rewrite

The output retains original and rewritten text, rule scores and attempt counts. Lower scores do not guarantee more natural prose.

```text
$ .venv/bin/python examples/presentation-demo.py
{
  "corpus_posts": 4,
  "corpus_chars": 221,
  "backend": "mock",
  "before": "姐妹们！！！这家咖啡馆真的绝绝子😭😭😭\n谁懂啊家人们直接封神yyds！！！\n手把手教你三步找到宝藏咖啡馆，建议收藏码住🔥🔥🔥\n错过血亏，闭眼入不踩雷～～～",
  "after": "这家咖啡馆真的很不错。\n非常好很顶。\n三步找到宝藏咖啡馆，建议收藏码住。\n值得看看，可以放心买不踩雷。",
  "rule_score_before": 100.0,
  "rule_score_after": 0.0,
  "rewrite_attempts": 5
}
```

## Capabilities and integration

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/presentation/integrations-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/presentation/integrations-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/presentation/integrations-dark.svg">
  <img src="assets/presentation/integrations-light.svg" width="1000" alt="fingerprint builds a profile; voice-distance shows statistical consistency and leading difference dimensions; audit flags text; rewrite emits before/after. It does not log in, scrape or publish posts. The llm backend sends relevant text to the configured service.">
</picture>

fingerprint builds a profile; voice-distance shows statistical consistency and leading difference dimensions; audit flags text; rewrite emits before/after. It does not log in, scrape or publish posts. The llm backend sends relevant text to the configured service.



## Configuration

`VOICELOCK_HOME` defaults to `~/.voicelock`; profiles are voice.yaml or voice.<account>.yaml. Backend precedence is --backend, VOICELOCK_BACKEND, then automatic selection based on VOICELOCK_API_KEY. Explicit llm without a key errors; VOICELOCK_BASE_URL and VOICELOCK_MODEL select the service. voice-distance currently displays the top three contributing difference dimensions.

## Roadmap and scope

Statistical profiles, sentence rules, difference breakdowns and two rewrite backends are implemented. Custom rules, profile visualization, collaboration and hosted UI remain future directions.

- The rule score is not an AI detector and cannot establish whether a person or model wrote a text.
- No platform throttling, recommendation or reach effects were validated. Review rewrites for facts, meaning and personal expression.

![Terminal recording](assets/demo.gif) · [Recording script](docs/demo.tape)

## License

[Apache-2.0](LICENSE)
