# Design Document: Multi-Skill Batch Recommendations

## Overview

This design enhances the Skillevate recommendation system to support batch processing of multiple skills in a single API request. The enhancement maintains the existing async architecture and ranking algorithm while introducing a new request/response structure that supports per-skill preferences, language filtering, and simplified course objects.

### Key Design Decisions

1. **New endpoint vs. endpoint modification**: Create a new `/api/batch-recommendations` endpoint to maintain backward compatibility while allowing the old endpoint to be deprecated gradually
2. **Parallel processing**: Use `asyncio.gather()` with nested parallelism - outer level for skills, inner level for providers per skill
3. **Language filtering**: Implement at the provider level to reduce unnecessary API calls and data transfer
4. **Preference handling**: Extend existing keyword matching in the ranking engine to support new preference categories
5. **Error isolation**: Ensure failures in one skill's processing don't affect other skills in the batch

### Design Principles

- **Maintain async performance**: All I/O operations remain non-blocking
- **Fail gracefully**: Partial results are better than complete failure
- **Keep it simple**: Reuse existing ranking logic with minimal modifications
- **Backward compatible**: Old endpoint remains functional during migration period

## Architecture

### High-Level Flow

```
Client Request (Multiple Skills)
    ↓
FastAPI Endpoint (/api/batch-recommendations)
    ↓
Batch Orchestrator
    ↓
[Parallel Processing per Skill]
    ↓
For each skill:
    ↓
    Provider Fetching (YouTube, GitHub in parallel)
    ↓
    Ranking Engine (per skill)
    ↓
    Result Aggregation
    ↓
[End Parallel Processing]
    ↓
Response Assembly
    ↓
Client Response (Skill Results List)
```

### Concurrency Model

```python
# Outer parallelism: Process all skills concurrently
skill_results = await asyncio.gather(
    process_skill(skill_obj_1, max_results, language),
    process_skill(skill_obj_2, max_results, language),
    process_skill(skill_obj_3, max_results, language),
    return_exceptions=True
)

# Inner parallelism (within each process_skill): Fetch from providers concurrently
async def process_skill(skill_obj, max_results, language):
    provider_results = await asyncio.gather(
        youtube.fetch_courses(skill_obj.skill, max_results, language),
        github.fetch_courses(skill_obj.skill, max_results, language),
        return_exceptions=True
    )
    # Rank and return
```

## Components and Interfaces

### 1. New Data Models

#### BatchRecommendationRequest

```python
class SkillRequest(BaseModel):
    """Individual skill with optional preferences"""
    skill: str = Field(..., min_length=1, description="Skill or topic to learn")
    preferences: Optional[List[str]] = Field(
        default=None, 
        description="Career goals, learning styles, time commitments, or technologies"
    )

class BatchRecommendationRequest(BaseModel):
    """Batch request for multiple skills"""
    skills: List[SkillRequest] = Field(
        ..., 
        min_length=1,
        description="List of skills to get recommendations for"
    )
    max_results: int = Field(
        default=10, 
        ge=1, 
        le=50,
        description="Maximum results per skill"
    )
    language: Optional[str] = Field(
        default=None,
        description="ISO 639-1 language code (e.g., 'en', 'es', 'fr')"
    )
```

#### SimplifiedCourse

```python
class SimplifiedCourse(BaseModel):
    """Simplified course object without difficulty, duration, rating, thumbnail"""
    id: str
    title: str
    provider: str
    url: str
    description: str
    tags: List[str] = []
    relevance_score: float = Field(ge=0.0, le=1.0)
```

#### SkillRecommendationResult

```python
class SkillRecommendationResult(BaseModel):
    """Recommendations for a single skill"""
    skill: str
    total_results: int
    recommendations: List[SimplifiedCourse]
```

#### BatchRecommendationResponse

```python
class BatchRecommendationResponse(BaseModel):
    """Response containing results for all skills"""
    results: List[SkillRecommendationResult]
    metadata: dict = Field(default_factory=dict)
```

### 2. Modified Provider Interface

Both `YouTubeProvider` and `GitHubProvider` need to accept an optional `language` parameter:

```python
class YouTubeProvider:
    async def fetch_courses(
        self, 
        skill: str, 
        max_results: int,
        language: Optional[str] = None
    ) -> List[SimplifiedCourse]:
        """
        Fetch courses with optional language filtering.
        
        Args:
            skill: The skill to search for
            max_results: Maximum number of results
            language: ISO 639-1 language code (e.g., 'en', 'es')
        """
        params = {
            "part": "snippet",
            "q": f"{skill} tutorial",
            "type": "video",
            "maxResults": max_results,
            "key": self.api_key,
            "videoDuration": "medium"
        }
        
        # Add language filter if provided
        if language:
            params["relevanceLanguage"] = language
        
        # ... rest of implementation
```

```python
class GitHubProvider:
    async def fetch_courses(
        self, 
        skill: str, 
        max_results: int,
        language: Optional[str] = None
    ) -> List[SimplifiedCourse]:
        """
        Fetch repositories with optional language filtering.
        
        Args:
            skill: The skill to search for
            max_results: Maximum number of results
            language: Programming language filter (maps from ISO code)
        """
        query = f"{skill} tutorial OR {skill} course OR {skill} learning"
        
        # Map language codes to GitHub language filters where applicable
        # Note: GitHub uses programming language names, not ISO codes
        # This is a best-effort mapping for technical content
        if language:
            lang_map = {
                "en": None,  # English is default, no filter needed
                "es": None,  # Spanish content not filterable by GitHub API
                # For programming languages, we could add:
                # "py": "python", "js": "javascript", etc.
            }
            # For MVP, we'll filter in post-processing based on description
        
        # ... rest of implementation
```

### 3. Batch Orchestrator

New module: `api/batch_recommendations.py`

```python
async def get_batch_recommendations(
    request: BatchRecommendationRequest
) -> BatchRecommendationResponse:
    """
    Process multiple skills concurrently and return aggregated results.
    """
    # Process all skills in parallel
    skill_tasks = [
        process_single_skill(
            skill_req.skill,
            skill_req.preferences or [],
            request.max_results,
            request.language
        )
        for skill_req in request.skills
    ]
    
    skill_results = await asyncio.gather(*skill_tasks, return_exceptions=True)
    
    # Build response
    results = []
    for idx, result in enumerate(skill_results):
        if isinstance(result, Exception):
            # Log error and return empty result for this skill
            logger.error(f"Error processing skill {request.skills[idx].skill}: {result}")
            results.append(SkillRecommendationResult(
                skill=request.skills[idx].skill,
                total_results=0,
                recommendations=[]
            ))
        else:
            results.append(result)
    
    return BatchRecommendationResponse(
        results=results,
        metadata={
            "total_skills": len(request.skills),
            "language": request.language
        }
    )

async def process_single_skill(
    skill: str,
    preferences: List[str],
    max_results: int,
    language: Optional[str]
) -> SkillRecommendationResult:
    """
    Process a single skill: fetch from providers, rank, and return results.
    """
    # Initialize providers
    youtube = YouTubeProvider()
    github = GitHubProvider()
    
    # Fetch from providers in parallel
    provider_results = await asyncio.gather(
        youtube.fetch_courses(skill, max_results, language),
        github.fetch_courses(skill, max_results, language),
        return_exceptions=True
    )
    
    # Aggregate courses
    all_courses = []
    for result in provider_results:
        if not isinstance(result, Exception):
            all_courses.extend(result)
    
    # Rank courses
    ranking_engine = RankingEngine()
    ranked_courses = ranking_engine.rank_courses(
        all_courses,
        skill,
        preferences
    )
    
    # Apply max_results limit
    final_courses = ranked_courses[:max_results]
    
    return SkillRecommendationResult(
        skill=skill,
        total_results=len(final_courses),
        recommendations=final_courses
    )
```

### 4. Modified Ranking Engine

The `RankingEngine` needs minor modifications to remove difficulty filtering:

```python
class RankingEngine:
    def rank_courses(
        self, 
        courses: List[SimplifiedCourse], 
        skill: str,
        preferences: List[str]
    ) -> List[SimplifiedCourse]:
        """
        Rank courses using weighted scoring algorithm.
        No difficulty filtering in this version.
        """
        if not courses:
            return []
        
        # Calculate scores
        for course in courses:
            course.relevance_score = self._calculate_score(course, skill, preferences)
        
        # Remove duplicates
        courses = self._deduplicate(courses)
        
        # Sort by relevance
        courses.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return courses
    
    def _calculate_score(
        self, 
        course: SimplifiedCourse, 
        skill: str, 
        preferences: List[str]
    ) -> float:
        """
        Calculate relevance score.
        Preferences now include career goals, learning styles, time commitments, and technologies.
        All are treated equally in keyword matching.
        """
        score = 0.0
        
        # Title matching (40%)
        title_score = self._keyword_match_score(course.title, skill, preferences)
        score += title_score * 0.4
        
        # Description matching (30%)
        desc_score = self._keyword_match_score(course.description, skill, preferences)
        score += desc_score * 0.3
        
        # Popularity score (20%) - Note: rating removed from SimplifiedCourse
        # For MVP, we'll use a default popularity score or derive from provider-specific metrics
        # This can be enhanced later
        score += 0.0 * 0.2  # Placeholder for future enhancement
        
        # Tag matching (10%)
        tag_score = self._tag_match_score(course.tags, skill, preferences)
        score += tag_score * 0.1
        
        return min(score, 1.0)
    
    # _keyword_match_score and _tag_match_score remain unchanged
    # They already handle preferences as generic keywords
```

### 5. FastAPI Endpoint

New endpoint in `main.py`:

```python
@app.post("/api/batch-recommendations", response_model=BatchRecommendationResponse)
async def batch_recommend_courses(request: BatchRecommendationRequest):
    """
    Get personalized course recommendations for multiple skills.
    
    This endpoint processes multiple skills concurrently and returns
    recommendations for each skill with per-skill preferences.
    """
    try:
        logger.info(f"Received batch recommendation request for {len(request.skills)} skills")
        recommendations = await get_batch_recommendations(request)
        return recommendations
    except Exception as e:
        logger.error(f"Error processing batch recommendation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

## Data Models

### Request Flow

```
BatchRecommendationRequest
├── skills: List[SkillRequest]
│   ├── skill: str (required)
│   └── preferences: List[str] (optional)
├── max_results: int (default: 10, range: 1-50)
└── language: str (optional, ISO 639-1 code)
```

### Response Flow

```
BatchRecommendationResponse
├── results: List[SkillRecommendationResult]
│   ├── skill: str
│   ├── total_results: int
│   └── recommendations: List[SimplifiedCourse]
│       ├── id: str
│       ├── title: str
│       ├── provider: str
│       ├── url: str
│       ├── description: str
│       ├── tags: List[str]
│       └── relevance_score: float
└── metadata: dict
    ├── total_skills: int
    └── language: str (if provided)
```

### Transformation: Old Course → SimplifiedCourse

```python
def to_simplified_course(course: Course) -> SimplifiedCourse:
    """Convert old Course model to SimplifiedCourse"""
    return SimplifiedCourse(
        id=course.id,
        title=course.title,
        provider=course.provider,
        url=course.url,
        description=course.description,
        tags=course.tags,
        relevance_score=course.relevance_score
    )
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Batch request accepts list of skill objects
*For any* non-empty list of skill objects where each object has a non-empty skill field, the API should accept the request without validation errors.
**Validates: Requirements 1.1, 1.3**

### Property 2: Whitespace-only skills are rejected
*For any* skill object where the skill field contains only whitespace characters, the API should reject the request with a validation error.
**Validates: Requirements 2.3**

### Property 3: Preferences type validation
*For any* skill object with a preferences field, if the preferences field is not a list of strings, the API should reject the request with a validation error.
**Validates: Requirements 1.4**

### Property 4: Missing preferences default to empty list
*For any* skill object that omits the preferences field, the system should process that skill with an empty preferences list.
**Validates: Requirements 1.5**

### Property 5: Preferences flow through to ranking
*For any* skill with specified preferences, those preferences should be passed to the Recommendation_Engine and affect the relevance scores of returned courses.
**Validates: Requirements 2.4**

### Property 6: Skill processing independence
*For any* batch request with multiple skills, each skill should be processed independently such that the preferences and results for one skill do not affect the preferences and results for another skill.
**Validates: Requirements 2.5, 8.4**

### Property 7: All preference types affect scoring equally
*For any* course and any preference keyword (whether career goal, learning style, time commitment, or technology), matching that preference in the course content should increase the relevance score by the same amount regardless of preference type.
**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 12.4**

### Property 8: Language filter applies to all skills
*For any* batch request with a language parameter, all skills in the batch should have their results filtered to match the specified language code.
**Validates: Requirements 4.2**

### Property 9: Provider receives language parameter
*For any* batch request with a language parameter, each provider should receive and use that language parameter when fetching content.
**Validates: Requirements 4.3**

### Property 10: Valid language codes are accepted
*For any* valid ISO 639-1 language code (e.g., "en", "es", "fr", "hi"), the API should accept the request without validation errors.
**Validates: Requirements 4.5**

### Property 11: Invalid language codes are rejected
*For any* string that is not a valid ISO 639-1 language code, the API should reject the request with a validation error.
**Validates: Requirements 10.4**

### Property 12: Max results applies per skill
*For any* batch request with max_results specified, each skill in the batch should return at most max_results recommendations, not max_results total across all skills.
**Validates: Requirements 5.2, 5.5**

### Property 13: No difficulty filtering occurs
*For any* batch request, the returned recommendations should include content of all difficulty levels without filtering by difficulty.
**Validates: Requirements 6.2, 6.4**

### Property 14: Response structure matches specification
*For any* batch request, the response should contain a list of skill recommendation objects where each object has exactly one entry per requested skill, and each entry contains skill name, total_results count, and recommendations list.
**Validates: Requirements 7.1, 7.2**

### Property 15: SimplifiedCourse contains only specified fields
*For any* course object in the response, it should contain exactly these fields: id, title, provider, url, description, tags, and relevance_score, and should not contain difficulty, duration, rating, or thumbnail fields.
**Validates: Requirements 7.3, 7.4, 6.3**

### Property 16: Metadata contains required fields
*For any* batch response, the metadata should include total_skills count, and if a language filter was applied, the metadata should include the language code.
**Validates: Requirements 7.5, 11.1, 11.2, 11.3**

### Property 17: Error isolation between skills
*For any* batch request where provider calls fail for one skill, the API should continue processing remaining skills and return successful results for those skills.
**Validates: Requirements 8.3, 8.5**

### Property 18: Provider failure metadata
*For any* skill where provider calls fail, the metadata should indicate which providers failed for that skill.
**Validates: Requirements 11.4, 11.5**

### Property 19: Weighted scoring algorithm preserved
*For any* course being scored, the relevance score should be calculated using the weighted formula: title_match × 0.40 + description_match × 0.30 + popularity × 0.20 + tag_match × 0.10.
**Validates: Requirements 12.1**

### Property 20: Keyword matching preserved
*For any* course and skill, the relevance score should increase when the skill keywords appear in the course title, description, or tags.
**Validates: Requirements 12.2**

### Property 21: Deduplication preserved
*For any* set of courses with similar titles (after normalization), only one course should appear in the final results.
**Validates: Requirements 12.3**

## Error Handling

### Validation Errors (422 Unprocessable Entity)

The API will return validation errors for:

1. **Empty skills list**: Request must contain at least one skill
2. **Empty skill field**: Each skill object must have a non-empty skill string
3. **Invalid preferences type**: Preferences must be a list of strings if provided
4. **Invalid max_results**: Must be between 1 and 50
5. **Invalid language code**: Must be a valid ISO 639-1 code if provided

Error response format:
```json
{
    "detail": [
        {
            "loc": ["body", "skills", 0, "skill"],
            "msg": "ensure this value has at least 1 characters",
            "type": "value_error.any_str.min_length"
        }
    ]
}
```

### Provider Errors

When provider API calls fail:

1. **Single provider failure**: Continue with results from successful providers
2. **All providers fail for one skill**: Return empty recommendations list for that skill
3. **All providers fail for all skills**: Return response with empty recommendations for all skills

Provider error metadata format:
```json
{
    "metadata": {
        "total_skills": 2,
        "skill_errors": {
            "python": {
                "YouTube": {"status": "error", "message": "API quota exceeded"},
                "GitHub": {"status": "success", "count": 5}
            }
        }
    }
}
```

### Server Errors (500 Internal Server Error)

Unexpected errors will return:
```json
{
    "detail": "Internal server error message"
}
```

## Testing Strategy

### Dual Testing Approach

This feature requires both unit tests and property-based tests to ensure comprehensive coverage:

**Unit Tests** focus on:
- Specific examples of valid requests and responses
- Edge cases (empty lists, whitespace strings, boundary values)
- Error conditions (invalid inputs, provider failures)
- Integration between components

**Property-Based Tests** focus on:
- Universal properties that hold for all inputs
- Comprehensive input coverage through randomization
- Invariants that must be maintained across all executions

### Property-Based Testing Configuration

**Library Selection**: Use `hypothesis` for Python property-based testing

**Test Configuration**:
- Minimum 100 iterations per property test
- Each test must reference its design document property
- Tag format: `# Feature: multi-skill-batch-recommendations, Property {number}: {property_text}`

**Example Property Test Structure**:
```python
from hypothesis import given, strategies as st
import pytest

@given(
    skills=st.lists(
        st.builds(
            SkillRequest,
            skill=st.text(min_size=1).filter(lambda s: s.strip()),
            preferences=st.one_of(st.none(), st.lists(st.text()))
        ),
        min_size=1
    )
)
@pytest.mark.property_test
def test_batch_request_accepts_skill_objects(skills):
    """
    Feature: multi-skill-batch-recommendations
    Property 1: Batch request accepts list of skill objects
    
    For any non-empty list of skill objects where each object has a 
    non-empty skill field, the API should accept the request without 
    validation errors.
    """
    request = BatchRecommendationRequest(skills=skills, max_results=10)
    # Should not raise validation error
    assert len(request.skills) == len(skills)
```

### Unit Test Coverage

**Request Validation Tests**:
- Test empty skills list rejection
- Test whitespace-only skill rejection
- Test invalid preferences type rejection
- Test max_results boundary values (0, 1, 50, 51)
- Test invalid language codes

**Response Structure Tests**:
- Test response has one result per skill
- Test SimplifiedCourse has only specified fields
- Test metadata contains required fields
- Test difficulty field is absent

**Ranking Engine Tests**:
- Test preference keywords increase scores
- Test all preference types treated equally
- Test weighted scoring formula
- Test deduplication logic
- Test no difficulty filtering

**Error Handling Tests**:
- Test single provider failure doesn't affect other providers
- Test all providers failing returns empty results
- Test error metadata is populated correctly
- Test partial results when some skills fail

**Integration Tests**:
- Test end-to-end batch request with multiple skills
- Test language filtering across all skills
- Test max_results applies per skill
- Test concurrent processing of skills

### Test Data Generators

For property-based tests, create generators for:

```python
# Valid skill requests
valid_skill_request = st.builds(
    SkillRequest,
    skill=st.text(min_size=1, alphabet=st.characters(blacklist_categories=['Cs'])),
    preferences=st.one_of(st.none(), st.lists(st.text(min_size=1), max_size=5))
)

# Valid batch requests
valid_batch_request = st.builds(
    BatchRecommendationRequest,
    skills=st.lists(valid_skill_request, min_size=1, max_size=10),
    max_results=st.integers(min_value=1, max_value=50),
    language=st.one_of(st.none(), st.sampled_from(['en', 'es', 'fr', 'hi', 'de']))
)

# Simplified courses
simplified_course = st.builds(
    SimplifiedCourse,
    id=st.text(min_size=1),
    title=st.text(min_size=1),
    provider=st.sampled_from(['YouTube', 'GitHub']),
    url=st.text(min_size=1),
    description=st.text(min_size=1),
    tags=st.lists(st.text(min_size=1), max_size=10),
    relevance_score=st.floats(min_value=0.0, max_value=1.0)
)
```

### Migration Testing

**Backward Compatibility Tests**:
- Verify old `/api/recommendations` endpoint still works
- Test that single-skill requests can be converted to batch format
- Verify response structure differences are documented

**Conversion Tests**:
```python
def test_single_to_batch_conversion():
    """Test converting old single-skill request to new batch format"""
    # Old format
    old_request = {
        "skill": "python",
        "difficulty": "beginner",
        "max_results": 10,
        "preferences": ["web development"]
    }
    
    # New format
    new_request = {
        "skills": [
            {
                "skill": "python",
                "preferences": ["web development"]
            }
        ],
        "max_results": 10
    }
    
    # Both should return similar results (ignoring difficulty filtering)
    # and new format should not include difficulty, duration, rating, thumbnail
```

## Migration Path

### Deployment Strategy

**Phase 1: Deploy new endpoint alongside old endpoint**
- Add `/api/batch-recommendations` endpoint
- Keep `/api/recommendations` endpoint functional
- Both endpoints available simultaneously

**Phase 2: Client migration period**
- Clients gradually migrate to new endpoint
- Monitor usage of old endpoint
- Provide migration guide and examples

**Phase 3: Deprecation**
- Mark old endpoint as deprecated in documentation
- Add deprecation warning in API responses
- Set sunset date for old endpoint

**Phase 4: Removal**
- Remove old endpoint after sunset date
- All clients using new batch endpoint

### Migration Guide for Clients

**Converting Single-Skill Requests**:

Old format:
```json
POST /api/recommendations
{
    "skill": "python programming",
    "difficulty": "beginner",
    "max_results": 10,
    "preferences": ["web development"]
}
```

New format:
```json
POST /api/batch-recommendations
{
    "skills": [
        {
            "skill": "python programming",
            "preferences": ["web development"]
        }
    ],
    "max_results": 10
}
```

**Key Differences**:
1. `skill` becomes `skills` array with `SkillRequest` objects
2. `difficulty` parameter removed (no longer supported)
3. `preferences` moved inside each skill object
4. Response structure changed: `results` array instead of flat `recommendations`
5. Course objects simplified: removed `difficulty`, `duration`, `rating`, `thumbnail`

**Response Mapping**:

Old response:
```json
{
    "skill": "python programming",
    "total_results": 10,
    "recommendations": [...]
}
```

New response:
```json
{
    "results": [
        {
            "skill": "python programming",
            "total_results": 10,
            "recommendations": [...]
        }
    ],
    "metadata": {
        "total_skills": 1
    }
}
```

To access recommendations for a single skill in new format:
```python
# Old: response.recommendations
# New: response.results[0].recommendations
```

## Performance Considerations

### Concurrency Benefits

**Old System** (single skill):
- 2 concurrent provider calls (YouTube + GitHub)
- Total time ≈ max(youtube_time, github_time)

**New System** (3 skills):
- 3 × 2 = 6 concurrent provider calls
- Total time ≈ max(youtube_time, github_time) (same as single skill!)
- Benefit: Process 3 skills in the time it took to process 1

### Resource Usage

**Memory**: Linear growth with number of skills
- Each skill holds its own result set
- Results are independent and can be garbage collected after response

**API Quota**: Multiplied by number of skills
- YouTube API: quota_per_skill × num_skills
- GitHub API: quota_per_skill × num_skills
- Consider rate limiting for large batches

### Optimization Opportunities

**Future Enhancements**:
1. **Caching**: Cache provider results per skill to avoid redundant API calls
2. **Batch size limits**: Limit maximum number of skills per request (e.g., 10)
3. **Request deduplication**: If same skill appears multiple times, fetch once and reuse
4. **Streaming responses**: Stream results as each skill completes (Server-Sent Events)

## Security Considerations

### Input Validation

- All inputs validated by Pydantic models
- SQL injection not applicable (no database)
- XSS prevention: API returns JSON, client responsible for safe rendering

### Rate Limiting

**Recommendations**:
- Limit batch size to prevent abuse (max 10 skills per request)
- Implement per-IP rate limiting
- Monitor API quota usage for external providers

### API Key Protection

- YouTube API key stored in environment variables
- Never expose API keys in responses or logs
- Rotate keys periodically

## Future Enhancements

### Phase 2 Features

1. **Request deduplication**: Detect and merge duplicate skills in same batch
2. **Skill relationships**: Suggest related skills based on batch content
3. **Learning path generation**: Order skills by prerequisite relationships
4. **Personalized ranking**: Use user history to adjust relevance scores
5. **More providers**: Add Coursera, edX, Udemy, Khan Academy
6. **Caching layer**: Redis cache for popular skill queries
7. **Analytics**: Track popular skill combinations and preferences

### LLM Integration

1. **Query enhancement**: Use LLM to expand skill queries with related terms
2. **Preference interpretation**: Parse natural language preferences
3. **Content summarization**: Generate concise summaries of courses
4. **Difficulty assessment**: Use LLM to infer difficulty from content
5. **Learning path recommendations**: Generate personalized learning sequences

## Appendix: Complete API Examples

### Example 1: Single Skill (Backward Compatible)

Request:
```json
POST /api/batch-recommendations
{
    "skills": [
        {
            "skill": "python",
            "preferences": ["Backend Developer", "FastAPI"]
        }
    ],
    "max_results": 5,
    "language": "en"
}
```

Response:
```json
{
    "results": [
        {
            "skill": "python",
            "total_results": 5,
            "recommendations": [
                {
                    "id": "youtube_abc123",
                    "title": "Python FastAPI Tutorial for Backend Development",
                    "provider": "YouTube",
                    "url": "https://youtube.com/watch?v=abc123",
                    "description": "Learn FastAPI for building backend APIs",
                    "tags": ["python", "fastapi", "backend"],
                    "relevance_score": 0.92
                }
            ]
        }
    ],
    "metadata": {
        "total_skills": 1,
        "language": "en"
    }
}
```

### Example 2: Multiple Skills with Different Preferences

Request:
```json
POST /api/batch-recommendations
{
    "skills": [
        {
            "skill": "python",
            "preferences": ["Backend Developer", "project-based", "FastAPI"]
        },
        {
            "skill": "docker",
            "preferences": ["Backend Developer", "microservices"]
        },
        {
            "skill": "postgresql",
            "preferences": ["Backend Developer", "hands-on", "database design"]
        }
    ],
    "max_results": 10,
    "language": "en"
}
```

Response:
```json
{
    "results": [
        {
            "skill": "python",
            "total_results": 10,
            "recommendations": [...]
        },
        {
            "skill": "docker",
            "total_results": 10,
            "recommendations": [...]
        },
        {
            "skill": "postgresql",
            "total_results": 10,
            "recommendations": [...]
        }
    ],
    "metadata": {
        "total_skills": 3,
        "language": "en"
    }
}
```

### Example 3: Error Handling - Partial Failure

Request:
```json
POST /api/batch-recommendations
{
    "skills": [
        {
            "skill": "python",
            "preferences": ["web development"]
        },
        {
            "skill": "nonexistent-skill-xyz",
            "preferences": []
        }
    ],
    "max_results": 10
}
```

Response:
```json
{
    "results": [
        {
            "skill": "python",
            "total_results": 10,
            "recommendations": [...]
        },
        {
            "skill": "nonexistent-skill-xyz",
            "total_results": 0,
            "recommendations": []
        }
    ],
    "metadata": {
        "total_skills": 2,
        "skill_errors": {
            "nonexistent-skill-xyz": {
                "YouTube": {"status": "success", "count": 0},
                "GitHub": {"status": "success", "count": 0}
            }
        }
    }
}
```

### Example 4: Validation Error

Request:
```json
POST /api/batch-recommendations
{
    "skills": [
        {
            "skill": "",
            "preferences": ["web development"]
        }
    ],
    "max_results": 10
}
```

Response (422):
```json
{
    "detail": [
        {
            "loc": ["body", "skills", 0, "skill"],
            "msg": "ensure this value has at least 1 characters",
            "type": "value_error.any_str.min_length"
        }
    ]
}
```
