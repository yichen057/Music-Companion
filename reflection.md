# Reflection: Comparing User Profile Outputs

## High-Energy Pop Fan vs. Chill Lofi Listener

The Pop Fan wants upbeat, popular, high-energy pop music (energy 0.85). The Lofi Listener wants the opposite — quiet, acoustic, instrumental tracks to study to (energy 0.35). Their top results are completely different worlds: Sunrise City (pop, happy, 0.82 energy) vs. Library Rain (lofi, chill, 0.35 energy), with zero overlap in their top 5.

This makes sense because they disagree on almost every preference — genre, mood, energy level, acoustic, instrumental, and popularity all point in opposite directions. It is like asking one person what they want to hear at a party and another what they want to hear in a library. The system correctly separates them, which tells us the scoring features are actually working when preferences are cleanly different.

## High-Energy Pop Fan vs. Acoustic Popular Pop

These two profiles look almost identical on paper — both want pop, happy, and similar energy (0.85 vs. 0.80). The only difference is that the Acoustic Popular Pop user set `likes_acoustic: True`. You would expect their results to shift toward acoustic-sounding pop music.

But that is not what happens. Sunrise City still wins for both profiles (5.47 vs. 4.96), even though Sunrise City has an acousticness of only 0.18 — meaning it is not acoustic at all. The acoustic preference only costs 0.5 points when it misses, and genre + mood + energy together are worth up to 4.0 points. So the system essentially ignores the acoustic request because it is not weighted heavily enough to matter. This is like telling a waiter "I want pasta, but make it gluten-free" and getting regular pasta anyway because the kitchen prioritizes the "pasta" part and treats "gluten-free" as optional.

## High-Energy Pop Fan vs. Deep Intense Rock

Both users want loud, high-energy music (0.85 vs. 0.90), but one wants happy pop and the other wants intense rock. Their #1 picks are completely different — Sunrise City (pop, happy) vs. Storm Runner (rock, intense) — which makes sense because genre and mood are the two biggest scoring features.

What is interesting is that Gym Hero (pop, intense, energy 0.93) shows up as #2 for both profiles. For the Pop Fan, it matches on genre (pop) and energy, but misses on mood (intense instead of happy). For the Rock Fan, it matches on mood (intense) and energy, but misses on genre (pop instead of rock). It earns similar scores through completely different reasons. This tells us that a high-energy song with broad appeal can "sneak into" any profile's top list just by being close enough on energy and matching one major feature — the system does not penalize for mismatches, it just does not reward them.

## Chill Lofi Listener vs. Sad But Energetic

The Lofi Listener wants calm, low-energy music (0.35). The Sad But Energetic user also likes quiet genres (classical) but wants high energy (0.90) — a contradictory combination, like asking for a loud lullaby.

The Lofi Listener gets a clean top 5 full of lofi and ambient tracks. The Sad But Energetic user gets Ghost Waltz (classical, melancholy, energy 0.30) as #1 despite wanting energy at 0.90. Ghost Waltz only scores 0.80 on the energy component out of a possible 2.0, but it locks in genre + mood (1.0 + 1.0 = 2.0) which no other song can match. The rest of their top 5 is a scattered mix — Focus Flow, Pixel Party, Library Rain — none of which match on genre or mood, just energy proximity and boolean features. This shows that when a user's preferences contradict each other, the system does not know how to compromise. It just picks whichever song wins the math, even if the result does not feel right to a human listener.

## Deep Intense Rock vs. Chill Metal Listener

Both users like heavy music — rock and metal are neighboring genres. But the Rock Fan wants it loud and intense (energy 0.90), while the Chill Metal Listener wants it quiet and calm (energy 0.20). Their results reveal the most important lesson from our experiments.

Under the original weights (genre = 2.0), both users got aggressive, high-energy songs at #1 — Storm Runner for Rock, Basement Fury for Metal. The system treated genre as the most important thing, almost like a filter. But recommending Basement Fury (aggressive, energy 0.96) to someone who asked for "chill, low-energy metal" is like recommending a horror movie to someone who said they like thrillers but want something relaxing tonight. The label matches, but the vibe is completely wrong.

After we shifted the weights (genre from 2.0 to 1.0, energy from 1.0 to 2.0), the Chill Metal Listener's #1 changed to Spacewalk Thoughts (ambient, chill, energy 0.28). This song is not metal at all, but it matches the mood and energy the user actually asked for. The Rock Fan's results barely changed because Storm Runner already matched on everything. This taught us that weight tuning matters most when user preferences conflict — and that genre should inform recommendations, not override everything else about what the user actually wants to hear.

## Chill Lofi Listener vs. Chill Metal Listener

Both users want chill, low-energy music — they agree on mood and energy but disagree on genre (lofi vs. metal). You would expect their top results to overlap on the chill/low-energy songs but diverge based on genre preference.

After the weight adjustment, that is roughly what happens. Library Rain and Spacewalk Thoughts appear near the top for both profiles — they are the chillest, lowest-energy songs in the catalog. The difference is that the Lofi Listener gets three lofi tracks at the top (Library Rain, Midnight Coding, Focus Flow) because the catalog has multiple lofi songs. The Metal Listener gets Basement Fury at #3 — the only metal song — but it feels out of place next to ambient and lofi tracks at #1 and #2. This highlights a catalog problem, not a scoring problem: if we had a song like "acoustic metal ballad, chill, energy 0.3" in the dataset, it would likely rank #1 for this user. The system can only recommend what it has.

With the diversity penalty turned on, the Lofi Listener's results improve noticeably. Instead of three lofi songs in the top 3 (two by LoRoom), Spacewalk Thoughts (ambient) jumps to #2 and Midnight Coding drops to #3 with a -1.5 genre penalty. The user still gets lofi at #1 and #3, but now they also discover an ambient track that matches their vibe. For the Metal Listener, the diversity penalty has less impact because the top results are already spread across different genres — the problem there was never repetition, it was the lack of chill metal in the catalog.

---

## How the Four Challenges Changed the System

### Challenge 1: Advanced Features

Adding five new features (decade, mood tags, language, duration, replay) increased the max score from 5.5 to 10.0 and gave the system more ways to differentiate songs. The mood tags feature was the most impactful — it rewards partial overlap between a user's vibes and a song's vibes, which is something the single "mood" field could never do. For example, the Deep Intense Rock profile matches Storm Runner on all three tags (aggressive + powerful + driving) for +0.90, while Gym Hero only matches on two (aggressive + euphoric → only euphoric overlaps with the user's tags, so +0.30). This creates meaningful separation between songs that previously scored identically on mood.

But more features also introduced new problems. Basement Fury climbed back to #1 for Chill Metal in Balanced mode because it gained +1.0 for decade match and +1.0 for language match. These features have nothing to do with vibe, but they added enough points to overcome the energy penalty. The lesson: every new feature is a trade-off. It helps some profiles and hurts others.

### Challenge 2: Scoring Modes

The Strategy pattern was the cleanest change architecturally. Three weight dictionaries, one scoring function — switching modes is just passing a different string. The most revealing comparison was the Chill Metal Listener across all three modes: Basement Fury at #1 in Genre-First (genre=3.0 dominates), Basement Fury at #1 in Balanced (decade and language help), Coffee Shop Stories at #1 in Energy-Focused (energy=3.0 rewards low-energy songs). No single mode is "correct" — each embodies a different philosophy about what matters most.

### Challenge 3: Diversity Penalty

The diversity penalty was the most practically useful change. Before it, the Chill Lofi Listener got two LoRoom tracks in the top 3 — same artist, same genre, very similar energy. With the penalty, LoRoom's second song gets -1.5 (repeat genre) or -4.5 (repeat genre + repeat artist), and Spacewalk Thoughts (ambient, different artist) rises to #2. The user still gets lofi as their top pick, but now the results feel like a curated playlist rather than a genre dump.

The penalty values (-3.0 for artist, -1.5 for genre) were chosen to be strong enough to matter but not so strong that they override clear matches. An artist penalty of 3.0 means a second song by the same artist needs to outscore alternatives by 3+ points to still make the list — that is a high bar, which is appropriate since hearing the same artist twice in 5 songs feels repetitive.

### Challenge 4: Visual Output

Switching from plain text to tabulate tables made a bigger difference than expected. The summary table lets you scan all 5 recommendations at a glance — title, artist, genre, mood, energy, score — without reading through walls of text. The detail cards underneath explain why each song was picked, with `+` for bonuses and `-` for diversity penalties. This two-layer format (overview first, details on demand) mirrors how real dashboards present information.

The formatted output also made debugging easier. When comparing results across modes, the table format made it obvious when rankings shifted — you could see at a glance that Spacewalk Thoughts jumped from #4 to #2 when diversity was turned on, without having to count through paragraphs of text.

---

# AI Integration Reflection: Feature 1 and Feature 2

## Overview
The AI integration work added Gemini to two parts of Music Companion, but in both cases the final design keeps the deterministic recommender in control of recommendation decisions. Gemini is used for language understanding and explanation, while local retrieval, scoring, validation, and fallback logic protect the system from unsupported AI outputs.

## Feature 1: Similar-Song Intent Parsing
Feature 1 starts with a searched seed song. The system retrieves that song from `data/songs.csv`, builds a similarity profile from its metadata, and ranks other songs with the existing scoring engine. Gemini is optional and is only called when the user provides a natural-language intent such as `more energetic but still instrumental for studying`.

The first design question was whether Gemini should directly decide recommendations. The final answer was no. Direct AI ranking would make the system harder to test and explain. Instead, Gemini parses intent into structured fields such as `energy_delta`, `preferred_mood`, `preferred_tags`, `required_language`, and instrumental/acoustic preferences. The local ranking engine then applies those fields to the seed-song profile and scores catalog songs normally.

### Failure Experience
The first Gemini failures were API-level failures, including HTTP errors from model access, permissions, or request setup. This exposed an important reliability requirement: the app should not require the user to manually decide whether Gemini is available. If Gemini fails, the system should continue automatically.

The second issue was that common intents often produced the same result from Gemini and the local fallback parser. This was not a bug. For simple phrases, the rule-based parser can correctly identify obvious signals like `more energetic`, `instrumental`, or `study`. Gemini becomes more useful for nuanced language, such as `same cozy rainy-night feeling but less sleepy`, where it can infer a softer adjustment than a keyword parser.

### Final Handling
The final Feature 1 implementation uses a two-layer parser:

- Gemini parser when `GEMINI_API_KEY` is available and `--intent` is provided.
- Local rule-based fallback if Gemini is disabled, unavailable, times out, or returns invalid output.

The CLI clearly reports which parser was used and separates three different confidence concepts:

- `Search confidence`: how confidently the seed song query matched a catalog song.
- `Intent confidence`: how confidently Gemini or the fallback parser understood the user's intent.
- `Song score`: how well each candidate song matches the final adjusted profile.

This made the system easier to debug because API failures, search ambiguity, and recommendation quality are not collapsed into one number.

## Feature 2: Listening-History Playlist Explanations
Feature 2 recommends songs and albums from user listening history. The local system aggregates play history, builds a taste profile, ranks songs and albums, and groups ranked songs into playlist packages. The intended AI role was to turn those retrieved signals into human-readable playlist explanations.

The first implementation asked Gemini to return structured JSON containing playlist packages, descriptions, and song IDs. This was too fragile. Gemini sometimes timed out because the prompt was too large. After reducing the prompt, Gemini returned malformed JSON. Adding JSON parsing cleanup, response schema, lower temperature, and higher output token limits improved the design but did not fully solve the issue. The model still occasionally returned invalid JSON such as missing delimiters.

### Failure Experience
The main Feature 2 failures were:

- `TimeoutError`: Gemini did not respond within the configured timeout.
- `HTTPError_404`: the selected model name was not supported by the current Gemini API endpoint.
- `HTTPError_429`: the selected model had no available quota or exceeded rate limits.
- `JSONDecodeError`: Gemini returned text that was not valid JSON even when JSON was requested.

The quota debugging also showed that model availability is model-specific. For example, a model can be listed with zero quota in the current project, causing a 429 even though the API key is valid. This made it important to report fallback reasons directly in the CLI instead of hiding all AI failures behind a generic message.

### Final Handling
The final Feature 2 design changed the boundary between AI and deterministic code. Gemini no longer generates playlist JSON and no longer controls `song_ids`. Instead:

1. The app aggregates listening history locally.
2. The app builds a taste profile locally.
3. The app ranks songs and albums locally.
4. The app builds playlist packages locally.
5. Gemini receives a compact prompt containing only the profile summary, top listening signals, top ranked songs, top ranked albums, package names, and optional context.
6. Gemini returns plain text lines in a fixed format: `Package Name: explanation`.
7. The app parses those lines and attaches the explanations to the deterministic package structure.
8. If Gemini fails, deterministic package explanations are used instead.

This final design is more reliable because the AI output is no longer trusted as application state. Gemini contributes useful language, but local code preserves recommendation correctness.



## Feature 3 Ranking Caps
For the wrapped recap feature, I decided to show capped rankings instead of dumping every listening-history record. The system reports up to 10 songs and up to 5 artists, albums, genres, moods, and tags. This keeps the recap readable and closer to real music-summary products, while still being grounded in deterministic counts.

The current sample output may show fewer than the cap because the demo dataset is small. For example, if a user only has 8 valid songs in the selected period, the recap shows 8 songs rather than padding or inventing extra entries. This is another guardrail: the app summarizes available data but does not fabricate missing listening history.

## API Key Handling
During implementation, I also changed the local Gemini setup from manually exporting the API key in every terminal session to loading it from a local `.env` file. This made the app easier to run reproducibly because a developer can open a new terminal and run the CLI without retyping the key.

The important guardrail is that `.env` is listed in `.gitignore`, so secrets stay local and are not staged by normal `git add .` usage. This is a small but important engineering detail: AI integrations often depend on external credentials, and the setup should be convenient without encouraging hardcoded or committed API keys.

## Final Result
Feature 1 now successfully supports Gemini-powered intent parsing with automatic fallback. Feature 2 now successfully supports Gemini-generated playlist explanations grounded in retrieved listening history and ranked candidates. The successful Feature 2 output is labeled in the CLI as:

```text
AI-generated section: Gemini created these package explanations from retrieved history and ranked candidates.
- source: gemini
```

The test suite currently passes with:

```text
26 passed
```

The most important lesson is that reliable AI integration depends on choosing the right responsibility boundary. AI is useful for understanding language and writing explanations, but deterministic code should own retrieval, ranking, IDs, validation, and fallback behavior.

