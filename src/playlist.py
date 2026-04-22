"""Playlist packaging and grounded AI explanation helpers."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Dict, List, Tuple

from src.intent import read_http_error_detail


def build_playlist_packages(
    profile: Dict,
    song_recommendations: List[Tuple[Dict, float, str]],
    context: str | None = None,
) -> List[Dict]:
    """Group ranked recommendations into user-facing playlist packages."""
    top_songs = [song for song, _, _ in song_recommendations]
    core_songs = top_songs[:3]
    context_songs = select_context_songs(profile, top_songs, context)
    if same_song_set(context_songs, core_songs):
        context_songs = rotate_selection(top_songs, start=1, size=3)

    discovery_songs = select_discovery_songs(profile, top_songs)
    if same_song_set(discovery_songs, core_songs) or same_song_set(discovery_songs, context_songs):
        discovery_songs = rotate_selection(top_songs, start=2, size=3)

    packages = [
        {
            "name": "Core Taste Mix",
            "description": "Closest matches to the user's strongest listening patterns.",
            "song_ids": [song["id"] for song in core_songs],
        },
        {
            "name": "Context Fit",
            "description": context_specific_description(context),
            "song_ids": [song["id"] for song in context_songs],
        },
        {
            "name": "Discovery Stretch",
            "description": "Slightly broader recommendations that still share parts of the user's taste profile.",
            "song_ids": [song["id"] for song in discovery_songs],
        },
    ]
    return [package for package in packages if package["song_ids"]]


def same_song_set(left: List[Dict], right: List[Dict]) -> bool:
    """Return True when two package selections contain the same songs."""
    return {song["id"] for song in left} == {song["id"] for song in right}


def rotate_selection(songs: List[Dict], start: int, size: int) -> List[Dict]:
    """Select a shifted window of songs for package diversity."""
    if not songs:
        return []
    if len(songs) <= size:
        return songs
    end = start + size
    if end <= len(songs):
        return songs[start:end]
    return (songs[start:] + songs[:end - len(songs)])[:size]


def context_specific_description(context: str | None) -> str:
    """Return a deterministic description for optional context."""
    if not context:
        return "A flexible package for the user's current listening context."
    return f"Recommendations shaped around the context: {context}."


def select_context_songs(profile: Dict, songs: List[Dict], context: str | None) -> List[Dict]:
    """Select songs that fit simple time/weather/activity context signals."""
    if not context:
        return songs[:3]

    text = context.lower()
    scored = []
    for song in songs:
        score = 0
        tags = set(song.get("mood_tags", "").split("|"))
        if any(term in text for term in ["rain", "night", "late"]):
            score += len(tags & {"nocturnal", "dreamy", "cozy", "reflective"})
            if song["energy"] <= profile["target_energy"] + 0.2:
                score += 1
        if any(term in text for term in ["study", "focus", "work", "coding"]):
            score += len(tags & {"focused", "minimal", "steady"})
            if song["instrumentalness"] > 0.5:
                score += 1
        if any(term in text for term in ["morning", "sunny", "workout", "party"]):
            score += len(tags & {"bright", "uplifting", "euphoric", "energetic"})
            if song["energy"] >= profile["target_energy"]:
                score += 1
        scored.append((score, song))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [song for score, song in scored if score > 0]
    return (selected or songs)[:3]


def select_discovery_songs(profile: Dict, songs: List[Dict]) -> List[Dict]:
    """Pick adjacent recommendations that avoid only repeating the top genre."""
    discovery = [
        song for song in songs
        if song["genre"] != profile["favorite_genre"]
    ]
    return (discovery or songs[3:] or songs)[:3]


def build_playlist_prompt(
    stats: Dict,
    profile: Dict,
    packages: List[Dict],
    song_recommendations: List[Tuple[Dict, float, str]],
    album_recommendations: List[Tuple[Dict, float, str]],
    context: str | None,
) -> str:
    """Build a constrained Gemini prompt for package explanations."""
    songs = [
        {
            "title": song["title"],
            "artist": song["artist"],
            "genre": song["genre"],
            "mood": song["mood"],
            "tags": song["mood_tags"],
            "score": round(score, 2),
        }
        for song, score, _ in song_recommendations[:5]
    ]
    albums = [
        {
            "album": album["album_name"],
            "artist": album["artist"],
            "genre": album["genre"],
            "mood": album["mood"],
        }
        for album, _, _ in album_recommendations[:3]
    ]
    compact_payload = {
        "context": context,
        "taste_profile": {
            "favorite_genre": profile.get("favorite_genre"),
            "favorite_mood": profile.get("favorite_mood"),
            "top_tags": profile.get("top_tags", [])[:4],
        },
        "listening_summary": {
            "top_tags": stats.get("top_tags", [])[:4],
            "favorite_genres": stats.get("favorite_genres", [])[:3],
            "favorite_moods": stats.get("favorite_moods", [])[:3],
        },
        "candidate_songs": songs,
        "recommended_albums": albums,
        "package_names": [package["name"] for package in packages],
    }
    package_lines = "\n".join(f"{package['name']}:" for package in packages)
    return f"""
You are writing short explanations for music playlist packages.
Use only these package names, exactly as written:
{package_lines}

Return exactly one line per package in this format:
Package Name: explanation

Rules:
- No JSON.
- No markdown.
- No bullets.
- No extra intro or closing text.
- Keep each explanation under 22 words.
- Ground each explanation in the input data.

Input data:
{json.dumps(compact_payload, separators=(",", ":"))}
""".strip()


def parse_gemini_explanation_lines(text: str, packages: List[Dict]) -> Dict[str, str]:
    """Parse plain text package explanations from Gemini."""
    expected_names = [package["name"] for package in packages]
    explanations: Dict[str, str] = {}
    for raw_line in text.strip().splitlines():
        line = raw_line.strip().strip("- ")
        if not line or ":" not in line:
            continue
        name, explanation = line.split(":", 1)
        name = name.strip()
        explanation = explanation.strip()
        if name in expected_names and explanation:
            explanations[name] = explanation

    if not explanations:
        raise ValueError("Gemini output missing parseable package explanations.")
    return explanations


def attach_gemini_explanations(explanations: Dict[str, str], packages: List[Dict]) -> Dict:
    """Attach Gemini explanations to deterministic package structure."""
    explained_packages = []
    for package in packages:
        name = package["name"]
        explained_packages.append({
            "name": name,
            "description": package["description"],
            "song_ids": package["song_ids"],
            "why_it_fits": explanations.get(name, package["description"]),
        })

    return {"source": "gemini", "packages": explained_packages}


def generate_playlist_explanations_with_gemini(
    stats: Dict,
    profile: Dict,
    packages: List[Dict],
    song_recommendations: List[Tuple[Dict, float, str]],
    album_recommendations: List[Tuple[Dict, float, str]],
    context: str | None = None,
    timeout: int = 20,
) -> Dict:
    """Generate playlist explanations with Gemini."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    payload = {
        "contents": [
            {"parts": [{"text": build_playlist_prompt(
                stats,
                profile,
                packages,
                song_recommendations,
                album_recommendations,
                context,
            )}]}
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 500,
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

    text = body["candidates"][0]["content"]["parts"][0]["text"]
    explanations = parse_gemini_explanation_lines(text, packages)
    return attach_gemini_explanations(explanations, packages)


def deterministic_playlist_explanations(
    packages: List[Dict],
    song_lookup: Dict[int, Dict],
    source: str = "deterministic",
    fallback_reason: str | None = None,
    fallback_detail: str | None = None,
) -> Dict:
    """Build safe playlist package explanations without Gemini."""
    explained = []
    for package in packages:
        titles = [
            f"{song_lookup[song_id]['title']} by {song_lookup[song_id]['artist']}"
            for song_id in package["song_ids"]
            if song_id in song_lookup
        ]
        explained.append({
            "name": package["name"],
            "description": package["description"],
            "song_ids": package["song_ids"],
            "why_it_fits": (
                f"This package uses ranked recommendations from the user's "
                f"taste profile: {', '.join(titles)}."
            ),
        })

    result = {"source": source, "packages": explained}
    if fallback_reason:
        result["fallback_reason"] = fallback_reason
    if fallback_detail:
        result["fallback_detail"] = fallback_detail
    return result


def validate_playlist_output(ai_output: Dict, allowed_song_ids: set[int]) -> Dict:
    """Ensure generated playlist packages only contain allowed song IDs."""
    if not isinstance(ai_output, dict) or "packages" not in ai_output:
        raise ValueError("Playlist output missing packages.")

    validated = {"source": ai_output.get("source", "gemini"), "packages": []}
    for package in ai_output["packages"]:
        song_ids = package.get("song_ids", [])
        if not isinstance(song_ids, list):
            raise ValueError("Playlist song_ids must be a list.")
        cleaned_ids = [int(song_id) for song_id in song_ids if int(song_id) in allowed_song_ids]
        if not cleaned_ids:
            raise ValueError("Playlist package has no valid song IDs.")

        validated["packages"].append({
            "name": str(package.get("name", "Playlist Package")),
            "description": str(package.get("description", "")),
            "song_ids": cleaned_ids,
            "why_it_fits": str(package.get("why_it_fits", "")),
        })

    return validated


def generate_playlist_packages(
    stats: Dict,
    profile: Dict,
    song_recommendations: List[Tuple[Dict, float, str]],
    album_recommendations: List[Tuple[Dict, float, str]],
    context: str | None = None,
    use_gemini: bool = True,
) -> Dict:
    """Build, explain, validate, and safely fallback for playlist packages."""
    packages = build_playlist_packages(profile, song_recommendations, context)
    song_lookup = {song["id"]: song for song, _, _ in song_recommendations}
    allowed_song_ids = set(song_lookup)

    if use_gemini:
        try:
            ai_output = generate_playlist_explanations_with_gemini(
                stats,
                profile,
                packages,
                song_recommendations,
                album_recommendations,
                context,
            )
            return validate_playlist_output(ai_output, allowed_song_ids)
        except urllib.error.HTTPError as exc:
            return deterministic_playlist_explanations(
                packages,
                song_lookup,
                source="fallback_deterministic",
                fallback_reason=f"HTTPError_{exc.code}",
                fallback_detail=read_http_error_detail(exc),
            )
        except (ValueError, KeyError, TimeoutError, json.JSONDecodeError, urllib.error.URLError) as exc:
            return deterministic_playlist_explanations(
                packages,
                song_lookup,
                source="fallback_deterministic",
                fallback_reason=type(exc).__name__,
            )

    return deterministic_playlist_explanations(packages, song_lookup)
