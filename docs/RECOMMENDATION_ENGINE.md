# Recommendation engine — technical overview

This document describes how the Skillevate Recommendation API turns **skills** and **preferences** into ranked links (videos, playlists, repositories, articles). It reflects the behavior after the latest quality improvements.

## End-to-end flow

1. **Request** — `POST /api/batch-recommendations` (primary) or `POST /api/recommendations` (legacy single-skill). Both use the same ranking and re-ranking pipeline; batch supports `language` per request, legacy v1 does not expose `language` on the request model (providers default to English relevance where applicable).

2. **Fetch** — For each skill, the orchestrator calls **YouTube**, **GitHub**, and **Dev.to** concurrently (`asyncio.gather`).

3. **Rank** — `core/ranking.RankingEngine` assigns a composite score (relevance, quality, authority, recency) with several multiplicative guards (meta-content, difficulty mismatch, depth vs “short” format, GitHub list penalty when the user asks for hands-on work).

4. **Re-rank** — `core/content_similarity.rerank_with_tfidf` blends TF–IDF cosine similarity with the score, filters very low matches, then applies **MMR** (maximal marginal relevance) so results are not near-duplicates. **Provider caps** stop any single source (especially Dev.to) from occupying the whole list when other providers also returned candidates.

5. **Response** — Same JSON shape as before: `SimplifiedCourse` items with `id`, `title`, `provider`, `url`, `description`, `tags`, `relevance_score`. YouTube playlist entries use ids prefixed with `youtube_pl_` and playlist URLs; videos keep `youtube_{videoId}` and watch URLs.

---

## YouTube (`providers/youtube_provider.py`)

### Videos and playlists

- **Search** runs for:
  - **Videos** — query built from skill + up to two short preference terms + `"tutorial"`, with `videoDuration` driven by preferences (see below).
  - **Playlists** — same skill context but phrasing oriented toward **courses/series** (`full course`, `playlist`).
- If preferences ask for **long-form** content without also asking for “quick” snippets, an **additional** `videoDuration=long` search is run to surface full-length tutorials.

### Preference → search behavior

Users express intent via the **preferences** array (no schema change). Examples:

| Intent | Example preference phrases | Effect |
|--------|-----------------------------|--------|
| Quick | `quick tutorials`, `short videos`, `crash course` | Shorter YouTube videos (`videoDuration=short`). |
| Deep / course-like | `comprehensive courses`, `full course`, `deep dive`, `in depth` | Long videos + extra long search; playlist search emphasized by query text. |
| Audience | `beginner`, `senior`, `working developer` | Used by ranking (difficulty / depth penalties), not as separate API fields. |

Default when neither quick nor comprehensive dominates: **medium**-length videos (previous default).

### Metadata enrichment

- **Videos** — After search, the provider calls `videos.list` with `part=snippet,statistics` so **tags** and full descriptions are populated (search alone does not return tags).
- **Playlists** — After search, `playlists.list` with `part=snippet,contentDetails` supplies **item counts**, used as a quality signal for playlists.

### Topical filter

Results must match the skill (skill phrase or expanded taxonomy terms in title or description). This reduces irrelevant hits from broad or authority-heavy channels.

### Removed behavior

The previous parallel **“MIT / Stanford / Harvard”** institute search was removed: it often introduced off-topic but high-prestige videos. Authority is handled in `core/authority.py` instead.

Internal YouTube-only metadata (playlist vs video, item count) is stored on `SimplifiedCourse` in a **private** attribute and is **not** exposed in JSON.

When preferences include course-style phrases (e.g. “full course”, “comprehensive”, “playlist”), **playlist** candidates receive a small score lift so they are more likely to appear alongside single videos.

---

## GitHub (`providers/github_provider.py`)

Repository search uses skill + optional preference terms and filters for educational intent (name/description keywords, stars, language heuristics for `language: "en"`).

**Ranking**: If preferences suggest **hands-on** work (`project`, `hands-on`, `build`, etc.), repositories whose names look like generic **awesome lists / roadmaps / resources** receive a small score penalty so project-oriented repos can surface first.

---

## Dev.to (`providers/devto_provider.py`)

Articles are loaded by tag (skill + optional preference tags), with filters on reading time, reactions, language, and educational cues in the title.

**MMR caps**: When YouTube or GitHub return any candidates, Dev.to’s share of the final list is **capped** so a strong Dev.to feed cannot fill every slot unless it is the only provider with results.

---

## Ranking (`core/ranking.py`)

- **Relevance** — Keyword overlap on title, description, tags; skill expansion from `core/skill_taxonomy.py`; spam and coherence multipliers.
- **Quality** — GitHub stars/forks; YouTube views/likes; YouTube **playlist** size; Dev.to reactions/comments.
- **Guard** — If relevance is low, **quality is capped** so viral but off-topic items cannot dominate.
- **Authority** — YouTube channels / GitHub orgs (`core/authority.py`).
- **Recency** — Exponential decay by published/push date.
- **Multipliers** — Meta-content penalty, difficulty mismatch, **depth vs short-format** penalty, GitHub curated-list penalty (see above).

---

## TF-IDF + MMR (`core/content_similarity.py`)

Corpus = title (weighted), description, tags. Query = skill + preferences. Scores are blended, then MMR trades off similarity to the query vs diversity among selected items, subject to per-provider caps.

---

## API compatibility

- **Request and response models** (`models/batch_models.py`, `models/schemas.py`) are unchanged in shape.
- New YouTube **playlist** entries remain `provider: "YouTube"` with distinct `id` / `url` patterns.

For setup and curl examples, see [README.md](../README.md).
