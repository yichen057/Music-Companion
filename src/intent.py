"""Intent parsing for natural-language recommendation adjustments."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Dict, List


ALLOWED_MOODS = {
    "happy",
    "chill",
    "intense",
    "melancholy",
    "aggressive",
    "focused",
    "reflective",
    "dreamy",
    "peaceful",
}
ALLOWED_LANGUAGES = {"english", "instrumental", "spanish", "japanese"}
DEFAULT_INTENT = {
    "energy_delta": 0.0,
    "preferred_mood": None,
    "required_language": None,
    "preferred_tags": [],
    "avoid_tags": [],
    "requires_instrumental": None,
    "requires_acoustic": None,
    "confidence": 0.0,
    "source": "none",
    "fallback_reason": None,
    "fallback_detail": None,
}


def clamp(value: float, low: float, high: float) -> float:
    """Clamp a numeric value to a safe range."""
    return max(low, min(high, value))


def normalize_token(text: str) -> str:
    """Normalize short labels returned by an intent parser."""
    return text.strip().lower().replace(" ", "-")


def parse_intent_rule_based(
    intent_text: str,
    source: str = "rule_based",
    fallback_reason: str | None = None,
    fallback_detail: str | None = None,
) -> Dict:
    """Parse common music-intent phrases without an API dependency."""
    text = intent_text.lower()
    parsed = dict(DEFAULT_INTENT)
    parsed["source"] = source
    parsed["fallback_reason"] = fallback_reason
    parsed["fallback_detail"] = fallback_detail
    parsed["confidence"] = 0.35

    if any(term in text for term in ["more energetic", "upbeat", "faster", "workout"]):
        parsed["energy_delta"] = 0.2
    elif any(term in text for term in ["calmer", "softer", "relaxing", "sleep"]):
        parsed["energy_delta"] = -0.2

    if any(term in text for term in ["instrumental", "no lyrics", "without lyrics", "background"]):
        parsed["required_language"] = "instrumental"
        parsed["requires_instrumental"] = True
        parsed["confidence"] = max(parsed["confidence"], 0.6)

    if any(term in text for term in ["acoustic", "guitar", "piano"]):
        parsed["requires_acoustic"] = True
        parsed["confidence"] = max(parsed["confidence"], 0.55)

    tags: List[str] = []
    if any(term in text for term in ["study", "studying", "focus", "coding", "work"]):
        tags.append("focused")
        parsed["preferred_mood"] = "focused"
    if any(term in text for term in ["night", "late night", "rainy"]):
        tags.append("nocturnal")
    if any(term in text for term in ["cozy", "warm"]):
        tags.append("cozy")
    if any(term in text for term in ["dreamy", "soft"]):
        tags.append("dreamy")
    if tags:
        parsed["preferred_tags"] = tags
        parsed["confidence"] = max(parsed["confidence"], 0.65)

    return validate_intent(parsed)


def build_gemini_prompt(intent_text: str) -> str:
    """Build a constrained prompt for Gemini JSON intent parsing."""
    return f"""
You are an intent parser for a music recommendation system.

Convert the user's natural-language request into structured JSON.
Do not recommend songs.
Do not explain your answer.
Return only valid JSON.

Allowed output schema:
{{
  "energy_delta": number between -0.3 and 0.3,
  "preferred_mood": one of ["happy", "chill", "intense", "melancholy", "aggressive", "focused", "reflective", "dreamy", "peaceful"] or null,
  "required_language": one of ["english", "instrumental", "spanish", "japanese"] or null,
  "preferred_tags": list of lowercase strings,
  "avoid_tags": list of lowercase strings,
  "requires_instrumental": true, false, or null,
  "requires_acoustic": true, false, or null,
  "confidence": number between 0 and 1
}}

Interpretation rules:
- More upbeat, energetic, faster, or workout music should make energy_delta positive.
- Calmer, softer, relaxing, sleep, or quiet music should make energy_delta negative.
- Studying, coding, or focus should add "focused" to preferred_tags.
- Instrumental or no-lyrics requests should set required_language to "instrumental" and requires_instrumental to true.
- If the request is vague, keep fields null or empty and use a lower confidence.
- Never invent song titles.
- Never choose final recommendations.

User request:
{intent_text}
""".strip()


def extract_json_object(text: str) -> Dict:
    """Extract a JSON object from a model response."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Gemini response did not contain a JSON object.")

    return json.loads(cleaned[start:end + 1])


def parse_intent_with_gemini(intent_text: str, timeout: int = 12) -> Dict:
    """Parse intent text with Gemini and return validated structured fields."""
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
            {
                "parts": [
                    {"text": build_gemini_prompt(intent_text)}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
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
    parsed = extract_json_object(text)
    parsed["source"] = "gemini"
    return validate_intent(parsed)


def validate_intent(parsed: Dict) -> Dict:
    """Validate and sanitize parser output before it affects ranking."""
    result = dict(DEFAULT_INTENT)
    result.update(parsed)

    try:
        result["energy_delta"] = clamp(float(result["energy_delta"]), -0.3, 0.3)
    except (TypeError, ValueError):
        result["energy_delta"] = 0.0

    mood = result.get("preferred_mood")
    if mood is not None:
        mood = normalize_token(str(mood))
    result["preferred_mood"] = mood if mood in ALLOWED_MOODS else None

    language = result.get("required_language")
    if language is not None:
        language = normalize_token(str(language))
    result["required_language"] = language if language in ALLOWED_LANGUAGES else None

    result["preferred_tags"] = sanitize_tags(result.get("preferred_tags", []))
    result["avoid_tags"] = sanitize_tags(result.get("avoid_tags", []))
    result["requires_instrumental"] = sanitize_optional_bool(
        result.get("requires_instrumental")
    )
    result["requires_acoustic"] = sanitize_optional_bool(
        result.get("requires_acoustic")
    )

    try:
        result["confidence"] = clamp(float(result["confidence"]), 0.0, 1.0)
    except (TypeError, ValueError):
        result["confidence"] = 0.0

    return result


def sanitize_tags(tags) -> List[str]:
    """Return a clean list of short metadata tags."""
    if not isinstance(tags, list):
        return []
    cleaned = []
    for tag in tags:
        normalized = normalize_token(str(tag))
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned[:5]


def sanitize_optional_bool(value):
    """Keep booleans or null only."""
    return value if isinstance(value, bool) else None


def parse_intent(intent_text: str, use_gemini: bool = True) -> Dict:
    """Parse user intent with Gemini when available, otherwise use fallback."""
    if not intent_text or not intent_text.strip():
        return dict(DEFAULT_INTENT)

    if use_gemini:
        try:
            return parse_intent_with_gemini(intent_text)
        except urllib.error.HTTPError as exc:
            detail = read_http_error_detail(exc)
            return parse_intent_rule_based(
                intent_text,
                source="fallback_rule_based",
                fallback_reason=f"HTTPError_{exc.code}",
                fallback_detail=detail,
            )
        except (
            ValueError,
            KeyError,
            TimeoutError,
            json.JSONDecodeError,
            urllib.error.URLError,
        ) as exc:
            return parse_intent_rule_based(
                intent_text,
                source="fallback_rule_based",
                fallback_reason=type(exc).__name__,
            )

    return parse_intent_rule_based(intent_text)


def read_http_error_detail(exc: urllib.error.HTTPError) -> str:
    """Read a short HTTP error response body for transparent fallback logs."""
    try:
        body = exc.read().decode("utf-8")
    except Exception:
        return ""

    if not body:
        return ""

    compact = " ".join(body.split())
    return compact[:240]


def apply_intent_to_profile(profile: Dict, intent: Dict) -> Dict:
    """Apply parsed intent adjustments to a seed-song profile."""
    adjusted = dict(profile)
    adjusted["target_energy"] = clamp(
        adjusted["target_energy"] + intent.get("energy_delta", 0.0),
        0.0,
        1.0,
    )

    if intent.get("preferred_mood"):
        adjusted["favorite_mood"] = intent["preferred_mood"]
    if intent.get("required_language"):
        adjusted["preferred_language"] = intent["required_language"]
    if intent.get("requires_instrumental") is not None:
        adjusted["prefers_instrumental"] = intent["requires_instrumental"]
    if intent.get("requires_acoustic") is not None:
        adjusted["likes_acoustic"] = intent["requires_acoustic"]

    existing_tags = [
        tag for tag in adjusted.get("liked_mood_tags", "").split("|") if tag
    ]
    for tag in intent.get("preferred_tags", []):
        if tag not in existing_tags:
            existing_tags.append(tag)
    adjusted["liked_mood_tags"] = "|".join(existing_tags)

    return adjusted
