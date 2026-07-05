"""Tests for the account-voice fingerprint (milestone m1).

All offline, mock/lexical only — no API key, no network.
"""

from __future__ import annotations

from voicelock.voiceprint import (
    build_profile,
    load_profile,
    save_profile,
    voice_consistency,
    voice_distance,
)

# A small, calm, personal-voice corpus (the creator's OWN past 笔记).
CALM_CORPUS = """\
今天去了家门口新开的咖啡馆，坐了一下午。
豆子是耶加雪菲，酸度很干净，配他家的核桃可颂刚好。
店里人不多，适合带本书慢慢待着。

周末把阳台的绿萝换了个大一点的盆。
根系已经绕满了旧盆，换完浇透水，叶子第二天就精神了。
养植物这件事，急不得。

记录一下这周做的三顿家常菜。
番茄土豆炖牛腩、清炒时蔬、还有一锅杂粮饭。
都不难，重点是火候和耐心。
"""

# Text that clearly does NOT sound like the calm corpus (loud 爆款体).
OFF_VOICE = (
    "姐妹们！！！这家咖啡馆真的绝绝子救命😭😭😭 "
    "谁懂啊家人们直接封神yyds！！！"
)


def test_fingerprint_is_deterministic():
    p1 = build_profile(CALM_CORPUS, account_id="tester")
    p2 = build_profile(CALM_CORPUS, account_id="tester")
    assert p1.to_dict() == p2.to_dict()
    # sanity: real content produced non-trivial stats
    assert p1.n_posts == 3
    assert p1.n_chars > 0
    assert 0.0 < p1.lexical_diversity <= 1.0
    assert p1.sentence_length.mean > 0
    assert len(p1.signature_vec) == 8


def test_signature_words_exclude_generic_stopwords():
    p = build_profile(CALM_CORPUS, account_id="tester")
    # the very generic tokens should not appear as "signature" words
    for stop in ("的", "了", "我", "很"):
        assert stop not in p.high_freq_tokens


def test_same_voice_scores_closer_than_off_voice():
    profile = build_profile(CALM_CORPUS, account_id="tester")

    # a held-out sentence in the SAME calm voice
    same_voice = "晚上煮了碗清汤面，加了个溏心蛋，简单但很舒服。"

    d_same = voice_distance(profile, same_voice)
    d_off = voice_distance(profile, OFF_VOICE)

    # same-voice text must be measurably closer to the profile than off-voice
    assert d_same < d_off
    # and expressed as consistency, same-voice is the higher score
    assert voice_consistency(profile, same_voice) > voice_consistency(profile, OFF_VOICE)


def test_distance_is_bounded_0_1():
    profile = build_profile(CALM_CORPUS, account_id="tester")
    for txt in (CALM_CORPUS, OFF_VOICE, "随便一句话。", ""):
        d = voice_distance(profile, txt)
        assert 0.0 <= d <= 1.0


def test_profile_roundtrips_through_yaml(tmp_path):
    profile = build_profile(CALM_CORPUS, account_id="tester")
    path = tmp_path / "voice.yaml"
    save_profile(profile, path)
    assert path.exists()

    reloaded = load_profile(path)
    assert reloaded.account_id == profile.account_id
    assert reloaded.n_posts == profile.n_posts
    assert reloaded.high_freq_tokens == profile.high_freq_tokens
    # scoring is stable across a save/load cycle (profile is stored compactly, so
    # allow tiny rounding drift from the on-disk float precision)
    probe = "早上冲了杯手冲，配吐司，安安静静开始一天。"
    assert abs(voice_distance(profile, probe) - voice_distance(reloaded, probe)) < 1e-4
