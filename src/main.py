"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

import argparse
import sys

from tabulate import tabulate
from src.recommender import load_songs, recommend_songs, max_score
from src.search import explain_intent_adjustment, recommend_similar_songs


def format_reasons(explanation: str) -> str:
    """Compress explanation into a single-line summary."""
    parts = explanation.replace("Matched on: ", "").split(", ")
    short = []
    for part in parts:
        if part.startswith("DIVERSITY:"):
            short.append(part.replace("DIVERSITY: ", "").strip())
        else:
            short.append(part)
    return " | ".join(short)


def print_profile_header(name: str, prefs: dict) -> None:
    """Print a formatted header for a user profile."""
    print(f"\n{'='*100}")
    print(f"  PROFILE: {name}")
    print(f"  Genre: {prefs['favorite_genre']}  |  Mood: {prefs['favorite_mood']}  "
          f"|  Energy: {prefs['target_energy']}  |  Decade: {prefs['preferred_decade']}"
          f"  |  Language: {prefs['preferred_language']}"
          f"  |  Tags: {prefs['liked_mood_tags'].replace('|', ', ')}")
    print(f"{'='*100}")


def print_results_table(recommendations: list, ms: float) -> None:
    """Print a single table with scores and reasons per song."""
    rows = []
    for rank, (song, score, explanation) in enumerate(recommendations, 1):
        reasons = format_reasons(explanation)
        rows.append([
            f"#{rank}",
            song["title"],
            song["artist"],
            f"{song['genre']}/{song['mood']}",
            song["energy"],
            f"{score:.2f}/{ms:.1f}",
            reasons,
        ])

    print(tabulate(
        rows,
        headers=["Rank", "Title", "Artist", "Genre/Mood", "Energy", "Score", "Breakdown"],
        tablefmt="grid",
        maxcolwidths=[None, None, None, None, None, None, 80],
    ))


def print_seed_song(seed_song: dict, confidence: float) -> None:
    """Print the searched song used as the recommendation seed."""
    print("\nMatched seed song:")
    print(
        f"- {seed_song['title']} by {seed_song['artist']} "
        f"({seed_song['genre']}, {seed_song['mood']}, energy {seed_song['energy']})"
    )
    print(f"Search confidence: {confidence:.2f}")


def print_intent_adjustment(intent: dict | None) -> None:
    """Print parsed natural-language intent when provided."""
    if not intent:
        return

    print("\nParsed intent adjustment:")
    print(f"- source: {intent['source']}")
    if intent.get("fallback_reason"):
        print(f"- fallback_reason: {intent['fallback_reason']}")
    if intent.get("fallback_detail"):
        print(f"- fallback_detail: {intent['fallback_detail']}")
    print(f"- confidence: {intent['confidence']:.2f}")
    print(f"- energy_delta: {intent['energy_delta']:+.2f}")
    if intent["preferred_mood"]:
        print(f"- preferred_mood: {intent['preferred_mood']}")
    if intent["required_language"]:
        print(f"- required_language: {intent['required_language']}")
    if intent["preferred_tags"]:
        print(f"- preferred_tags: {', '.join(intent['preferred_tags'])}")
    if intent["requires_instrumental"] is not None:
        print(f"- requires_instrumental: {intent['requires_instrumental']}")
    if intent["requires_acoustic"] is not None:
        print(f"- requires_acoustic: {intent['requires_acoustic']}")


def run_base_demo() -> None:
    """Run the original profile-based recommender demo."""
    songs = load_songs("data/songs.csv")
    print(f"\nLoaded {len(songs)} songs from catalog.\n")

    profiles = {
        "High-Energy Pop Fan": {
            "favorite_genre": "pop",
            "favorite_mood": "happy",
            "target_energy": 0.85,
            "likes_acoustic": False,
            "prefers_instrumental": False,
            "prefers_popular": True,
            "preferred_decade": 2020,
            "liked_mood_tags": "uplifting|euphoric|bright",
            "preferred_language": "english",
            "target_duration_sec": 210,
            "values_replayability": True,
        },
        "Chill Lofi Listener": {
            "favorite_genre": "lofi",
            "favorite_mood": "chill",
            "target_energy": 0.35,
            "likes_acoustic": True,
            "prefers_instrumental": True,
            "prefers_popular": False,
            "preferred_decade": 2020,
            "liked_mood_tags": "dreamy|peaceful|cozy",
            "preferred_language": "instrumental",
            "target_duration_sec": 220,
            "values_replayability": True,
        },
        "Deep Intense Rock": {
            "favorite_genre": "rock",
            "favorite_mood": "intense",
            "target_energy": 0.90,
            "likes_acoustic": False,
            "prefers_instrumental": False,
            "prefers_popular": True,
            "preferred_decade": 2010,
            "liked_mood_tags": "aggressive|powerful|driving",
            "preferred_language": "english",
            "target_duration_sec": 260,
            "values_replayability": True,
        },
        # --- Adversarial profiles for stress-testing ---
        "Sad But Energetic": {
            "favorite_genre": "classical",
            "favorite_mood": "melancholy",
            "target_energy": 0.90,
            "likes_acoustic": True,
            "prefers_instrumental": True,
            "prefers_popular": False,
            "preferred_decade": 1990,
            "liked_mood_tags": "melancholic|haunting|dark",
            "preferred_language": "instrumental",
            "target_duration_sec": 340,
            "values_replayability": False,
        },
        "Acoustic Popular Pop": {
            "favorite_genre": "pop",
            "favorite_mood": "happy",
            "target_energy": 0.80,
            "likes_acoustic": True,
            "prefers_instrumental": False,
            "prefers_popular": True,
            "preferred_decade": 2020,
            "liked_mood_tags": "uplifting|carefree|warm",
            "preferred_language": "english",
            "target_duration_sec": 200,
            "values_replayability": True,
        },
        "Chill Metal Listener": {
            "favorite_genre": "metal",
            "favorite_mood": "chill",
            "target_energy": 0.20,
            "likes_acoustic": False,
            "prefers_instrumental": False,
            "prefers_popular": False,
            "preferred_decade": 2000,
            "liked_mood_tags": "dark|nocturnal|intimate",
            "preferred_language": "english",
            "target_duration_sec": 280,
            "values_replayability": False,
        },
    }

    # Default: Balanced mode with diversity enabled
    mode = "balanced"
    ms = max_score(mode)

    for profile_name, user_prefs in profiles.items():
        print_profile_header(profile_name, user_prefs)

        recommendations = recommend_songs(
            user_prefs, songs, k=5, mode=mode, diverse=True
        )

        print()
        print_results_table(recommendations, ms)
        print()


def run_similar_song_search(
    song_query: str,
    k: int,
    mode: str,
    intent: str | None,
    use_gemini: bool,
) -> int:
    """Run Feature 1: search a song and recommend similar tracks."""
    songs = load_songs("data/songs.csv")
    intent_adjustment = None
    if intent:
        intent_adjustment = explain_intent_adjustment(intent, use_gemini=use_gemini)

    try:
        seed_song, confidence, recommendations = recommend_similar_songs(
            song_query,
            songs,
            k=k,
            mode=mode,
            intent_text=intent,
            use_gemini=use_gemini,
            intent_adjustment=intent_adjustment,
        )
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    print_seed_song(seed_song, confidence)
    print_intent_adjustment(intent_adjustment)
    print_results_table(recommendations, max_score(mode))
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Music Companion command line interface."
    )
    subparsers = parser.add_subparsers(dest="command")

    similar_parser = subparsers.add_parser(
        "similar",
        help="Search for a song and recommend tracks with similar metadata.",
    )
    similar_parser.add_argument(
        "--song",
        required=True,
        help="Song title, artist, or title plus artist to use as the seed.",
    )
    similar_parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="Number of similar songs to return.",
    )
    similar_parser.add_argument(
        "--mode",
        default="balanced",
        choices=["balanced", "genre-first", "energy-focused"],
        help="Scoring strategy used for similar-song ranking.",
    )
    similar_parser.add_argument(
        "--intent",
        default=None,
        help="Optional natural-language adjustment, such as 'more energetic but still instrumental'.",
    )
    similar_parser.add_argument(
        "--no-gemini",
        action="store_true",
        help="Use the local rule-based intent parser instead of Gemini.",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the base demo or a selected Music Companion workflow."""
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        run_base_demo()
        return 0

    args = parse_args(argv)
    if args.command == "similar":
        return run_similar_song_search(
            args.song,
            args.k,
            args.mode,
            args.intent,
            use_gemini=not args.no_gemini,
        )

    run_base_demo()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
