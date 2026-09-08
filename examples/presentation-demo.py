"""Run the offline lexical rewrite loop on shipped synthetic examples."""
from pathlib import Path
import json
from voicelock.voiceprint import build_profile
from voicelock.rewriter import rewrite
from voicelock.config import BackendConfig
profile=build_profile(Path('examples/my-posts.txt').read_text(),account_id='example')
text=Path('examples/draft.txt').read_text()
result=rewrite(text,profile,backend_cfg=BackendConfig(kind='mock'),max_iters=2)
print(json.dumps({'corpus_posts':profile.n_posts,'corpus_chars':profile.n_chars,'backend':result.backend,'before':result.before,'after':result.after,'rule_score_before':result.slop_before,'rule_score_after':result.slop_after,'rewrite_attempts':result.iterations},ensure_ascii=False,indent=2))
