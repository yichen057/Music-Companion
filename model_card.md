# Model Card: Music Companion

## System Summary
Music Companion is an AI-assisted music discovery and reflection application built from an original content-based music recommender. The base recommender scores songs from structured metadata, and the expanded system adds similar-song search, user-level listening-history recommendations, monthly/yearly music summaries, and metadata-based sheet music matching.

The main design principle is that deterministic code owns retrieval, ranking, IDs, validation, and fallback behavior. Gemini is used only for constrained language tasks: intent parsing, playlist explanations, recap narratives, and optional sheet music explanations.

## Base Project
The original project was a **Music Recommender Simulation**. Songs were represented with metadata such as genre, mood, energy, acousticness, instrumentalness, popularity, decade, language, duration, replay value, and mood tags. User profiles were represented as structured preferences, and the system produced ranked song recommendations with score explanations.

The base scoring engine supports:

- weighted feature matching
- multiple scoring modes
- optional diversity penalties
- human-readable recommendation breakdowns

This deterministic recommender remains the ranking backbone of Music Companion.

## Implemented Workflows
### 1. Similar Song Recommendation
The user searches for a song, and the system retrieves the best matching seed song from the catalog. It builds a similarity profile from that song's metadata and ranks other songs locally. If the user provides natural-language intent, Gemini can parse that intent into structured ranking adjustments, but the local scoring engine still decides the final order.

### 2. Listening-History Recommendation
The system aggregates a user's listening history, builds a taste profile, recommends songs and albums, and groups ranked songs into playlist packages. Gemini can write short package explanations from retrieved history and ranked candidates, but it does not choose songs or generate trusted song IDs.

### 3. Monthly and Yearly Music Summaries
The system filters listening history by month or year and computes deterministic recap statistics: up to 10 top songs, 5 top artists, 5 inferred top albums, 5 top genres, 5 top moods, 5 top tags, and average energy. Gemini is optional and only rewrites those computed statistics into a short narrative summary.

### 4. Sheet Music Matching
The system retrieves sheet music metadata for piano and guitar arrangements, then ranks matches by song, artist, instrument, difficulty, mood-tag overlap, light-music fit, and beginner-friendly flags. Gemini is optional and only explains the top ranked arrangement from retrieved metadata. It does not create sheet music, verify real-world availability, or invent links.

## Intended Use
This project is intended for:

- explainable music recommendation experiments
- lightweight music discovery from structured catalog metadata
- user-level listening-history analysis
- monthly and yearly listening summaries
- piano and guitar sheet music metadata matching

It is not intended for:

- commercial music streaming deployment
- music licensing or rights decisions
- professional sheet music publishing
- verified external sheet music search
- high-stakes decision-making

## Inputs and Outputs
### Inputs
- song title or artist queries
- optional natural-language intent for similar-song search
- user IDs from the listening-history dataset
- month or year recap windows
- sheet music requests with instrument and optional difficulty
- optional Gemini API configuration through `.env`

### Outputs
- similar-song recommendations with scores and explanations
- parsed intent adjustments and intent confidence
- user-level song and album recommendations
- playlist packages with deterministic or Gemini-written explanations
- monthly/yearly top songs, artists, inferred albums, taste tags, and summaries
- sheet music metadata matches for piano or guitar
- fallback reasons when Gemini is unavailable or invalid

## Data Sources
Current local datasets:

- [data/songs.csv](data/songs.csv): song catalog metadata
- [data/albums.csv](data/albums.csv): album metadata for album recommendation and inferred wrapped albums
- [data/listening_history.csv](data/listening_history.csv): simulated user listening logs
- [data/sheet_music.csv](data/sheet_music.csv): curated piano/guitar sheet music metadata

The project does not currently use live music APIs, audio analysis, web search, or licensed sheet music providers.

## AI Features and Boundaries
### Structured Retrieval-Grounded Generation
The project uses structured data retrieval before generation. Gemini never receives an empty prompt; it receives retrieved or computed context such as seed song metadata, listening-history statistics, ranked candidates, playlist package names, recap statistics, or sheet music metadata.

### Gemini Intent Parsing
For similar-song search, Gemini parses natural-language intent into structured fields such as energy adjustment, preferred mood, required language, preferred tags, and instrumental/acoustic preferences. These values are validated before they affect local ranking.

### Gemini Explanation and Narrative Layers
For listening-history recommendations, Gemini writes playlist package explanations. For wrapped recaps, Gemini may rewrite deterministic statistics into a short narrative. For sheet music matching, Gemini may explain why the top ranked arrangement fits.

In all cases, Gemini does not control final recommendation membership, ranking statistics, song IDs, or sheet music availability.

## Reliability and Guardrails
The system includes these guardrails:

- deterministic fallback when Gemini fails, times out, exceeds quota, or returns invalid output
- explicit CLI labels for deterministic, AI-generated, and AI fallback sections
- validation and clamping for Gemini intent outputs
- local package structures for playlist recommendations, so Gemini cannot invent song IDs
- capped wrapped recap rankings to avoid dumping or fabricating listening history
- input validation for period, month, instrument, and difficulty
- rejection of truncated or too-short Gemini sheet music explanations
- `DEBUG_GEMINI=1` support for inspecting raw Gemini response metadata during debugging
- local `.env` support for API keys, with `.env` ignored by git

## Strengths
- Recommendation behavior is explainable because scoring remains deterministic.
- Retrieval-first design grounds generated text in local data.
- Fallback behavior keeps the app usable without Gemini.
- CLI output makes AI-generated and fallback sections visible.
- Tests cover ranking, retrieval, fallback, validation, and edge cases.

## Limitations and Risks
- The catalog and listening history are small and partially simulated.
- Recommendation quality depends heavily on metadata quality and coverage.
- The system is metadata-based, not audio-based.
- Top albums are inferred because `songs.csv` does not include album IDs.
- Sheet music matching uses curated metadata and does not verify real-world score availability.
- Exact string matching can be rigid for related moods, genres, or alternate song names.
- Wrapped summaries can oversimplify a user's taste if the listening history is sparse.
- Popularity, language, and catalog coverage biases can affect recommendations.

## Testing Status
The current test suite passes with:

```text
41 passed
```

The automated tests cover:

- base recommender scoring
- exact and partial song search
- similar-song ranking and seed exclusion
- local intent parsing and Gemini fallback labeling
- unsafe intent validation and profile adjustment
- listening-history aggregation and taste-profile construction
- song and album recommendation from history
- playlist package generation and validation
- monthly/yearly recap period filtering and top-stat calculations
- sheet music metadata loading, ranking, instrument filtering, and difficulty filtering
- deterministic fallback behavior
- truncated AI explanation rejection
- Gemini debug-response logging
- missing-user and invalid-input behavior

## Human-AI Collaboration Reflection
AI assistance was useful for brainstorming workflows, organizing documentation, and identifying reliability risks such as hallucinated IDs, malformed JSON, API quota failures, and over-trusting generated text.

Implementation still required direct engineering decisions. I had to inspect CLI output, tune the AI boundary, add deterministic fallbacks, validate responses, and write automated tests. The strongest lesson was that AI should improve language understanding and explanation quality, but deterministic code should own the parts that must be correct.

## Changes from the Base Project
Compared with the original recommender simulation, Music Companion adds:

- song-search-based similar recommendation
- Gemini intent parsing with rule-based fallback
- user-level listening-history recommendation
- album recommendation and playlist package generation
- monthly and yearly listening summaries
- sheet music metadata matching for piano and guitar
- `.env`-based API key loading
- stronger validation, fallback behavior, and automated tests

## Future Work
- AI performer workflows and Suno-style reinterpretation prompts
- live sheet music provider or licensed API integration
- audio embeddings for richer similarity search
- stronger personalization evaluation metrics
- larger and more realistic listening-history datasets
- album IDs in the song catalog for more accurate wrapped album rankings
