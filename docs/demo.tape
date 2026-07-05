# voicelock demo — the 10-minute happy path, driven against the real CLI.
# Render locally or in CI:  vhs docs/demo.tape   ->   assets/demo.gif
#
# Requires: vhs, ttyd, ffmpeg, and `pip install -e .` (voicelock on PATH).

Output assets/demo.gif

Set Shell "bash"
Set FontSize 20
Set Width 1200
Set Height 760
Set Padding 24
Set Theme "Catppuccin Mocha"
Set TypingSpeed 45ms

# isolate the voice store so the demo is reproducible
Hide
Type "export VOICELOCK_HOME=$(mktemp -d)"
Enter
Type "clear"
Enter
Show

# 1. learn your account-voice fingerprint from your own 发布历史
Type "voicelock fingerprint --corpus examples/my-posts.txt"
Sleep 600ms
Enter
Sleep 3s

# 2. audit an AI draft — flag the 爆款体 slop regions + slop score
Type "voicelock audit examples/draft.txt"
Sleep 600ms
Enter
Sleep 3.5s

# 3. rewrite each region IN your voice — before/after + slop 去AI味
Type "voicelock rewrite examples/draft.txt"
Sleep 600ms
Enter
Sleep 5s

Sleep 2s
