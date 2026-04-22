import pytest

from src.history import load_albums, load_listening_history
from src.recommender import load_songs
from src.wrapped import (
    build_recap_stats,
    build_wrapped_report,
    deterministic_recap_summary,
    event_in_period,
    match_album_for_song,
)


def load_fixture_data():
    songs = load_songs("data/songs.csv")
    history = load_listening_history("data/listening_history.csv")
    albums = load_albums("data/albums.csv")
    return songs, history, albums


def test_event_in_period_filters_month_and_year():
    event = {"played_at": "2026-04-15T21:30:00"}

    assert event_in_period(event, "year", 2026) is True
    assert event_in_period(event, "month", 2026, 4) is True
    assert event_in_period(event, "month", 2026, 5) is False
    assert event_in_period(event, "year", 2025) is False


def test_build_recap_stats_returns_top_songs_artists_and_albums():
    songs, history, albums = load_fixture_data()

    stats = build_recap_stats("user_001", history, songs, albums, "year", 2026)

    assert stats["user_id"] == "user_001"
    assert stats["period_label"] == "2026"
    assert stats["top_songs"][0]["title"] == "Focus Flow"
    assert stats["top_artists"][0][0] == "LoRoom"
    assert stats["top_albums"]
    assert stats["average_energy"] < 0.5


def test_monthly_recap_requires_matching_history():
    songs, history, albums = load_fixture_data()

    with pytest.raises(ValueError, match="No listening history"):
        build_recap_stats("user_001", history, songs, albums, "month", 2026, 5)


def test_deterministic_recap_summary_is_grounded_in_stats():
    songs, history, albums = load_fixture_data()
    stats = build_recap_stats("user_001", history, songs, albums, "month", 2026, 4)

    summary = deterministic_recap_summary(stats)

    assert summary["source"] == "deterministic"
    assert "user_001" in summary["summary"]
    assert stats["top_songs"][0]["title"] in summary["summary"]


def test_build_wrapped_report_uses_deterministic_summary_without_gemini():
    songs, history, albums = load_fixture_data()

    report = build_wrapped_report(
        "user_001",
        history,
        songs,
        albums,
        period="year",
        year=2026,
        use_gemini=False,
    )

    assert report["stats"]["top_songs"]
    assert report["summary"]["source"] == "deterministic"


def test_match_album_prefers_same_artist():
    songs, _, albums = load_fixture_data()
    song = next(item for item in songs if item["artist"] == "LoRoom")

    album = match_album_for_song(song, albums)

    assert album["artist"] == "LoRoom"
