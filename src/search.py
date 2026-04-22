"""Song search and similar-song recommendation workflows."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Dict, List, Tuple

from src.intent import apply_intent_to_profile, parse_intent
from src.recommender import DEFAULT_MODE, score_song


def normalize_query(text: str) -> str:
    """Normalize user text for title and artist matching."""
    return " ".join(text.lower().strip().split())


def search_keys(song: Dict) -> List[str]:
    """Return searchable strings for a song."""
    title = song["title"]
    artist = song["artist"]
    return [
        title,
        artist,
        f"{title} {artist}",
        f"{artist} {title}",
    ]


def find_song_by_query(
    query: str,
    songs: List[Dict],
    min_confidence: float = 0.55,
) -> Tuple[Dict, float]:
    """Find the best seed song for a user query.

    The confidence score is based on exact, substring, or fuzzy matching.
    """
    normalized = normalize_query(query)
    if not normalized:
        raise ValueError("Song query cannot be empty.")

    for song in songs:
        if normalize_query(song["title"]) == normalized:
            return song, 1.0

    substring_matches = []
    for song in songs:
        keys = [normalize_query(key) for key in search_keys(song)]
        if any(normalized in key for key in keys):
            confidence = max(
                SequenceMatcher(None, normalized, key).ratio()
                for key in keys
            )
            substring_matches.append((confidence, song))

    if substring_matches:
        substring_matches.sort(key=lambda match: match[0], reverse=True)
        confidence, song = substring_matches[0]
        return song, confidence

    best_song = None
    best_confidence = 0.0
    for song in songs:
        confidence = max(
            SequenceMatcher(None, normalized, normalize_query(key)).ratio()
            for key in search_keys(song)
        )
        if confidence > best_confidence:
            best_confidence = confidence
            best_song = song

    if best_song is None or best_confidence < min_confidence:
        raise ValueError(f"No song found for query '{query}'.")

    return best_song, best_confidence


def build_profile_from_seed_song(song: Dict) -> Dict:
    """Convert a seed song into a user-like profile for similarity scoring."""
    return {
        "favorite_genre": song["genre"],
        "favorite_mood": song["mood"],
        "target_energy": song["energy"],
        "likes_acoustic": song["acousticness"] > 0.5,
        "prefers_instrumental": song["instrumentalness"] > 0.5,
        "prefers_popular": song["popularity"] > 0.5,
        "preferred_decade": song["release_decade"],
        "liked_mood_tags": song["mood_tags"],
        "preferred_language": song["lyrics_language"],
        "target_duration_sec": song["duration_sec"],
        "values_replayability": song["replay_value"] > 0.5,
    }


def recommend_similar_songs(
    query: str,
    songs: List[Dict],
    k: int = 5,
    mode: str = DEFAULT_MODE,
    intent_text: str | None = None,
    use_gemini: bool = True,
    intent_adjustment: Dict | None = None,
) -> Tuple[Dict, float, List[Tuple[Dict, float, str]]]:
    """Recommend songs that are similar to a searched seed song."""
    seed_song, confidence = find_song_by_query(query, songs)
    seed_profile = build_profile_from_seed_song(seed_song)
    intent = intent_adjustment or parse_intent(intent_text or "", use_gemini=use_gemini)
    if intent_text or intent_adjustment:
        seed_profile = apply_intent_to_profile(seed_profile, intent)

    scored = []
    for song in songs:
        if song["id"] == seed_song["id"]:
            continue

        score, explanation = score_song(song, seed_profile, mode)
        explanation = (
            f"Similar to '{seed_song['title']}' because: "
            f"{explanation.replace('Matched on: ', '')}"
        )
        scored.append((song, score, explanation))

    scored.sort(key=lambda item: item[1], reverse=True)
    return seed_song, confidence, scored[:k]


def explain_intent_adjustment(intent_text: str | None, use_gemini: bool = True) -> Dict:
    """Return the parsed intent for display or testing."""
    return parse_intent(intent_text or "", use_gemini=use_gemini)
