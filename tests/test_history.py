import pytest

from src.history import (
    aggregate_user_history,
    build_taste_profile,
    load_albums,
    load_listening_history,
    recommend_albums_from_profile,
    recommend_songs_from_history,
    summarize_taste,
)
from src.recommender import load_songs


def load_fixture_data():
    songs = load_songs("data/songs.csv")
    history = load_listening_history("data/listening_history.csv")
    albums = load_albums("data/albums.csv")
    return songs, history, albums


def test_aggregate_user_history_extracts_top_preferences():
    songs, history, _ = load_fixture_data()

    stats = aggregate_user_history("user_001", history, songs)

    assert stats["user_id"] == "user_001"
    assert stats["top_genre"] == "lofi"
    assert stats["top_language"] == "instrumental"
    assert stats["prefers_instrumental"] is True


def test_build_taste_profile_from_history_stats():
    songs, history, _ = load_fixture_data()
    stats = aggregate_user_history("user_001", history, songs)

    profile = build_taste_profile(stats)

    assert profile["favorite_genre"] == "lofi"
    assert profile["preferred_language"] == "instrumental"
    assert 0.0 <= profile["target_energy"] <= 1.0
    assert "dreamy" in profile["liked_mood_tags"]


def test_recommend_songs_from_history_excludes_played_songs():
    songs, history, _ = load_fixture_data()

    stats, profile, recommendations = recommend_songs_from_history(
        "user_001", history, songs, k=3
    )

    played_ids = {song_id for song_id, _ in stats["top_songs"]}
    assert profile["favorite_genre"] == "lofi"
    assert len(recommendations) == 3
    assert all(song["id"] not in played_ids for song, _, _ in recommendations)


def test_recommend_albums_from_profile_returns_ranked_albums():
    songs, history, albums = load_fixture_data()
    stats = aggregate_user_history("user_001", history, songs)
    profile = build_taste_profile(stats)

    recommendations = recommend_albums_from_profile(profile, albums, k=3)

    assert len(recommendations) == 3
    assert recommendations[0][1] >= recommendations[-1][1]
    assert recommendations[0][0]["genre"] in {"lofi", "ambient"}


def test_summarize_taste_mentions_user_and_genre():
    songs, history, _ = load_fixture_data()
    stats = aggregate_user_history("user_001", history, songs)
    profile = build_taste_profile(stats)

    summary = summarize_taste(stats, profile)

    assert "user_001" in summary
    assert "lofi" in summary


def test_aggregate_user_history_raises_for_missing_user():
    songs, history, _ = load_fixture_data()

    with pytest.raises(ValueError, match="No listening history"):
        aggregate_user_history("missing_user", history, songs)
