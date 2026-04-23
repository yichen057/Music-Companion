import pytest

from src.recommender import load_songs
from src.sheet_music import (
    deterministic_sheet_explanation,
    generate_sheet_explanation,
    load_sheet_music,
    rank_sheet_music,
    score_sheet_music,
    validate_sheet_summary,
)


def load_fixture_data():
    songs = load_songs("data/songs.csv")
    sheets = load_sheet_music("data/sheet_music.csv")
    return songs, sheets


def test_load_sheet_music_parses_metadata():
    _, sheets = load_fixture_data()

    assert sheets
    assert sheets[0]["sheet_id"] == 201
    assert sheets[0]["instrument"] == "piano"
    assert sheets[0]["beginner_friendly"] is True


def test_rank_sheet_music_matches_requested_instrument_and_song():
    songs, sheets = load_fixture_data()

    seed_song, confidence, recommendations = rank_sheet_music(
        "Library Rain", "piano", songs, sheets, difficulty="beginner", k=3
    )

    assert seed_song["title"] == "Library Rain"
    assert confidence == 1.0
    assert recommendations[0][0]["song_title"] == "Library Rain"
    assert recommendations[0][0]["instrument"] == "piano"
    assert recommendations[0][0]["difficulty"] == "beginner"


def test_rank_sheet_music_filters_to_guitar():
    songs, sheets = load_fixture_data()

    _, _, recommendations = rank_sheet_music(
        "Focus Flow", "guitar", songs, sheets, difficulty="beginner", k=2
    )

    assert recommendations
    assert all(sheet["instrument"] == "guitar" for sheet, _, _ in recommendations)


def test_score_sheet_music_rewards_difficulty_proximity():
    songs, sheets = load_fixture_data()
    song = next(item for item in songs if item["title"] == "Library Rain")
    beginner_sheet = next(item for item in sheets if item["sheet_id"] == 201)

    beginner_score, _ = score_sheet_music(beginner_sheet, song, "piano", "beginner")
    advanced_score, _ = score_sheet_music(beginner_sheet, song, "piano", "advanced")

    assert beginner_score > advanced_score


def test_rank_sheet_music_rejects_unsupported_instrument():
    songs, sheets = load_fixture_data()

    with pytest.raises(ValueError, match="Instrument"):
        rank_sheet_music("Library Rain", "violin", songs, sheets)


def test_deterministic_sheet_explanation_mentions_top_match():
    songs, sheets = load_fixture_data()
    seed_song, _, recommendations = rank_sheet_music(
        "Library Rain", "piano", songs, sheets, difficulty="beginner", k=3
    )

    explanation = deterministic_sheet_explanation(seed_song, recommendations)

    assert explanation["source"] == "deterministic"
    assert "Library Rain" in explanation["summary"]
    assert "piano" in explanation["summary"]

def test_validate_sheet_summary_rejects_truncated_text():
    with pytest.raises(ValueError, match="truncated|too short"):
        validate_sheet_summary("This beginner solo piano arrangement is ideal for")


def test_generate_sheet_explanation_falls_back_on_truncated_gemini(monkeypatch):
    songs, sheets = load_fixture_data()
    seed_song, _, recommendations = rank_sheet_music(
        "Library Rain", "piano", songs, sheets, difficulty="beginner", k=3
    )

    def truncated_stub(*args, **kwargs):
        raise ValueError("Gemini sheet explanation appeared truncated.")

    monkeypatch.setattr(
        "src.sheet_music.generate_sheet_explanation_with_gemini",
        truncated_stub,
    )

    explanation = generate_sheet_explanation(seed_song, recommendations, use_gemini=True)

    assert explanation["source"] == "fallback_deterministic"
    assert explanation["fallback_reason"] == "invalid_gemini_sheet_explanation"
    assert "truncated" in explanation["fallback_detail"]
    assert "Library Rain" in explanation["summary"]

def test_debug_gemini_prints_raw_sheet_response(monkeypatch, capsys):
    songs, sheets = load_fixture_data()
    seed_song, _, recommendations = rank_sheet_music(
        "Library Rain", "piano", songs, sheets, difficulty="beginner", k=3
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return (
                b'{"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":"This beginner piano arrangement fits the calm mood. It is short, accessible, and grounded in the original tags."}]}}]}'
            )

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("DEBUG_GEMINI", "1")
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())

    from src.sheet_music import generate_sheet_explanation_with_gemini

    result = generate_sheet_explanation_with_gemini(seed_song, recommendations)
    output = capsys.readouterr().out

    assert result["source"] == "gemini"
    assert "[DEBUG_GEMINI]" in output
    assert "finishReason" in output

