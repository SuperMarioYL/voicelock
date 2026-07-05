# examples

Sample inputs for the voicelock 10-minute happy path — all offline, no API key.

| file | what it is |
|---|---|
| `my-posts.txt` | a small **发布历史** corpus (the creator's OWN past 笔记), one note per blank-line block. `fingerprint` learns your `VoiceProfile` from this. |
| `draft.txt` | a homogeneous **爆款体** draft (the kind an AI 副驾 emits). `audit` flags it; `rewrite` regenerates it in your voice. |

```bash
# 1. learn your voice fingerprint
voicelock fingerprint --corpus examples/my-posts.txt

# 2. flag the 爆款体 slop regions in an AI draft
voicelock audit examples/draft.txt

# 3. rewrite each region in your own voice (before/after + slop score)
voicelock rewrite examples/draft.txt
```
