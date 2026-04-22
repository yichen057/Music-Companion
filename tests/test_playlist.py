from src.history import (
    build_taste_profile,
    aggregate_user_history,
    load_albums,
    load_listening_history,
    recommend_albums_from_profile,
    recommend_songs_from_history,
)
from src.playlist import (
    build_playlist_packages,
    deterministic_playlist_explanations,
    generate_playlist_packages,
    attach_gemini_explanations,
    validate_playlist_output,
)
from src.recommender import load_songs


def load_recommendation_context():
    songs = load_songs("data/songs.csv")
    history = load_listening_history("data/listening_history.csv")
    albums = load_albums("data/albums.csv")
    stats, profile, song_recs = recommend_songs_from_history(
        "user_001", history, songs, k=6
    )
    album_recs = recommend_albums_from_profile(profile, albums, k=3)
    return songs, stats, profile, song_recs, album_recs


def test_build_playlist_packages_uses_ranked_song_ids():
    _, _, profile, song_recs, _ = load_recommendation_context()

    packages = build_playlist_packages(profile, song_recs, context="rainy night study")

    allowed_ids = {song["id"] for song, _, _ in song_recs}
    assert packages
    assert all(set(package["song_ids"]) <= allowed_ids for package in packages)


def test_build_playlist_packages_avoids_identical_packages():
    _, _, profile, song_recs, _ = load_recommendation_context()

    packages = build_playlist_packages(profile, song_recs, context="rainy night study")
    package_sets = [tuple(package["song_ids"]) for package in packages]

    assert len(set(package_sets)) > 1


def test_validate_playlist_output_rejects_invalid_song_ids():
    ai_output = {
        "source": "gemini",
        "packages": [
            {
                "name": "Bad Package",
                "description": "Contains invalid IDs",
                "song_ids": [999],
                "why_it_fits": "Invalid",
            }
        ],
    }

    try:
        validate_playlist_output(ai_output, allowed_song_ids={1, 2, 3})
    except ValueError as exc:
        assert "no valid song IDs" in str(exc)
    else:
        raise AssertionError("Expected invalid playlist IDs to fail validation.")


def test_attach_gemini_explanations_keeps_local_song_ids():
    packages = [
        {
            "name": "Core Taste Mix",
            "description": "Closest matches.",
            "song_ids": [1, 2, 3],
        }
    ]
    explanations = {
        "Core Taste Mix": "Matches the user's lofi and focused listening pattern."
    }

    explained = attach_gemini_explanations(explanations, packages)

    assert explained["source"] == "gemini"
    assert explained["packages"][0]["song_ids"] == [1, 2, 3]
    assert "lofi" in explained["packages"][0]["why_it_fits"]


def test_deterministic_playlist_explanations_include_source():
    songs, _, profile, song_recs, _ = load_recommendation_context()
    song_lookup = {song["id"]: song for song, _, _ in song_recs}
    packages = build_playlist_packages(profile, song_recs)

    explained = deterministic_playlist_explanations(packages, song_lookup)

    assert explained["source"] == "deterministic"
    assert explained["packages"]
    assert "why_it_fits" in explained["packages"][0]


def test_generate_playlist_packages_fallback_without_gemini():
    _, stats, profile, song_recs, album_recs = load_recommendation_context()

    packages = generate_playlist_packages(
        stats,
        profile,
        song_recs,
        album_recs,
        context="rainy night study",
        use_gemini=False,
    )

    assert packages["source"] == "deterministic"
    assert packages["packages"]


def test_history_profile_still_available_for_playlist_context():
    songs = load_songs("data/songs.csv")
    history = load_listening_history("data/listening_history.csv")
    stats = aggregate_user_history("user_001", history, songs)
    profile = build_taste_profile(stats)

    assert profile["favorite_genre"] == "lofi"
    assert stats["top_tags"]


def test_generate_playlist_packages_falls_back_on_timeout(monkeypatch):
    _, stats, profile, song_recs, album_recs = load_recommendation_context()

    def timeout_stub(*args, **kwargs):
        raise TimeoutError("simulated timeout")

    monkeypatch.setattr(
        "src.playlist.generate_playlist_explanations_with_gemini",
        timeout_stub,
    )

    packages = generate_playlist_packages(
        stats,
        profile,
        song_recs,
        album_recs,
        context=None,
        use_gemini=True,
    )

    assert packages["source"] == "fallback_deterministic"
    assert packages["fallback_reason"] == "TimeoutError"
