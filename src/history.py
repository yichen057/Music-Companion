"""Listening-history based song and album recommendations."""

from __future__ import annotations

import csv
from collections import Counter
from typing import Dict, List, Tuple

from src.recommender import DEFAULT_MODE, score_song


def load_albums(csv_path: str) -> List[Dict]:
    """Load album metadata from CSV."""
    albums = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            albums.append({
                "album_id": int(row["album_id"]),
                "album_name": row["album_name"],
                "artist": row["artist"],
                "genre": row["genre"],
                "mood": row["mood"],
                "avg_energy": float(row["avg_energy"]),
                "language": row["language"],
                "release_decade": int(row["release_decade"]),
                "mood_tags": row["mood_tags"],
            })
    return albums


def load_listening_history(csv_path: str) -> List[Dict]:
    """Load timestamped user listening events from CSV."""
    events = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append({
                "user_id": row["user_id"],
                "song_id": int(row["song_id"]),
                "played_at": row["played_at"],
                "play_count": int(row["play_count"]),
                "completed": row["completed"].lower() == "true",
                "skipped": row["skipped"].lower() == "true",
            })
    return events


def aggregate_user_history(
    user_id: str,
    history: List[Dict],
    songs: List[Dict],
) -> Dict:
    """Aggregate one user's listening history into weighted taste signals."""
    song_by_id = {song["id"]: song for song in songs}
    user_events = [
        event for event in history
        if event["user_id"] == user_id and event["song_id"] in song_by_id
    ]
    if not user_events:
        raise ValueError(f"No listening history found for user '{user_id}'.")

    genre_counts = Counter()
    mood_counts = Counter()
    language_counts = Counter()
    artist_counts = Counter()
    tag_counts = Counter()
    song_counts = Counter()
    total_weight = 0
    weighted_energy = 0.0
    weighted_duration = 0.0
    weighted_decade = 0.0
    acoustic_weight = 0
    instrumental_weight = 0
    popular_weight = 0
    replay_weight = 0

    for event in user_events:
        song = song_by_id[event["song_id"]]
        weight = max(1, event["play_count"])
        if event["completed"]:
            weight += 1
        if event["skipped"]:
            weight = max(1, weight - 2)

        total_weight += weight
        song_counts[song["id"]] += weight
        genre_counts[song["genre"]] += weight
        mood_counts[song["mood"]] += weight
        language_counts[song["lyrics_language"]] += weight
        artist_counts[song["artist"]] += weight
        weighted_energy += song["energy"] * weight
        weighted_duration += song["duration_sec"] * weight
        weighted_decade += song["release_decade"] * weight

        if song["acousticness"] > 0.5:
            acoustic_weight += weight
        if song["instrumentalness"] > 0.5:
            instrumental_weight += weight
        if song["popularity"] > 0.5:
            popular_weight += weight
        if song["replay_value"] > 0.5:
            replay_weight += weight

        for tag in song["mood_tags"].split("|"):
            if tag:
                tag_counts[tag] += weight

    return {
        "user_id": user_id,
        "event_count": len(user_events),
        "total_weight": total_weight,
        "top_genre": genre_counts.most_common(1)[0][0],
        "top_mood": mood_counts.most_common(1)[0][0],
        "top_language": language_counts.most_common(1)[0][0],
        "top_artists": artist_counts.most_common(5),
        "top_songs": song_counts.most_common(10),
        "top_tags": tag_counts.most_common(5),
        "avg_energy": weighted_energy / total_weight,
        "avg_duration_sec": round(weighted_duration / total_weight),
        "avg_decade": round(weighted_decade / total_weight / 10) * 10,
        "likes_acoustic": acoustic_weight / total_weight >= 0.5,
        "prefers_instrumental": instrumental_weight / total_weight >= 0.5,
        "prefers_popular": popular_weight / total_weight >= 0.5,
        "values_replayability": replay_weight / total_weight >= 0.5,
    }


def build_taste_profile(stats: Dict) -> Dict:
    """Convert aggregated listening stats into a recommender profile."""
    tags = [tag for tag, _ in stats["top_tags"]]
    return {
        "favorite_genre": stats["top_genre"],
        "favorite_mood": stats["top_mood"],
        "target_energy": round(stats["avg_energy"], 2),
        "likes_acoustic": stats["likes_acoustic"],
        "prefers_instrumental": stats["prefers_instrumental"],
        "prefers_popular": stats["prefers_popular"],
        "preferred_decade": stats["avg_decade"],
        "liked_mood_tags": "|".join(tags),
        "preferred_language": stats["top_language"],
        "target_duration_sec": stats["avg_duration_sec"],
        "values_replayability": stats["values_replayability"],
    }


def recommend_songs_from_history(
    user_id: str,
    history: List[Dict],
    songs: List[Dict],
    k: int = 5,
    mode: str = DEFAULT_MODE,
) -> Tuple[Dict, Dict, List[Tuple[Dict, float, str]]]:
    """Recommend songs from a user's listening history profile."""
    stats = aggregate_user_history(user_id, history, songs)
    profile = build_taste_profile(stats)
    played_song_ids = {song_id for song_id, _ in stats["top_songs"]}

    scored = []
    for song in songs:
        if song["id"] in played_song_ids:
            continue
        score, explanation = score_song(song, profile, mode)
        explanation = (
            f"Based on {user_id}'s listening history: "
            f"{explanation.replace('Matched on: ', '')}"
        )
        scored.append((song, score, explanation))

    scored.sort(key=lambda item: item[1], reverse=True)
    return stats, profile, scored[:k]


def album_to_song_like(album: Dict) -> Dict:
    """Map album metadata into fields compatible with score_song."""
    return {
        "genre": album["genre"],
        "mood": album["mood"],
        "energy": album["avg_energy"],
        "acousticness": 0.6 if "acoustic" in album["mood_tags"] else 0.4,
        "instrumentalness": 0.8 if album["language"] == "instrumental" else 0.2,
        "popularity": 0.5,
        "release_decade": album["release_decade"],
        "mood_tags": album["mood_tags"],
        "lyrics_language": album["language"],
        "duration_sec": 240,
        "replay_value": 0.7,
    }


def recommend_albums_from_profile(
    profile: Dict,
    albums: List[Dict],
    k: int = 3,
    mode: str = DEFAULT_MODE,
) -> List[Tuple[Dict, float, str]]:
    """Rank albums against a taste profile."""
    scored = []
    for album in albums:
        score, explanation = score_song(album_to_song_like(album), profile, mode)
        explanation = (
            "Album fit: " + explanation.replace("Matched on: ", "")
        )
        scored.append((album, score, explanation))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:k]


def summarize_taste(stats: Dict, profile: Dict) -> str:
    """Create a concise deterministic taste summary."""
    tags = ", ".join(tag for tag, _ in stats["top_tags"][:3])
    artists = ", ".join(artist for artist, _ in stats["top_artists"][:3])
    return (
        f"{stats['user_id']} leans toward {profile['favorite_genre']} and "
        f"{profile['favorite_mood']} music with average energy "
        f"{profile['target_energy']:.2f}. Common tags include {tags}. "
        f"Frequently played artists include {artists}."
    )
