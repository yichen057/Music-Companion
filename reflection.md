# Reflection: From Music Recommender to Music Companion

## Overview
This project started as a deterministic music recommender and evolved into Music Companion, an AI-assisted music discovery and reflection app. The most important design lesson across both versions is that recommendation quality depends on clear scoring logic, reliable retrieval, and honest fallback behavior. AI is useful around the edges of the system, but the application should not depend on AI to compute rankings, invent IDs, or decide what data is true.

## 1. Base Recommender Lessons
The original recommender compared structured user profiles against song metadata. These experiments were useful because they showed how small scoring decisions change recommendation behavior in visible ways.

### 1.1 Cleanly Different Profiles Produce Cleanly Different Results
The High-Energy Pop Fan and Chill Lofi Listener had opposite preferences. One wanted upbeat, popular, high-energy pop, while the other wanted quiet, acoustic, instrumental study music. Their top results had no overlap: the pop profile favored `Sunrise City`, while the lofi profile favored `Library Rain`.

This was a good sign. When users disagree on genre, mood, energy, acousticness, instrumentalness, and popularity, the system should separate them clearly. This confirmed that the basic feature matching logic was working for simple, non-conflicting profiles.

### 1.2 Similar Profiles Revealed Weak Weights
The High-Energy Pop Fan and Acoustic Popular Pop profiles looked very similar, except the second profile asked for acoustic music. The result did not shift enough. `Sunrise City` still ranked highly even though it was not acoustic.

This showed that acousticness was underweighted. Genre, mood, and energy dominated the score, so the system treated acoustic preference as optional. The lesson was that feature weights communicate product priorities. If a user says a constraint matters, the scoring system needs enough weight to reflect that.

### 1.3 Conflicting Profiles Need Better Compromise Logic
The Sad But Energetic profile wanted classical, melancholy music but also high energy. That combination was contradictory in the catalog. The system ranked `Ghost Waltz` first because it matched genre and mood, even though its energy was far lower than requested.

This revealed a limitation of simple additive scoring. When preferences conflict, the system does not reason about compromise; it simply adds points and picks the highest total. That insight later influenced the AI integration strategy: AI should not directly rank songs unless the deterministic scoring behavior is still inspectable.

### 1.4 Weight Tuning Changed the Meaning of Recommendations
The Deep Intense Rock and Chill Metal profiles showed that genre can become too dominant. Under the original weights, the Chill Metal Listener received aggressive high-energy metal even though the requested mood was chill and low-energy. After lowering genre weight and increasing energy weight, the result shifted toward calmer songs that better matched the requested listening context.

The lesson was that genre should inform recommendations, not override the actual listening experience. Mood and energy often matter more for whether a recommendation feels right.

### 1.5 Catalog Coverage Limits Recommendation Quality
The Chill Metal Listener also exposed a catalog problem. The system could not recommend a true chill metal track because the catalog did not contain one. The best it could do was choose between low-energy non-metal songs and high-energy metal songs.

This is an important limitation: a recommender can only recommend what exists in its data. Improving scoring logic cannot fully compensate for missing catalog coverage.

## 2. How the Original Challenges Improved the System
The original project included four technical challenges. These became the foundation for the later AI version.

### Challenge 1: Advanced Features
Adding decade, mood tags, language, duration, and replay value increased the max score and gave the system more ways to differentiate songs. Mood tags were especially useful because they allowed partial vibe overlap instead of relying only on one broad mood label.

The trade-off was that every new feature also introduced new ways to distort ranking. Some features, such as decade and language, could boost songs even when they did not improve the actual vibe match. This reinforced the need to inspect score breakdowns rather than only final ranks.

### Challenge 2: Scoring Modes
The scoring modes made the system easier to experiment with. Balanced, genre-first, and energy-focused modes represented different recommendation philosophies without rewriting the scoring function.

This made the code more modular and easier to reason about. It also showed that no single scoring mode is universally correct. Different user contexts may need different ranking priorities.

### Challenge 3: Diversity Penalty
The diversity penalty made recommendations feel less repetitive. Before the penalty, the Chill Lofi Listener received multiple similar LoRoom tracks near the top. With the penalty, `Spacewalk Thoughts` moved higher, giving the result more variety while still preserving the user's core taste.

This became an important product lesson: a ranked list is not just a math result. It should feel like a useful playlist, not a duplicate-heavy dump of near-identical matches.

### Challenge 4: Visual Output
Switching from plain text to tables made the recommender easier to evaluate. The summary table showed ranks, title, artist, genre, mood, energy, and score at a glance. The breakdown column made debugging easier because it showed exactly why each song was selected.

This output style carried into the expanded project. Clear CLI labels now distinguish deterministic sections, AI-generated sections, and fallback sections.

## 3. From Base Project to AI System
The earlier recommender experiments became the foundation for the AI version. Because the scoring behavior was already explainable and testable, I used AI only around the edges of the system: intent parsing, narrative summaries, and explanation generation.

This boundary is important. The deterministic code owns retrieval, ranking, IDs, validation, and fallback behavior. Gemini helps translate language or make explanations more natural, but it is not trusted as the source of truth.

## 4. AI Integration Lessons

### Feature 1: Similar-Song Intent Parsing
Feature 1 starts with a searched seed song. The system retrieves that song from `data/songs.csv`, builds a similarity profile from its metadata, and ranks other songs with the existing scoring engine. Gemini is optional and is only called when the user provides a natural-language intent such as `more energetic but still instrumental for studying`.

The first design question was whether Gemini should directly decide recommendations. The final answer was no. Direct AI ranking would make the system harder to test and explain. Instead, Gemini parses intent into structured fields such as `energy_delta`, `preferred_mood`, `preferred_tags`, `required_language`, and instrumental/acoustic preferences. The local ranking engine then applies those fields to the seed-song profile and scores catalog songs normally.

The main failure cases were API errors and fallback behavior. Some simple intents produced the same result from Gemini and the local parser, which was expected. The local parser can handle obvious phrases, while Gemini is more useful for nuanced language such as `same cozy rainy-night feeling but less sleepy`.

The final Feature 1 implementation uses a two-layer parser: Gemini when available, and a rule-based fallback when Gemini is disabled, unavailable, or invalid. The CLI separates `Search confidence`, `Intent confidence`, and `Song score`, which makes debugging much clearer.

### Feature 2: Listening-History Playlist Explanations
Feature 2 recommends songs and albums from user listening history. The local system aggregates play history, builds a taste profile, ranks songs and albums, and groups ranked songs into playlist packages.

The first implementation asked Gemini to return structured JSON containing playlist packages, descriptions, and song IDs. This was too fragile. Gemini sometimes timed out, returned malformed JSON, or failed due to quota and model availability errors. The failures included `TimeoutError`, `HTTPError_404`, `HTTPError_429`, and `JSONDecodeError`.

The final design changed the AI boundary. Gemini no longer generates playlist JSON and no longer controls `song_ids`. The app builds packages locally, then Gemini returns plain text explanations in a fixed format: `Package Name: explanation`. The app parses those lines and attaches the explanations to deterministic package structures.

This made Feature 2 much more reliable. Gemini contributes language, but local code preserves recommendation correctness.

### Feature 3: Monthly and Yearly Listening Summaries
Feature 3 creates monthly and yearly listening summaries. The rankings are deterministic: top songs, artists, inferred albums, genres, moods, tags, and average energy all come from listening-history aggregation.

I decided to show capped rankings instead of dumping every listening-history record. The system reports up to 10 songs and up to 5 artists, albums, genres, moods, and tags. This keeps the recap readable and closer to real music-summary products.

The current sample output may show fewer than the cap because the dataset is small. If a user only has 8 valid songs in the selected period, the recap shows 8 songs rather than padding or inventing extra entries. This is another guardrail: the app summarizes available data but does not fabricate missing listening history.

Gemini is optional in this workflow. It only rewrites computed statistics into a short narrative summary. If Gemini fails, deterministic recap text is used.

### Feature 4: Sheet Music Matching
Feature 4 matches sheet music metadata for light music arrangements, especially piano and guitar. The system retrieves and ranks sheet music locally using song match, artist match, instrument, difficulty proximity, mood-tag overlap, light-music energy fit, and beginner-friendly flags.

This workflow does not search the live web. That is intentional for the current project scope. A real product could connect to a licensed sheet music provider or external API, but the current implementation uses curated metadata so the project remains reproducible and avoids inventing links or availability.

Gemini is optional and only explains why the top arrangement fits. During testing, Gemini sometimes returned truncated explanations. I added validation that rejects too-short or incomplete AI text and falls back to the deterministic explanation. I also added a `DEBUG_GEMINI=1` switch to inspect raw Gemini response metadata when debugging finish reasons.

### API Key Handling
During implementation, I changed the local Gemini setup from manually exporting the API key in every terminal session to loading it from a local `.env` file. This made the app easier to run reproducibly because a developer can open a new terminal and run the CLI without retyping the key.

The important guardrail is that `.env` is listed in `.gitignore`, so secrets stay local and are not staged by normal `git add .` usage. This is a small but important engineering detail: AI integrations often depend on external credentials, and the setup should be convenient without encouraging hardcoded or committed API keys.

## 5. Reliability, Ethics, and Final Takeaways
Reliability testing changed the system design. Gemini worked well for some language tasks, but it also exposed practical failure modes: quota limits, unsupported model names, timeouts, malformed JSON, and truncated explanations. The surprising part was that even a very short sheet music explanation could come back incomplete, which led me to add output-quality validation and deterministic fallback instead of trusting AI text by default.

The system also has ethical and misuse risks. A user could over-read a generated taste summary as a deep identity judgment, or mistake local sheet music metadata for verified real-world score availability. To reduce those risks, the app keeps rankings deterministic, labels AI-generated sections clearly, avoids inventing links or IDs, and falls back to grounded deterministic text when AI output is weak.

AI collaboration helped most during architecture and reliability review. A helpful suggestion was separating AI language tasks from deterministic ranking tasks. A flawed suggestion was the early JSON-based playlist explanation design, where Gemini was expected to produce structured package data. Testing showed that this was fragile, so the final design moved structure back into local code and limited Gemini to explanations.

The final system now includes four implemented workflows:

- Similar-song recommendation from a searched song, with optional Gemini intent parsing.
- User-level listening-history recommendations, with optional Gemini playlist explanations.
- Monthly and yearly listening summaries, with optional Gemini narrative summaries.
- Metadata-based sheet music matching for piano and guitar, with deterministic matching and fallback explanations.

The current test suite passes with:

```text
41 passed
```

The most important lesson is that reliable AI integration depends on choosing the right responsibility boundary. AI is useful for understanding language and writing explanations, but deterministic code should own retrieval, ranking, IDs, validation, and fallback behavior.
