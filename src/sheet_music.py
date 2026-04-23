"""Sheet music matching for light music arrangements."""

from __future__ import annotations

import csv
import json
import os
import urllib.error
import urllib.request
from typing import Dict, List, Tuple

from src.intent import read_http_error_detail
from src.search import find_song_by_query

DIFFICULTY_ORDER = {
    "beginner": 1,
    "intermediate": 2,
    "advanced": 3,
}


def load_sheet_music(csv_path: str) -> List[Dict]:
    """Load sheet music metadata from CSV."""
    sheets = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sheets.append({
                "sheet_id": int(row["sheet_id"]),
                "song_title": row["song_title"],
                "artist": row["artist"],
                "instrument": row["instrument"],
                "difficulty": row["difficulty"],
                "arrangement_style": row["arrangement_style"],
                "key_signature": row["key_signature"],
                "page_count": int(row["page_count"]),
                "source_type": row["source_type"],
                "mood_tags": row["mood_tags"],
                "beginner_friendly": row["beginner_friendly"].lower() == "true",
            })
    return sheets


def difficulty_distance(sheet_difficulty: str, requested_difficulty: str | None) -> int:
    """Return distance between sheet difficulty and requested difficulty."""
    if not requested_difficulty:
        return 0
    return abs(DIFFICULTY_ORDER[sheet_difficulty] - DIFFICULTY_ORDER[requested_difficulty])


def score_sheet_music(
    sheet: Dict,
    seed_song: Dict,
    instrument: str,
    difficulty: str | None = None,
) -> Tuple[float, str]:
    """Score one sheet music entry against the requested song and instrument."""
    score = 0.0
    reasons = []

    if sheet["song_title"].lower() == seed_song["title"].lower():
        score += 4.0
        reasons.append("song title match (+4.0)")
    if sheet["artist"].lower() == seed_song["artist"].lower():
        score += 2.0
        reasons.append("artist match (+2.0)")
    if sheet["instrument"] == instrument:
        score += 3.0
        reasons.append("instrument match (+3.0)")
    else:
        score -= 2.0
        reasons.append("different instrument (-2.0)")

    if difficulty:
        distance = difficulty_distance(sheet["difficulty"], difficulty)
        difficulty_score = max(0.0, 1.5 - (distance * 0.75))
        score += difficulty_score
        reasons.append(f"difficulty proximity (+{difficulty_score:.2f})")

    sheet_tags = set(sheet["mood_tags"].split("|"))
    song_tags = set(seed_song["mood_tags"].split("|"))
    overlap = sorted(sheet_tags & song_tags)
    if overlap:
        tag_score = min(1.0, len(overlap) * 0.35)
        score += tag_score
        reasons.append(f"shared mood tags [{', '.join(overlap)}] (+{tag_score:.2f})")

    if seed_song["energy"] <= 0.45:
        score += 0.5
        reasons.append("light music energy fit (+0.5)")
    if sheet["beginner_friendly"] and difficulty == "beginner":
        score += 0.5
        reasons.append("beginner-friendly arrangement (+0.5)")

    return score, "Sheet match because: " + " | ".join(reasons)


def rank_sheet_music(
    song_query: str,
    instrument: str,
    songs: List[Dict],
    sheets: List[Dict],
    difficulty: str | None = None,
    k: int = 5,
) -> Tuple[Dict, float, List[Tuple[Dict, float, str]]]:
    """Find a song and rank matching sheet music entries."""
    instrument = instrument.lower()
    if instrument not in {"piano", "guitar"}:
        raise ValueError("Instrument must be 'piano' or 'guitar'.")
    if difficulty and difficulty not in DIFFICULTY_ORDER:
        raise ValueError("Difficulty must be beginner, intermediate, or advanced.")

    seed_song, confidence = find_song_by_query(song_query, songs)
    scored = []
    for sheet in sheets:
        if sheet["instrument"] != instrument:
            continue
        score, explanation = score_sheet_music(sheet, seed_song, instrument, difficulty)
        if score > 0:
            scored.append((sheet, score, explanation))

    scored.sort(key=lambda item: item[1], reverse=True)
    if not scored:
        raise ValueError(f"No sheet music found for instrument '{instrument}'.")
    return seed_song, confidence, scored[:k]


def deterministic_sheet_explanation(seed_song: Dict, recommendations: List[Tuple[Dict, float, str]]) -> Dict:
    """Create a safe sheet-matching explanation without Gemini."""
    top_sheet = recommendations[0][0]
    summary = (
        f"The best match for {seed_song['title']} is the {top_sheet['instrument']} "
        f"{top_sheet['arrangement_style']} arrangement at {top_sheet['difficulty']} level. "
        f"It matches the requested song metadata and preserves tags such as "
        f"{top_sheet['mood_tags'].replace('|', ', ')}."
    )
    return {"source": "deterministic", "summary": summary}




def validate_sheet_summary(summary: str) -> str:
    """Reject truncated or low-information Gemini sheet explanations."""
    cleaned = summary.strip()
    if len(cleaned.split()) < 14:
        raise ValueError("Gemini sheet explanation was too short.")
    if cleaned[-1] not in ".!?":
        raise ValueError("Gemini sheet explanation appeared truncated.")
    return cleaned


def build_sheet_prompt(seed_song: Dict, recommendations: List[Tuple[Dict, float, str]]) -> str:
    """Build compact Gemini prompt for sheet music explanation."""
    payload = {
        "song": {
            "title": seed_song["title"],
            "artist": seed_song["artist"],
            "genre": seed_song["genre"],
            "mood": seed_song["mood"],
            "energy": seed_song["energy"],
            "tags": seed_song["mood_tags"],
        },
        "ranked_sheet_music": [
            {
                "sheet_id": sheet["sheet_id"],
                "instrument": sheet["instrument"],
                "difficulty": sheet["difficulty"],
                "arrangement_style": sheet["arrangement_style"],
                "key_signature": sheet["key_signature"],
                "page_count": sheet["page_count"],
                "source_type": sheet["source_type"],
                "score": round(score, 2),
            }
            for sheet, score, _ in recommendations[:3]
        ],
    }
    return f"""
Write a complete explanation for why the top sheet music result fits the requested song.
Use only the provided song and sheet music metadata. Do not invent links or availability.
Mention instrument, difficulty, arrangement style, and why it fits the song's mood.
Return exactly 2 complete sentences ending with punctuation.

Input data:
{json.dumps(payload, separators=(",", ":"))}
""".strip()


def generate_sheet_explanation_with_gemini(
    seed_song: Dict,
    recommendations: List[Tuple[Dict, float, str]],
    timeout: int = 20,
) -> Dict:
    """Generate grounded sheet music explanation with Gemini."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    payload = {
        "contents": [{"parts": [{"text": build_sheet_prompt(seed_song, recommendations)}]}],
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

    if os.getenv("DEBUG_GEMINI") == "1":
        print("\n[DEBUG_GEMINI] Sheet music Gemini raw response")
        print(json.dumps(body, indent=2))

    summary = body["candidates"][0]["content"]["parts"][0]["text"].strip()
    if not summary:
        raise ValueError("Gemini returned an empty sheet explanation.")
    return {"source": "gemini", "summary": validate_sheet_summary(summary)}


def generate_sheet_explanation(
    seed_song: Dict,
    recommendations: List[Tuple[Dict, float, str]],
    use_gemini: bool = True,
) -> Dict:
    """Generate sheet music explanation with safe deterministic fallback."""
    if not use_gemini:
        return deterministic_sheet_explanation(seed_song, recommendations)

    try:
        return generate_sheet_explanation_with_gemini(seed_song, recommendations)
    except urllib.error.HTTPError as exc:
        fallback = deterministic_sheet_explanation(seed_song, recommendations)
        fallback["source"] = "fallback_deterministic"
        fallback["fallback_reason"] = f"HTTPError_{exc.code}"
        fallback["fallback_detail"] = read_http_error_detail(exc)
        return fallback
    except ValueError as exc:
        fallback = deterministic_sheet_explanation(seed_song, recommendations)
        fallback["source"] = "fallback_deterministic"
        fallback["fallback_reason"] = "invalid_gemini_sheet_explanation"
        fallback["fallback_detail"] = str(exc)
        return fallback
    except (KeyError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        fallback = deterministic_sheet_explanation(seed_song, recommendations)
        fallback["source"] = "fallback_deterministic"
        fallback["fallback_reason"] = type(exc).__name__
        return fallback
