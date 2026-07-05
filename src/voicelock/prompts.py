"""Prompt templates for the LLM backend.

The rewrite is conditioned on the account-voice fingerprint (not a one-shot
"write like me"): the profile's concrete statistics + signature words + real
opener patterns are injected so the model regenerates a flagged region *in that
voice* rather than in a generic "natural" register.
"""

from __future__ import annotations

from .models import VoiceProfile


def _profile_brief(profile: VoiceProfile | None) -> str:
    if profile is None:
        return "（无账号声线指纹，按自然、口语、不套路的风格改写）"
    p = profile
    openers = "、".join(p.opener_hooks[:5]) or "（无）"
    words = "、".join(p.high_freq_tokens[:12]) or "（无）"
    return (
        f"账号声线指纹（account voice fingerprint）：\n"
        f"- 平均句长约 {p.sentence_length.mean:.0f} 字，句长起伏 std≈{p.sentence_length.std:.0f}\n"
        f"- 词汇多样度（type-token ratio）≈ {p.lexical_diversity:.2f}\n"
        f"- emoji 密度 ≈ 每 100 字 {p.emoji_per_100_chars:.1f} 个（请贴近，不要堆叠）\n"
        f"- 感叹/疑问/波浪节奏 ≈ ！{p.exclaim_ratio:.2f} ？{p.question_ratio:.2f} ～{p.wave_ratio:.2f}（每句）\n"
        f"- 该账号真实的开头习惯：{openers}\n"
        f"- 该账号的高频签名词：{words}"
    )


SYSTEM_PROMPT = (
    "你是一个小红书正文『去AI味』改写助手。你的任务是把一句『爆款体/一眼AI』的句子，"
    "改写成指定账号本人声线的自然表达。要求：\n"
    "1. 去掉群呼开头（姐妹们/家人们/宝子们）、烂大街词（绝绝子/yyds/救命/绝了）、"
    "感叹号轰炸、emoji 堆叠、手把手教你/建议收藏 之类的套路。\n"
    "2. 保留原句的信息与意图，只换掉『同质化爆款体外壳』。\n"
    "3. 贴合给定账号声线指纹（句长、emoji 密度、标点节奏、签名词）。\n"
    "4. 只输出改写后的这一句，不要解释、不要加引号、不要加前后缀。"
)


def build_rewrite_prompt(region_text: str, profile: VoiceProfile | None) -> str:
    """Return the user prompt for rewriting a single flagged region."""
    return (
        f"{_profile_brief(profile)}\n\n"
        f"待改写的爆款体句子：\n{region_text}\n\n"
        f"请只输出改写后的这一句（账号本人声线、去AI味）："
    )
