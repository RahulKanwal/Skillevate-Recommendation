# Skillevate Recommendation System — Architecture Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Design](#architecture-design)
3. [Application Flow](#application-flow)
4. [Recommendation Engine](#recommendation-engine)
5. [Authority Scoring](#authority-scoring)
6. [Component Details](#component-details)
7. [Data Models](#data-models)
8. [API Endpoints](#api-endpoints)
9. [Future Enhancements](#future-enhancements)

---

## System Overview

The Skillevate Recommendation System is a FastAPI-based microservice that aggregates educational content from multiple providers (YouTube, GitHub) and ranks it using a multi-signal scoring algorithm that considers relevance, content quality, source authority, and recency.

### Key Features
- Asynchronous concurrent API calls via `asyncio.gather()`
- Multi-provider content aggregation
- Multi-signal ranking: relevance + quality + authority + recency
- Spam/keyword-stuffing detection and penalty
- Title-description coherence check
- Authority boosting for official channels and trusted orgs
- Automatic deduplication
- RESTful API with OpenAPI documentation

### Technology Stack
- **Framework**: FastAPI 0.115+
- **HTTP Client**: httpx (async)
- **Data Validation**: Pydantic 2.10+
- **Server**: Uvicorn with auto-reload
- **Environment Management**: python-dotenv

---

## Architecture Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
│              (Web App, Mobile App, CLI, etc.)               │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/REST
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
│                         (main.py)                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              API Endpoint Layer                       │  │
│  │   POST /api/recommendations                           │  │
│  │   POST /api/batch-recommendations                     │  │
│  └──────────────────────┬───────────────────────────────┘  │
└─────────────────────────┼───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Recommendation Orchestration Layer              │
│     (api/recommendations.py, api/batch_recommendations.py)  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  • Request validation                                 │  │
│  │  • Provider initialization                            │  │
│  │  • Parallel API calls (asyncio.gather)               │  │
│  │  • Result aggregation                                 │  │
│  │  • Ranking & filtering                                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            │                           │
            ▼                           ▼
┌───────────────────────┐   ┌───────────────────────┐
│   YouTube Provider    │   │   GitHub Provider     │
│ (youtube_provider.py) │   │ (github_provider.py)  │
│                       │   │                       │
│ Returns:              │   │ Returns:              │
│  • title              │   │  • title              │
│  • channel_id  ◄──┐  │   │  • org_login   ◄──┐  │
│  • channel_name    │  │   │  • stars           │  │
│  • published_at    │  │   │  • forks           │  │
└───────────┬───────────┘   │  • pushed_at       │  │
            │               └───────────┬───────────┘
            ▼                           ▼
┌───────────────────────┐   ┌───────────────────────┐
│  YouTube Data API v3  │   │    GitHub REST API    │
│  (External Service)   │   │  (External Service)   │
└───────────────────────┘   └───────────────────────┘
            │                           │
            └─────────────┬─────────────┘
                          │ List[SimplifiedCourse]
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ranking Engine Layer                      │
│                     (core/ranking.py)                        │
│                                                              │
│   final_score = relevance(0.35) + quality(0.35)             │
│               + authority(0.20) + recency(0.10)             │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Relevance   │  │   Quality    │  │    Authority     │  │
│  │  • keyword   │  │  • stars     │  │  (core/          │  │
│  │    match     │  │  • forks     │  │   authority.py)  │  │
│  │  • spam      │  │  • log-norm  │  │  • official org  │  │
│  │    penalty   │  └──────────────┘  │  • trusted chan  │  │
│  │  • coherence │  ┌──────────────┐  └──────────────────┘  │
│  └──────────────┘  │   Recency    │                         │
│                    │  • exp decay │                         │
│                    │  • 1yr half  │                         │
│                    │    life      │                         │
│                    └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

#### 1. API Endpoint Layer (`main.py`)
- Receives HTTP requests
- CORS configuration
- Request routing and error handling

#### 2. Orchestration Layer (`api/recommendations.py`, `api/batch_recommendations.py`)
- Validates incoming requests
- Initializes content providers
- Executes parallel API calls
- Aggregates and ranks results
- Compiles final response with metadata

#### 3. Provider Layer (`providers/`)
- Abstracts external API interactions
- Transforms external data into `SimplifiedCourse` objects
- Now passes quality signals (stars, forks) and authority signals (channel_id, org_login) downstream

#### 4. Ranking Layer (`core/ranking.py`)
- Calculates multi-signal relevance scores
- Applies spam penalty and coherence check
- Removes duplicates and sorts results

#### 5. Authority Layer (`core/authority.py`)
- Maintains whitelists of trusted YouTube channels and GitHub orgs
- Returns authority score tier for any given source + skill combination
- Fully decoupled — update `AUTHORITY_SOURCES.md` and the dicts here to add new sources

#### 6. Data Model Layer (`models/`)
- `schemas.py` — original single-skill request/response models
- `batch_models.py` — batch request/response models + `SimplifiedCourse`

---

## Application Flow

### Complete Request-Response Flow

```
1. Client Request
   │
   ├─→ POST /api/recommendations
   │   Body: {
   │     "skill": "python programming",
   │     "difficulty": "beginner",
   │     "max_results": 10,
   │     "preferences": ["web development"]
   │   }
   │
   ▼
2. FastAPI Endpoint (main.py)
   │
   ├─→ Validates request using Pydantic schema
   ├─→ Calls get_recommendations()
   │
   ▼
3. Recommendation Orchestrator (api/recommendations.py)
   │
   ├─→ Initialize providers:
   │   ├─→ YouTubeProvider()
   │   └─→ GitHubProvider()
   │
   ├─→ Execute parallel API calls (asyncio.gather):
   │   │
   │   ├─→ YouTube Provider
   │   │   ├─→ Query: "{skill} tutorial"
   │   │   ├─→ Params: type=video, duration=medium, language=en
   │   │   ├─→ Parse response → SimplifiedCourse
   │   │   │   (includes channel_id, channel_name, published_at)
   │   │   └─→ Return List[SimplifiedCourse]
   │   │
   │   └─→ GitHub Provider
   │       ├─→ Query: "{skill} tutorial OR course OR learning"
   │       ├─→ Sort by stars descending
   │       ├─→ Filter: must contain educational keywords
   │       ├─→ Parse response → SimplifiedCourse
   │       │   (includes org_login, stars, forks, pushed_at)
   │       └─→ Return List[SimplifiedCourse]
   │
   ├─→ Aggregate: all_courses = youtube_results + github_results
   │
   └─→ Invoke Ranking Engine
       │
       ▼
4. Ranking Engine (core/ranking.py)
   │
   ├─→ For each course, compute final_score:
   │   │
   │   ├─→ relevance_score (weight: 0.35)
   │   │   ├─→ title keyword match    (50% of relevance)
   │   │   ├─→ description keyword match (35% of relevance)
   │   │   ├─→ tag match              (15% of relevance)
   │   │   ├─→ × spam_penalty         (halved if keyword density > 10%)
   │   │   └─→ × coherence_multiplier (0.7–1.0 based on title/desc overlap)
   │   │
   │   ├─→ quality_score (weight: 0.35)
   │   │   ├─→ GitHub: log1p(stars)/log1p(200k) × 0.7
   │   │   │          + log1p(forks)/log1p(50k)  × 0.3
   │   │   └─→ YouTube: 0.5 (neutral — no stats from search API)
   │   │
   │   ├─→ authority_score (weight: 0.20)
   │   │   ├─→ Lookup channel_id / org_login in core/authority.py
   │   │   ├─→ Official source for this skill → 1.0
   │   │   ├─→ Trusted educational platform  → 0.8
   │   │   └─→ Unknown source               → 0.0
   │   │
   │   └─→ recency_score (weight: 0.10)
   │       └─→ exp(-days_since_update / 365)
   │           today → 1.0 | 1 year ago → 0.37 | 3 years ago → 0.08
   │
   ├─→ Filter by difficulty (if specified)
   ├─→ Deduplicate by normalized title
   └─→ Sort by final_score descending
   │
   ▼
5. Response to Client
   {
     "skill": "python programming",
     "total_results": 10,
     "recommendations": [
       {
         "id": "youtube_abc123",
         "title": "Python Tutorial — Official",
         "provider": "YouTube",
         "relevance_score": 0.82,
         ...
       }
     ],
     "metadata": { "providers": {...} }
   }
```

---

## Recommendation Engine

### Scoring Formula

```
final_score = (
    relevance_score  × 0.35   +
    quality_score    × 0.35   +
    authority_score  × 0.20   +
    recency_score    × 0.10
)
```

Quality and authority together account for 55% of the score. This means keyword-rich but low-quality or unknown-source content cannot dominate the rankings.

---

### Signal 1 — Relevance Score (35%)

Measures how well the content matches the requested skill and preferences.

```
relevance = (
    title_match    × 0.50 +
    desc_match     × 0.35 +
    tag_match      × 0.15
) × spam_penalty × coherence_multiplier
```

**Keyword match logic (per field):**
```
if exact skill phrase in text:
    base = 0.6
else:
    base = (matching_skill_words / total_skill_words) × 0.5

if preferences provided:
    pref_bonus = (matching_prefs / total_prefs) × 0.4
    base += pref_bonus

return min(base, 1.0)
```

**Spam penalty (Improvement #2):**
```
density = skill_word_count_in_text / total_word_count
if density > 0.10:
    penalty = 0.5   ← relevance halved
else:
    penalty = 1.0
```

**Coherence multiplier (Improvement #4):**
```
title_words = meaningful words in title (stop words removed)
desc_words  = meaningful words in description
overlap     = |title_words ∩ desc_words| / |title_words|
coherence   = 0.7 + overlap × 0.3   # range: [0.7, 1.0]
```
A title that shares no words with its description scores at 70% of its raw relevance.

---

### Signal 2 — Quality Score (35%)

**GitHub (Improvement #1):**
```
star_score = log1p(stars) / log1p(200_000)
fork_score = log1p(forks) / log1p(50_000)
quality    = star_score × 0.7 + fork_score × 0.3
```

Log normalization prevents a 100k-star repo from completely dominating a 5k-star repo. Both are good; the difference is proportional, not linear.

| Stars | Quality Score |
|-------|--------------|
| 0     | 0.00         |
| 100   | 0.19         |
| 1,000 | 0.38         |
| 10,000| 0.57         |
| 50,000| 0.73         |
| 200,000| 1.00        |

**YouTube:** Returns 0.5 (neutral) — the basic search API doesn't return view/like counts. A future improvement can add a second API call to `/videos?part=statistics` to get real engagement data.

---

### Signal 3 — Authority Score (20%)

Rewards content from official and trusted educational sources. Defined in `core/authority.py` and documented in `AUTHORITY_SOURCES.md`.

| Tier | Score | Example |
|------|-------|---------|
| official | 1.0 | Docker official YouTube channel for a "docker" query |
| trusted_platform | 0.8 | freeCodeCamp, MIT OCW, Google for Developers |
| unknown | 0.0 | Random creator / unknown org |

**YouTube lookup order:**
1. Is `channel_id` in the official list for this skill? → 1.0
2. Is `channel_id` in the generic trusted list? → 0.8
3. Does `channel_name` match a trusted name? → 0.8
4. Otherwise → 0.0

**GitHub lookup order:**
1. Is `org_login` in the official list for this skill? → 1.0
2. Is `org_login` in the generic trusted list? → 0.8
3. Otherwise → 0.0

---

### Signal 4 — Recency Score (10%) — Improvement #3

```
days_old      = (today - published_at).days
recency_score = exp(-days_old / 365)
```

| Age | Score |
|-----|-------|
| Today | 1.00 |
| 6 months | 0.61 |
| 1 year | 0.37 |
| 2 years | 0.14 |
| 3 years | 0.05 |

Content with unknown dates gets a neutral 0.5.

---

### Worked Example

**Input:** skill = "docker", preferences = ["microservices"]

**Candidate A** — Docker official YouTube channel, published 3 months ago
```
relevance  = 0.70 (title + desc match, no spam)
quality    = 0.50 (YouTube neutral)
authority  = 1.00 (official Docker channel for "docker" skill)
recency    = 0.78 (3 months old)

final = 0.70×0.35 + 0.50×0.35 + 1.00×0.20 + 0.78×0.10
      = 0.245 + 0.175 + 0.200 + 0.078 = 0.698
```

**Candidate B** — Random creator, keyword-stuffed title, published 1 month ago
```
relevance  = 0.60 × 0.5 (spam penalty) = 0.30
quality    = 0.50 (YouTube neutral)
authority  = 0.00 (unknown channel)
recency    = 0.92 (1 month old)

final = 0.30×0.35 + 0.50×0.35 + 0.00×0.20 + 0.92×0.10
      = 0.105 + 0.175 + 0.000 + 0.092 = 0.372
```

Candidate A wins (0.698 vs 0.372) despite the spammy title of Candidate B.

---

## Authority Scoring

The authority system is split across two files:

- `core/authority.py` — Python dicts and scoring logic
- `AUTHORITY_SOURCES.md` — Human-readable registry with channel IDs, org names, and rationale

### Adding a New Trusted Source

1. Find the YouTube channel ID (permanent `UC...` identifier) or GitHub org login
2. Add an entry to `AUTHORITY_SOURCES.md` with the rationale
3. Add the ID/login to the appropriate dict in `core/authority.py`
4. No other code changes needed

### Trusted YouTube Channels (Generic)

| Channel | Why |
|---------|-----|
| freeCodeCamp.org | Non-profit, peer-reviewed full courses |
| Traversy Media | Industry-standard web dev tutorials |
| Google for Developers | Official Google developer content |
| IBM Technology | Official IBM educational content |
| MIT OpenCourseWare | Academic lectures |
| Corey Schafer | Deep-dive Python/programming tutorials |
| CS Dojo | CS fundamentals |

### Trusted GitHub Orgs (Generic)

`google`, `microsoft`, `ibm`, `meta`, `aws`, `awslabs`, `apache`, `cncf`, `freecodecamp`

---

## Component Details

### YouTube Provider (`providers/youtube_provider.py`)

**API call:**
```
GET /youtube/v3/search
  part=snippet
  q="{skill} tutorial"
  type=video
  videoDuration=medium
  relevanceLanguage=en
  maxResults=min(max_results, 25)
```

**Fields extracted into SimplifiedCourse:**
- `snippet.title`, `snippet.description`, `snippet.tags`
- `snippet.channelId` → `channel_id` (authority signal)
- `snippet.channelTitle` → `channel_name` (authority fallback)
- `snippet.publishedAt` → `published_at` (recency signal)

### GitHub Provider (`providers/github_provider.py`)

**API call:**
```
GET /search/repositories
  q="{skill} tutorial OR {skill} course OR {skill} learning"
  sort=stars
  order=desc
  per_page=min(max_results, 30)
```

**Pre-filter:** repo name or description must contain one of: `tutorial`, `course`, `learn`, `guide`, `example`

**Fields extracted into SimplifiedCourse:**
- `name`, `description`, `topics`
- `owner.login` → `org_login` (authority signal)
- `stargazers_count` → `stars` (quality signal)
- `forks_count` → `forks` (quality signal)
- `pushed_at` → `published_at` (recency signal)

### Ranking Engine (`core/ranking.py`)

**Public method:**
```python
rank_courses(courses, skill, preferences, difficulty) → List[SimplifiedCourse]
```

**Internal methods:**

| Method | Purpose |
|--------|---------|
| `_calculate_score` | Orchestrates all 4 signals into final score |
| `_relevance_score` | Keyword match × spam_penalty × coherence |
| `_keyword_match_score` | Per-field text matching with preference bonus |
| `_tag_match_score` | Tag/topic matching |
| `_spam_penalty` | Keyword density check |
| `_coherence_score` | Title/description word overlap |
| `_quality_score` | Log-normalized stars/forks |
| `_recency_score` | Exponential decay from published_at |
| `_authority_score` | Delegates to core/authority.py |
| `_deduplicate` | Normalized title deduplication |
| `_matches_difficulty` | Difficulty filter (Course objects only) |

---

## Data Models

### SimplifiedCourse (`models/batch_models.py`)

The internal representation used by both providers and the ranking engine.

```python
class SimplifiedCourse(BaseModel):
    # API response fields
    id: str
    title: str
    provider: str
    url: str
    description: str
    tags: List[str] = []
    relevance_score: float          # 0.0 – 1.0, set by ranking engine

    # Quality signals (used by ranking, not in API response)
    stars: Optional[int]            # GitHub stargazers_count
    forks: Optional[int]            # GitHub forks_count
    published_at: Optional[str]     # ISO date — YouTube publishedAt / GitHub pushed_at

    # Authority signals (used by ranking, not in API response)
    channel_id: Optional[str]       # YouTube channel ID (UC...)
    channel_name: Optional[str]     # YouTube channel title
    org_login: Optional[str]        # GitHub owner login
```

### Request Models

```python
# Single skill
RecommendationRequest:
    skill: str                      # required
    difficulty: DifficultyLevel     # beginner | intermediate | advanced | all
    max_results: int                # 1–50, default 10
    preferences: List[str] | None

# Batch
BatchRecommendationRequest:
    skills: List[SkillRequest]      # each has skill + optional preferences
    max_results: int                # 1–50, default 10
    language: str | None            # ISO 639-1 code
```

---

## API Endpoints

### POST /api/recommendations
Single skill recommendation.

```json
// Request
{
  "skill": "python programming",
  "difficulty": "beginner",
  "max_results": 10,
  "preferences": ["web development"]
}

// Response
{
  "skill": "python programming",
  "total_results": 10,
  "recommendations": [
    {
      "id": "youtube_abc123",
      "title": "...",
      "provider": "YouTube",
      "url": "...",
      "relevance_score": 0.7234
    }
  ],
  "metadata": {
    "providers": {
      "YouTube": {"status": "success", "count": 5},
      "GitHub": {"status": "success", "count": 5}
    },
    "total_fetched": 20,
    "filtered_count": 10
  }
}
```

### POST /api/batch-recommendations
Multiple skills in one request.

```json
// Request
{
  "skills": [
    {"skill": "python", "preferences": ["backend", "fastapi"]},
    {"skill": "docker", "preferences": ["microservices"]}
  ],
  "max_results": 5,
  "language": "en"
}
```

### GET /health
```json
{"status": "healthy"}
```

---

## Performance Characteristics

- Parallel API calls via `asyncio.gather()` — both providers run concurrently
- Typical response time: 1–3 seconds (bottleneck is external APIs)
- Stateless design — horizontally scalable
- No database dependencies

---

## Future Enhancements

### Near-term (no LLM required)
- YouTube statistics via second API call (`/videos?part=statistics`) for real view/like counts
- TF-IDF or BM25 to replace simple keyword matching — more robust against gaming
- Coursera provider (free public API)
- Redis caching for repeated queries

### Longer-term
- Cosine similarity with TF-IDF vectors for semantic relevance
- User preference learning from click history
- Rate limiting and quota management
- Analytics and monitoring dashboard

---

## Configuration

### Environment Variables

```bash
YOUTUBE_API_KEY=your_youtube_data_api_v3_key
```

### Adding a New Provider

1. Create `providers/your_provider.py` implementing `fetch_courses(skill, max_results) -> List[SimplifiedCourse]`
2. Populate quality/authority fields in `SimplifiedCourse` where available
3. Add to `asyncio.gather()` in `api/recommendations.py`
4. Add authority entries in `core/authority.py` and `AUTHORITY_SOURCES.md`
