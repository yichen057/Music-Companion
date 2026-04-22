# Model Card: Music Companion

## System Name
Music Companion

## Project Summary
Music Companion is an AI-powered music application that extends a base content-based recommender into a broader system for recommendation, listening-history analysis, recap generation, and sheet music matching.

## Base Functionality
The base system is a content-based music recommender implemented in [src/recommender.py](src/recommender.py). Songs are represented by structured metadata, and users are represented by a taste profile. The system scores each song against the profile and returns the highest-ranked results.

The current scoring system uses:

- genre matching
- mood matching
- energy similarity
- acousticness preference matching
- instrumentalness preference matching
- popularity preference matching
- decade proximity
- mood-tag overlap
- language matching
- duration proximity
- replay-value matching

The base recommender also supports multiple scoring modes and an optional diversity penalty.

## AI-Enhanced Functionality
The expanded application design adds four higher-level workflows.

### 1. Similar Song Recommendation
The user searches for a song, and the system retrieves the seed song's metadata before ranking other songs with similar attributes. If the user provides a natural-language intent, Gemini can parse that request into structured ranking adjustments while the local scoring engine still decides the final order.

### 2. Habit-Based Recommendation
The system aggregates listening history, builds a taste profile, and recommends songs and albums that fit the user's habits. This workflow is implemented with simulated listening-history data. It also groups ranked songs into playlist packages and can use Gemini to generate grounded package explanations from retrieved user-history and recommendation context. Gemini only writes explanations; local ranking and package construction decide the actual recommendations.

### 3. Monthly and Yearly Music Wrapped
The system summarizes listening activity over time and generates a recap with top songs, top artists, top albums, and a taste summary.

### 4. Sheet Music Matching
The system retrieves sheet music resources that best match a requested song, instrument, and difficulty level, especially for piano and guitar.

## Intended Use
This project is intended for:

- experimentation with explainable recommendation workflows
- testing retrieval-based recommendation and recap logic
- lightweight music discovery and reflection scenarios

It is not intended for:

- commercial music streaming deployment
- music licensing or rights decisions
- professional sheet music publishing
- high-stakes decision-making

## Intended Users
The system is designed for:

- music listeners exploring similar songs
- users who want general music and album recommendations
- users who want monthly or yearly listening summaries
- beginner and casual musicians searching for piano or guitar sheet music

## Core AI Features
### Retrieval-Augmented Generation
The system retrieves structured context before producing outputs. For example:

- song search retrieves seed-song metadata before recommending similar tracks
- listening recap retrieves aggregated statistics before generating summary text
- sheet music matching retrieves music-sheet entries before ranking options

This grounding step is central to the system design.

### Gemini Integration
Gemini is used in two constrained ways. For similar-song search, it parses optional user intent into structured fields that the recommender can validate and apply. For habit-based recommendation, it writes short playlist package explanations from locally retrieved listening history, ranked songs, ranked albums, and optional context. Gemini does not directly select final songs or produce trusted song IDs. If Gemini times out, exceeds quota, fails, or returns unparseable output, the system automatically uses a deterministic fallback and reports the fallback source and short error detail. The CLI labels deterministic, AI-generated, and fallback sections so users can tell which parts used Gemini.

### Reliability and Validation
The system includes planned validation and fallback behavior:

- recap outputs are checked against computed statistics
- missing or ambiguous inputs are handled safely
- logging captures retrieval and ranking steps
- fallback summaries are used when data is insufficient
- Gemini parser outputs are validated, clamped, and backed up by a local rule-based parser
- Gemini playlist explanations are attached to deterministic package structures, so recommendation membership remains locally controlled

These are the main advanced AI components of the project and they are integrated directly into the recommendation, recap, and matching workflows.

## Inputs
The full application design accepts:

- song title queries
- optional natural-language intent text for similar-song search
- user identifiers
- listening history records
- recap time windows such as month or year
- sheet music requests with instrument and optional difficulty

## Outputs
The system may return:

- similar-song recommendations
- parsed intent adjustments and confidence scores
- personalized song and album recommendations
- playlist packages with grounded explanations
- monthly and yearly listening recaps
- sheet music matches
- explanation text grounded in retrieved metadata

The system separates three scoring concepts: search confidence measures seed-song retrieval quality, intent confidence measures how strongly Gemini or the fallback parser understood the user's natural-language adjustment, and song score measures candidate-song fit against the final adjusted profile.

## Data Sources
### Current Data
- [data/songs.csv](data/songs.csv)
- [data/albums.csv](data/albums.csv)
- [data/listening_history.csv](data/listening_history.csv)

### Planned Data
- `data/sheet_music.csv`

The current implementation supports song-level recommendation, similar-song search, and habit-based song and album recommendation. The remaining workflows depend on the planned datasets being added and validated.

## How the System Works
### Base Recommender
The system loads songs, compares each song to a structured user profile, computes a weighted score, and returns the top-ranked results.

### Similar Song Recommendation
The system retrieves a seed song from the catalog, reuses its features as a similarity profile, optionally adjusts that profile with parsed intent, and ranks other songs against the final profile.

### Habit-Based Recommendation
The system aggregates listening history into summary statistics such as top genres, top artists, top moods, top tags, language preference, and typical energy levels, then converts those signals into recommendation targets for songs and albums. Ranked songs are grouped locally into playlist packages such as Core Taste Mix, Context Fit, and Discovery Stretch. Gemini receives a compact retrieved context and returns line-based package explanations, which are attached to the local package structure; deterministic fallback explanations are used if the AI call fails.

### Monthly and Yearly Wrapped
The system will filter listening history by time period, compute top songs, artists, and albums, and generate a natural-language recap grounded in those statistics.

### Sheet Music Matching
The system will retrieve matching sheet music resources based on song title, instrument, and optionally difficulty, then rank the best available options.

## Strengths
- The base recommender is transparent and explainable.
- Weighted feature matching makes recommendation behavior easy to inspect.
- Diversity penalties reduce repetitive results.
- Retrieval-based design keeps generated text tied to real data.
- The application covers both recommendation and reflective summary use cases.

## Limitations
- The current repository uses a small and partially simulated music catalog.
- Recommendation quality depends heavily on metadata quality.
- The current scoring logic is metadata-based rather than audio-based.
- The planned recap and sheet-music workflows require additional implementation and, for sheet music, an additional dataset.
- Exact string matching can be too rigid for related moods or genres.

## Biases and Risks
### Metadata Bias
If tags such as genre, mood, or language are incomplete or inconsistent, recommendations may be skewed.

### Catalog Coverage Bias
Genres with only one or two songs are disadvantaged compared with genres that have more entries.

### Popularity Bias
Songs marked as popular may receive repeated advantages, while niche songs remain buried.

### Language Bias
If the catalog contains mostly one language, multilingual or non-English listeners may receive weaker personalization.

### Summary Simplification Risk
Monthly or yearly recap text may oversimplify a user's listening identity if it compresses diverse behaviors into a small number of labels.

## Failure Cases
- the song query does not match any title in the catalog
- multiple songs match the same query ambiguously
- listening history is too sparse to build a stable taste profile
- top recap outputs conflict with summary text
- no sheet music exists for the requested instrument or difficulty

## Guardrails
The full project design includes:

- input validation for CLI arguments, Gemini outputs, and dataset fields
- fallback responses for missing song or sheet music matches
- recap validation against computed statistics
- logging of retrieval, ranking, and validation decisions
- safe handling of insufficient listening history
- automatic local fallback when Gemini is unavailable, including reported fallback reasons such as HTTP or network errors

## Testing Strategy
The testing plan covers:

- correctness of base recommender ranking
- exact and partial song-query matching
- exclusion of the seed song from similar-song outputs
- user-history aggregation and profile building
- recap statistics for monthly and yearly filtering
- validation checks for recap consistency
- instrument and difficulty filtering for sheet music matches
- edge cases involving missing or ambiguous inputs

## Current Testing Status
The current repository includes tests for the base recommender in [tests/test_recommender.py](tests/test_recommender.py), similar-song search tests in [tests/test_search.py](tests/test_search.py), listening-history recommendation tests in [tests/test_history.py](tests/test_history.py), and playlist package tests in [tests/test_playlist.py](tests/test_playlist.py). The current test suite passes with `26 passed`. Manual evaluation of the base system found:

- strong performance when profile preferences align with the catalog
- improved behavior after reducing genre dominance and increasing energy weight
- better result variety when diversity penalties are enabled
- visible failure cases for rare genres, exact-match rigidity, and sparse catalog coverage

The recap and sheet-music workflows are still under implementation and will require additional automated tests once their modules are added.

## Planned Evaluation
The next evaluation steps are:

- additional ranking checks for more varied user histories
- validation checks for monthly and yearly recap statistics
- error-handling tests for missing song queries and missing sheet music
- manual review of recommendation quality and recap accuracy

## Human-AI Collaboration Reflection
AI tools were useful during the design process for brainstorming user workflows, naming modules, framing system architecture, and refining documentation structure. They also helped surface blind spots such as catalog bias, popularity feedback loops, and the need to separate base functionality from AI-enhanced functionality in the documentation.

However, implementation details still require manual verification. Score calculations, ranking behavior, dataset design, and testing logic must be checked directly in code. AI assistance accelerated planning and writing, but it did not replace the need for precise engineering decisions or manual validation.

## Changes from the Base Project
Compared with the original music recommender simulation, this expanded project adds a broader product direction:

- similar-song retrieval from song search
- listening-history-based personalization
- monthly and yearly listening recaps
- sheet music matching
- logging and validation as first-class design requirements

The original weighted recommender remains the core ranking component.

## Future Work
- AI performer workflows
- Suno-style reinterpretation prompts
- multi-instrument arrangement planning
- audio embeddings for richer similarity search
- stronger evaluation metrics for personalization quality
