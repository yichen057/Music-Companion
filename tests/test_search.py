import pytest

from src.recommender import load_songs
from src.intent import apply_intent_to_profile, parse_intent_rule_based, validate_intent
from src.search import (
    build_profile_from_seed_song,
    find_song_by_query,
    recommend_similar_songs,
)


def load_catalog():
    return load_songs("data/songs.csv")


def test_find_song_by_query_matches_exact_title():
    songs = load_catalog()

    song, confidence = find_song_by_query("Library Rain", songs)

    assert song["title"] == "Library Rain"
    assert confidence == 1.0


def test_find_song_by_query_matches_partial_title():
    songs = load_catalog()

    song, confidence = find_song_by_query("library", songs)

    assert song["title"] == "Library Rain"
    assert confidence > 0.0


def test_build_profile_from_seed_song_uses_seed_metadata():
    songs = load_catalog()
    seed_song, _ = find_song_by_query("Library Rain", songs)

    profile = build_profile_from_seed_song(seed_song)

    assert profile["favorite_genre"] == "lofi"
    assert profile["favorite_mood"] == "chill"
    assert profile["target_energy"] == seed_song["energy"]
    assert profile["preferred_language"] == "instrumental"


def test_recommend_similar_songs_excludes_seed_song():
    songs = load_catalog()

    seed_song, confidence, recommendations = recommend_similar_songs(
        "Library Rain", songs, k=5
    )

    assert seed_song["title"] == "Library Rain"
    assert confidence == 1.0
    assert len(recommendations) == 5
    assert all(song["id"] != seed_song["id"] for song, _, _ in recommendations)


def test_find_song_by_query_raises_for_missing_song():
    songs = load_catalog()

    with pytest.raises(ValueError, match="No song found"):
        find_song_by_query("this song does not exist", songs, min_confidence=0.9)


def test_rule_based_intent_parser_extracts_common_adjustments():
    intent = parse_intent_rule_based("more energetic but still instrumental for studying")

    assert intent["energy_delta"] > 0
    assert intent["required_language"] == "instrumental"
    assert intent["requires_instrumental"] is True
    assert "focused" in intent["preferred_tags"]


def test_validate_intent_clamps_unsafe_values():
    intent = validate_intent({
        "energy_delta": 99,
        "preferred_mood": "unknown mood",
        "required_language": "klingon",
        "confidence": 5,
    })

    assert intent["energy_delta"] == 0.3
    assert intent["preferred_mood"] is None
    assert intent["required_language"] is None
    assert intent["confidence"] == 1.0


def test_apply_intent_to_profile_adjusts_seed_profile():
    songs = load_catalog()
    seed_song, _ = find_song_by_query("Library Rain", songs)
    profile = build_profile_from_seed_song(seed_song)
    intent = parse_intent_rule_based("more energetic but still instrumental for studying")

    adjusted = apply_intent_to_profile(profile, intent)

    assert adjusted["target_energy"] > profile["target_energy"]
    assert adjusted["preferred_language"] == "instrumental"
    assert adjusted["prefers_instrumental"] is True
    assert "focused" in adjusted["liked_mood_tags"]


def test_recommend_similar_songs_accepts_intent_without_gemini():
    songs = load_catalog()

    seed_song, confidence, recommendations = recommend_similar_songs(
        "Library Rain",
        songs,
        k=3,
        intent_text="more energetic but still instrumental for studying",
        use_gemini=False,
    )

    assert seed_song["title"] == "Library Rain"
    assert confidence == 1.0
    assert len(recommendations) == 3


def test_rule_based_parser_can_mark_gemini_fallback_reason():
    intent = parse_intent_rule_based(
        "more energetic",
        source="fallback_rule_based",
        fallback_reason="TimeoutError",
        fallback_detail="request timed out",
    )

    assert intent["source"] == "fallback_rule_based"
    assert intent["fallback_reason"] == "TimeoutError"
    assert intent["fallback_detail"] == "request timed out"
