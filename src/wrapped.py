"""Monthly and yearly listening recap generation."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from typing import Dict, List

from src.intent import read_http_error_detail


def event_weight(event: Dict) -> int:
    """Return a weighted play count for recap ranking."""
    weight = max(1, event["play_count"])
    if event["completed"]:
        weight += 1
    if event["skipped"]:
        weight = max(1, weight - 2)
    return weight


def event_in_period(event: Dict, period: str, year: int, month: int | None = None) -> bool:
    """Return whether a listening event belongs to the requested period."""
    played_at = datetime.fromisoformat(event["played_at"])
    if played_at.year != year:
        return False
    if period == "year":
        return True
    if period == "month":
        if month is None:
            raise ValueError("Month is required when period is 'month'.")
        return played_at.month == month
    raise ValueError("Period must be 'month' or 'year'.")


def period_label(period: str, year: int, month: int | None = None) -> str:
    """Create a user-facing recap period label."""
    if period == "year":
        return str(year)
    if month is None:
        raise ValueError("Month is required when period is 'month'.")
    return f"{year}-{month:02d}"


def match_album_for_song(song: Dict, albums: List[Dict]) -> Dict | None:
    """Infer an album match from current metadata.

    The song catalog does not contain album IDs yet, so this uses artist first,
    then genre/mood proximity as a transparent approximation.
    """
    for album in albums:
        if album["artist"] == song["artist"]:
            return album
    for album in albums:
        if album["genre"] == song["genre"] and album["mood"] == song["mood"]:
            return album
    for album in albums:
        if album["genre"] == song["genre"]:
            return album
    return None


def build_recap_stats(
    user_id: str,
    history: List[Dict],
    songs: List[Dict],
    albums: List[Dict],
    period: str,
    year: int,
    month: int | None = None,
) -> Dict:
    """Compute grounded monthly or yearly listening recap statistics."""
    song_by_id = {song["id"]: song for song in songs}
    selected_events = [
        event for event in history
        if event["user_id"] == user_id
        and event["song_id"] in song_by_id
        and event_in_period(event, period, year, month)
    ]
    if not selected_events:
        raise ValueError(
            f"No listening history found for user '{user_id}' in {period_label(period, year, month)}."
        )

    song_counts = Counter()
    artist_counts = Counter()
    album_counts = Counter()
    genre_counts = Counter()
    mood_counts = Counter()
    tag_counts = Counter()
    total_weight = 0
    weighted_energy = 0.0

    album_lookup = {}
    for event in selected_events:
        song = song_by_id[event["song_id"]]
        weight = event_weight(event)
        total_weight += weight
        weighted_energy += song["energy"] * weight
        song_counts[song["id"]] += weight
        artist_counts[song["artist"]] += weight
        genre_counts[song["genre"]] += weight
        mood_counts[song["mood"]] += weight
        for tag in song["mood_tags"].split("|"):
            if tag:
                tag_counts[tag] += weight

        album = match_album_for_song(song, albums)
        if album:
            album_counts[album["album_id"]] += weight
            album_lookup[album["album_id"]] = album

    top_songs = [
        {
            "song_id": song_id,
            "title": song_by_id[song_id]["title"],
            "artist": song_by_id[song_id]["artist"],
            "weighted_plays": plays,
        }
        for song_id, plays in song_counts.most_common(10)
    ]
    top_albums = [
        {
            "album_id": album_id,
            "album_name": album_lookup[album_id]["album_name"],
            "artist": album_lookup[album_id]["artist"],
            "weighted_plays": plays,
        }
        for album_id, plays in album_counts.most_common(5)
    ]

    return {
        "user_id": user_id,
        "period": period,
        "period_label": period_label(period, year, month),
        "event_count": len(selected_events),
        "total_weighted_plays": total_weight,
        "average_energy": round(weighted_energy / total_weight, 2),
        "top_songs": top_songs,
        "top_artists": artist_counts.most_common(5),
        "top_albums": top_albums,
        "top_genres": genre_counts.most_common(5),
        "top_moods": mood_counts.most_common(5),
        "top_tags": tag_counts.most_common(5),
    }


def deterministic_recap_summary(stats: Dict) -> Dict:
    """Create a safe recap summary directly from computed stats."""
    top_genre = stats["top_genres"][0][0]
    top_mood = stats["top_moods"][0][0]
    top_tag_names = ", ".join(tag for tag, _ in stats["top_tags"][:3])
    top_artist_names = ", ".join(artist for artist, _ in stats["top_artists"][:3])
    top_song = stats["top_songs"][0]
    summary = (
        f"In {stats['period_label']}, {stats['user_id']} leaned toward {top_genre} "
        f"and {top_mood} music with average energy {stats['average_energy']:.2f}. "
        f"Key taste tags were {top_tag_names}. The most-played track was "
        f"{top_song['title']} by {top_song['artist']}, and frequent artists included "
        f"{top_artist_names}."
    )
    return {"source": "deterministic", "summary": summary}


def build_recap_prompt(stats: Dict) -> str:
    """Build a compact Gemini prompt grounded in recap statistics."""
    compact_stats = {
        "user_id": stats["user_id"],
        "period_label": stats["period_label"],
        "event_count": stats["event_count"],
        "total_weighted_plays": stats["total_weighted_plays"],
        "average_energy": stats["average_energy"],
        "top_songs": stats["top_songs"][:10],
        "top_artists": stats["top_artists"][:5],
        "top_albums": stats["top_albums"][:5],
        "top_genres": stats["top_genres"][:5],
        "top_moods": stats["top_moods"][:5],
        "top_tags": stats["top_tags"][:5],
    }
    return f"""
Write a concise listening recap for this user.
Use only the provided statistics. Do not invent songs, artists, albums, or numbers.
Mention the user's overall music taste, top genre or mood, and one standout song.
Keep it to 3 sentences.

Recap statistics:
{json.dumps(compact_stats, separators=(",", ":"))}
""".strip()


def generate_recap_summary_with_gemini(stats: Dict, timeout: int = 20) -> Dict:
    """Generate a grounded recap narrative with Gemini."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    payload = {
        "contents": [{"parts": [{"text": build_recap_prompt(stats)}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 350,
        },
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))

    summary = body["candidates"][0]["content"]["parts"][0]["text"].strip()
    if not summary:
        raise ValueError("Gemini returned an empty recap summary.")
    return {"source": "gemini", "summary": summary}


def generate_recap_summary(stats: Dict, use_gemini: bool = True) -> Dict:
    """Generate recap summary with Gemini and safe deterministic fallback."""
    if not use_gemini:
        return deterministic_recap_summary(stats)

    try:
        return generate_recap_summary_with_gemini(stats)
    except urllib.error.HTTPError as exc:
        fallback = deterministic_recap_summary(stats)
        fallback["source"] = "fallback_deterministic"
        fallback["fallback_reason"] = f"HTTPError_{exc.code}"
        fallback["fallback_detail"] = read_http_error_detail(exc)
        return fallback
    except (ValueError, KeyError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        fallback = deterministic_recap_summary(stats)
        fallback["source"] = "fallback_deterministic"
        fallback["fallback_reason"] = type(exc).__name__
        return fallback


def build_wrapped_report(
    user_id: str,
    history: List[Dict],
    songs: List[Dict],
    albums: List[Dict],
    period: str,
    year: int,
    month: int | None = None,
    use_gemini: bool = True,
) -> Dict:
    """Build a complete monthly or yearly listening recap."""
    stats = build_recap_stats(user_id, history, songs, albums, period, year, month)
    summary = generate_recap_summary(stats, use_gemini=use_gemini)
    return {"stats": stats, "summary": summary}
