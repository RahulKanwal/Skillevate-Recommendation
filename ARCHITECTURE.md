# Skillevate Recommendation System - Architecture Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Design](#architecture-design)
3. [Application Flow](#application-flow)
4. [Recommendation Engine](#recommendation-engine)
5. [Component Details](#component-details)
6. [Data Models](#data-models)
7. [API Endpoints](#api-endpoints)

---

## System Overview

The Skillevate Recommendation System is a FastAPI-based microservice that aggregates educational content from multiple providers (YouTube, GitHub) and provides personalized learning recommendations based on user skills and preferences.

### Key Features
- Asynchronous API calls for concurrent data fetching
- Multi-provider content aggregation
- Intelligent ranking algorithm
- Automatic deduplication
- RESTful API with OpenAPI documentation
- Extensible architecture for adding new providers

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
│  │         POST /api/recommendations                     │  │
│  └──────────────────────┬───────────────────────────────┘  │
└─────────────────────────┼───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Recommendation Orchestration Layer              │
│                  (api/recommendations.py)                    │
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
│   Provider Layer      │   │   Provider Layer      │
│  YouTube Provider     │   │  GitHub Provider      │
│ (youtube_provider.py) │   │ (github_provider.py)  │
└───────────┬───────────┘   └───────────┬───────────┘
            │                           │
            ▼                           ▼
┌───────────────────────┐   ┌───────────────────────┐
│  YouTube Data API v3  │   │    GitHub REST API    │
│  (External Service)   │   │  (External Service)   │
└───────────────────────┘   └───────────────────────┘
            │                           │
            └─────────────┬─────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ranking Engine Layer                      │
│                     (core/ranking.py)                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  • Relevance scoring                                  │  │
│  │  • Keyword matching                                   │  │
│  │  • Popularity weighting                               │  │
│  │  • Deduplication                                      │  │
│  │  • Difficulty filtering                               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

#### 1. API Endpoint Layer (`main.py`)
- Receives HTTP requests
- CORS configuration
- Request routing
- Error handling
- Response formatting

#### 2. Orchestration Layer (`api/recommendations.py`)
- Validates incoming requests
- Initializes content providers
- Executes parallel API calls
- Aggregates results from multiple providers
- Invokes ranking engine
- Compiles final response with metadata

#### 3. Provider Layer (`providers/`)
- Abstracts external API interactions
- Handles API-specific authentication
- Transforms external data into internal format
- Error handling and retry logic
- Rate limiting compliance

#### 4. Ranking Layer (`core/ranking.py`)
- Calculates relevance scores
- Applies filtering rules
- Removes duplicates
- Sorts results by relevance

#### 5. Data Model Layer (`models/schemas.py`)
- Defines request/response structures
- Data validation
- Type safety
- API documentation

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
   ├─→ Logs incoming request
   ├─→ Calls get_recommendations()
   │
   ▼
3. Recommendation Orchestrator (api/recommendations.py)
   │
   ├─→ Initialize providers:
   │   ├─→ YouTubeProvider()
   │   └─→ GitHubProvider()
   │
   ├─→ Execute parallel API calls:
   │   │
   │   ├─→ asyncio.gather(
   │   │     youtube.fetch_courses("python programming", 10),
   │   │     github.fetch_courses("python programming", 10)
   │   │   )
   │   │
   │   ▼
   │   [Concurrent Execution]
   │   │
   │   ├─→ YouTube Provider
   │   │   ├─→ Build query: "python programming tutorial"
   │   │   ├─→ Call YouTube API
   │   │   ├─→ Parse response
   │   │   └─→ Return List[Course]
   │   │
   │   └─→ GitHub Provider
   │       ├─→ Build query: "python programming tutorial OR course"
   │       ├─→ Call GitHub API
   │       ├─→ Filter educational repos
   │       ├─→ Parse response
   │       └─→ Return List[Course]
   │
   ├─→ Aggregate results:
   │   └─→ all_courses = youtube_results + github_results
   │
   ├─→ Invoke Ranking Engine:
   │   │
   │   ▼
   │   4. Ranking Engine (core/ranking.py)
   │      │
   │      ├─→ For each course:
   │      │   ├─→ Calculate keyword match score (title: 40%)
   │      │   ├─→ Calculate keyword match score (description: 30%)
   │      │   ├─→ Calculate popularity score (rating: 20%)
   │      │   ├─→ Calculate tag match score (10%)
   │      │   └─→ Total relevance_score = weighted sum
   │      │
   │      ├─→ Filter by difficulty level
   │      ├─→ Remove duplicates (similar titles)
   │      └─→ Sort by relevance_score (descending)
   │
   ├─→ Apply max_results limit
   │
   └─→ Build response with metadata
   │
   ▼
5. Response to Client
   {
     "skill": "python programming",
     "total_results": 10,
     "recommendations": [
       {
         "id": "youtube_abc123",
         "title": "Python Tutorial for Beginners",
         "provider": "YouTube",
         "url": "https://youtube.com/watch?v=abc123",
         "relevance_score": 0.85,
         ...
       },
       ...
     ],
     "metadata": {
       "providers": {
         "YouTube": {"status": "success", "count": 5},
         "GitHub": {"status": "success", "count": 5}
       }
     }
   }
```

### Sequence Diagram

```
Client          FastAPI         Orchestrator    YouTube API    GitHub API    Ranking Engine
  │                │                 │               │              │              │
  ├─Request────────>│                 │               │              │              │
  │                ├─Validate────────>│               │              │              │
  │                │                 ├─Fetch─────────>│              │              │
  │                │                 ├─Fetch──────────┼─────────────>│              │
  │                │                 │               │              │              │
  │                │                 │<──Results──────┤              │              │
  │                │                 │<──Results──────┼──────────────┤              │
  │                │                 │               │              │              │
  │                │                 ├─Aggregate──────┼──────────────┼──────────────>│
  │                │                 │               │              │              │
  │                │                 │<──Ranked Results──────────────┼──────────────┤
  │                │<──Response──────┤               │              │              │
  │<──JSON Response┤                 │               │              │              │
  │                │                 │               │              │              │
```

---

## Recommendation Engine

### Ranking Algorithm

The ranking engine uses a weighted scoring system to calculate relevance:

```python
relevance_score = (
    keyword_match_title * 0.40 +      # Title relevance
    keyword_match_description * 0.30 + # Description relevance
    popularity_score * 0.20 +          # Rating/stars
    tag_match_score * 0.10             # Tag matching
)
```

### Scoring Components

#### 1. Keyword Match Score (Title & Description)

**Algorithm:**
```
if exact_skill_match_in_text:
    base_score = 0.8
else:
    skill_words = skill.split()
    matches = count(word in text for word in skill_words)
    base_score = matches / len(skill_words)

if preferences_provided:
    preference_matches = count(pref in text for pref in preferences)
    bonus = (preference_matches / len(preferences)) * 0.2
    base_score += bonus

return min(base_score, 1.0)
```

**Example:**
- Skill: "python programming"
- Title: "Python Programming Tutorial for Beginners"
- Exact match found → base_score = 0.8
- Preferences: ["web development"]
- "web" not in title → no bonus
- Final title score: 0.8

#### 2. Popularity Score

**Algorithm:**
```
if course.rating exists:
    popularity_score = min(rating / 5.0, 1.0)
else:
    popularity_score = 0.0
```

**Example:**
- GitHub repo with 4,500 stars
- Normalized rating: min(4500/1000, 5.0) = 5.0
- Popularity score: 5.0 / 5.0 = 1.0

#### 3. Tag Match Score

**Algorithm:**
```
if skill in tags:
    score = 1.0
else:
    score = 0.0

if preferences:
    pref_matches = count(pref in tags for pref in preferences)
    score += pref_matches / len(preferences)

return min(score / 2, 1.0)
```

### Filtering & Deduplication

#### Difficulty Filtering
```python
if difficulty != "all":
    courses = [c for c in courses 
               if c.difficulty is None or 
                  c.difficulty.lower() == difficulty.lower()]
```

#### Deduplication
```python
# Normalize titles by removing special characters
normalized_title = re.sub(r'[^\w\s]', '', title.lower())

# Keep only first occurrence of each normalized title
seen_titles = set()
unique_courses = []
for course in courses:
    if normalized_title not in seen_titles:
        seen_titles.add(normalized_title)
        unique_courses.append(course)
```

### Example Calculation

**Input:**
- Skill: "javascript"
- Course: "JavaScript Tutorial for Beginners"
- Description: "Learn JavaScript from scratch with practical examples"
- Rating: 4.5/5
- Tags: ["javascript", "tutorial", "beginner"]

**Calculation:**
```
Title Match:
  - "javascript" in title → 0.8
  - Weight: 0.8 × 0.40 = 0.32

Description Match:
  - "javascript" in description → 0.8
  - Weight: 0.8 × 0.30 = 0.24

Popularity:
  - Rating: 4.5/5 = 0.9
  - Weight: 0.9 × 0.20 = 0.18

Tag Match:
  - "javascript" in tags → 1.0
  - Weight: (1.0/2) × 0.10 = 0.05

Total Relevance Score: 0.32 + 0.24 + 0.18 + 0.05 = 0.79
```

---

## Component Details

### 1. YouTube Provider (`providers/youtube_provider.py`)

**Purpose:** Fetch educational videos from YouTube Data API v3

**Key Methods:**
- `fetch_courses(skill, max_results)` - Main entry point
- `_parse_response(data)` - Transform API response to Course objects

**API Parameters:**
```python
{
    "part": "snippet",
    "q": f"{skill} tutorial",
    "type": "video",
    "maxResults": max_results,
    "key": api_key,
    "videoDuration": "medium",  # Filter short videos
    "relevanceLanguage": "en"
}
```

**Error Handling:**
- Returns empty list on API failure
- Logs errors for debugging
- Graceful degradation (other providers still work)

### 2. GitHub Provider (`providers/github_provider.py`)

**Purpose:** Fetch educational repositories from GitHub

**Key Methods:**
- `fetch_courses(skill, max_results)` - Main entry point
- `_parse_response(data, skill)` - Transform and filter results

**Query Construction:**
```python
query = f"{skill} tutorial OR {skill} course OR {skill} learning"
```

**Filtering Logic:**
```python
# Only include repos with educational keywords
keywords = ["tutorial", "course", "learn", "guide", "example"]
if any(keyword in name.lower() or keyword in description.lower() 
       for keyword in keywords):
    include_repo = True
```

**Rating Calculation:**
```python
# Convert GitHub stars to 5-star rating
rating = min(stargazers_count / 1000, 5.0)
```

### 3. Ranking Engine (`core/ranking.py`)

**Purpose:** Score, filter, and sort recommendations

**Key Methods:**
- `rank_courses()` - Main orchestration
- `_calculate_score()` - Compute relevance score
- `_keyword_match_score()` - Text matching logic
- `_tag_match_score()` - Tag matching logic
- `_matches_difficulty()` - Difficulty filtering
- `_deduplicate()` - Remove duplicates

**Extensibility:**
- Easy to adjust weights
- Can add new scoring factors
- Pluggable filtering rules

---

## Data Models

### Request Model (`RecommendationRequest`)

```python
{
    "skill": str,                    # Required, min_length=1
    "difficulty": DifficultyLevel,   # "beginner"|"intermediate"|"advanced"|"all"
    "max_results": int,              # Default: 10, Range: 1-50
    "preferences": List[str] | None  # Optional keywords
}
```

### Response Model (`RecommendationResponse`)

```python
{
    "skill": str,
    "total_results": int,
    "recommendations": List[Course],
    "metadata": {
        "providers": {
            "YouTube": {"status": "success", "count": 5},
            "GitHub": {"status": "success", "count": 5}
        },
        "total_fetched": int,
        "filtered_count": int
    }
}
```

### Course Model

```python
{
    "id": str,                    # Unique identifier
    "title": str,                 # Course/video title
    "provider": str,              # "YouTube" | "GitHub"
    "url": str,                   # Direct link
    "description": str,           # Content description
    "difficulty": str | None,     # Difficulty level
    "duration": str | None,       # Time to complete
    "rating": float | None,       # 0.0 - 5.0
    "tags": List[str],            # Keywords/topics
    "relevance_score": float,     # 0.0 - 1.0
    "thumbnail": str | None       # Image URL
}
```

---

## API Endpoints

### 1. Root Endpoint
```
GET /
```
**Response:**
```json
{
    "message": "Skillevate Recommendation API",
    "version": "1.0.0",
    "endpoints": {
        "recommendations": "/api/recommendations"
    }
}
```

### 2. Health Check
```
GET /health
```
**Response:**
```json
{
    "status": "healthy"
}
```

### 3. Get Recommendations
```
POST /api/recommendations
```

**Request Body:**
```json
{
    "skill": "python programming",
    "difficulty": "beginner",
    "max_results": 10,
    "preferences": ["web development", "practical projects"]
}
```

**Response:** (See RecommendationResponse model above)

**Status Codes:**
- `200 OK` - Success
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Server error

---

## Performance Characteristics

### Concurrency
- Parallel API calls using `asyncio.gather()`
- Non-blocking I/O with httpx AsyncClient
- Typical response time: 1-3 seconds (depends on external APIs)

### Scalability
- Stateless design (easy horizontal scaling)
- No database dependencies
- Can add caching layer (Redis) for improved performance

### Error Resilience
- Partial results on provider failure
- Graceful degradation
- Comprehensive error logging

---

## Future Enhancements

### Phase 2: LLM Integration
- Query enhancement using GPT-4
- Semantic search with embeddings
- Content summarization
- Personalized difficulty assessment

### Phase 3: Additional Features
- User preference learning
- Content caching (Redis)
- More providers (Coursera, edX, Khan Academy)
- Rate limiting and quota management
- Analytics and monitoring

---

## Configuration

### Environment Variables

```bash
# Required for YouTube
YOUTUBE_API_KEY=your_youtube_api_key

# Optional for future LLM features
OPENAI_API_KEY=your_openai_api_key
```

### Adding New Providers

1. Create new provider class in `providers/`
2. Implement `fetch_courses(skill, max_results)` method
3. Return `List[Course]` objects
4. Add to orchestrator in `api/recommendations.py`
5. Update `asyncio.gather()` call

**Example:**
```python
# providers/coursera_provider.py
class CourseraProvider:
    async def fetch_courses(self, skill: str, max_results: int) -> List[Course]:
        # Implementation
        pass

# api/recommendations.py
coursera = CourseraProvider()
results = await asyncio.gather(
    youtube.fetch_courses(...),
    github.fetch_courses(...),
    coursera.fetch_courses(...)  # Add new provider
)
```

---

## Conclusion

The Skillevate Recommendation System provides a robust, scalable foundation for aggregating and ranking educational content. Its modular architecture allows easy extension with new providers and ranking algorithms, while the async design ensures optimal performance.
