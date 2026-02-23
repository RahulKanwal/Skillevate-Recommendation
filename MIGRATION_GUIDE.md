# Migration Guide: v1 to v2 API

## Overview

Version 2.0 of the Skillevate Recommendation API introduces a new batch recommendations endpoint that supports multiple skills in a single request. This guide helps you migrate from the v1 single-skill endpoint to the v2 batch endpoint.

## What's New in v2

### New Features
- **Batch processing**: Request recommendations for multiple skills in one API call
- **Per-skill preferences**: Each skill can have its own set of preferences
- **Language filtering**: Filter content by ISO 639-1 language codes
- **Enhanced preferences**: Support for career goals, learning styles, time commitments, and technologies
- **Simplified response**: Removed unused fields (difficulty, duration, rating, thumbnail)

### Breaking Changes
- **Difficulty field removed**: The `difficulty` parameter is no longer supported
- **Response structure changed**: Results are now nested under a `results` array
- **Course object simplified**: Removed `difficulty`, `duration`, `rating`, and `thumbnail` fields

## Endpoint Comparison

### Old Endpoint (v1) - Still Available
```
POST /api/recommendations
```

### New Endpoint (v2) - Recommended
```
POST /api/batch-recommendations
```

## Migration Examples

### Example 1: Single Skill Request

**Old Format (v1):**
```json
POST /api/recommendations
{
    "skill": "python programming",
    "difficulty": "beginner",
    "max_results": 10,
    "preferences": ["web development", "django"]
}
```

**New Format (v2):**
```json
POST /api/batch-recommendations
{
    "skills": [
        {
            "skill": "python programming",
            "preferences": ["web development", "django"]
        }
    ],
    "max_results": 10,
    "language": "en"
}
```

**Key Changes:**
1. `skill` becomes `skills` array containing skill objects
2. `difficulty` parameter removed (no longer supported)
3. `preferences` moved inside each skill object
4. Optional `language` parameter added at request level

### Example 2: Multiple Skills (New Capability)

**New Format (v2):**
```json
POST /api/batch-recommendations
{
    "skills": [
        {
            "skill": "python",
            "preferences": ["Backend Developer", "FastAPI", "project-based"]
        },
        {
            "skill": "docker",
            "preferences": ["Backend Developer", "microservices"]
        },
        {
            "skill": "postgresql",
            "preferences": ["Backend Developer", "database optimization"]
        }
    ],
    "max_results": 10,
    "language": "en"
}
```

## Response Structure Changes

### Old Response (v1)

```json
{
    "skill": "python programming",
    "total_results": 10,
    "recommendations": [
        {
            "id": "youtube_abc123",
            "title": "Python Tutorial",
            "provider": "YouTube",
            "url": "https://youtube.com/watch?v=abc123",
            "description": "Learn Python",
            "difficulty": "beginner",
            "duration": "2:30:00",
            "rating": 4.5,
            "tags": ["python", "tutorial"],
            "relevance_score": 0.92,
            "thumbnail": "https://..."
        }
    ],
    "metadata": {
        "providers": {...},
        "total_fetched": 20,
        "filtered_count": 15
    }
}
```

### New Response (v2)

```json
{
    "results": [
        {
            "skill": "python programming",
            "total_results": 10,
            "recommendations": [
                {
                    "id": "youtube_abc123",
                    "title": "Python Tutorial",
                    "provider": "YouTube",
                    "url": "https://youtube.com/watch?v=abc123",
                    "description": "Learn Python",
                    "tags": ["python", "tutorial"],
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

**Key Changes:**
1. Results wrapped in `results` array
2. Each result contains `skill`, `total_results`, and `recommendations`
3. Course objects no longer include: `difficulty`, `duration`, `rating`, `thumbnail`
4. Metadata simplified to show `total_skills` and `language`

## Code Migration Examples

### Python (requests library)

**Old Code:**
```python
import requests

url = "http://localhost:8000/api/recommendations"
payload = {
    "skill": "python programming",
    "difficulty": "beginner",
    "max_results": 10,
    "preferences": ["web development"]
}

response = requests.post(url, json=payload)
data = response.json()

# Access recommendations
for course in data['recommendations']:
    print(f"{course['title']} - {course['provider']}")
```

**New Code:**
```python
import requests

url = "http://localhost:8000/api/batch-recommendations"
payload = {
    "skills": [
        {
            "skill": "python programming",
            "preferences": ["web development"]
        }
    ],
    "max_results": 10,
    "language": "en"
}

response = requests.post(url, json=payload)
data = response.json()

# Access recommendations (note the extra nesting)
for skill_result in data['results']:
    print(f"Skill: {skill_result['skill']}")
    for course in skill_result['recommendations']:
        print(f"  {course['title']} - {course['provider']}")
```

### JavaScript (fetch API)

**Old Code:**
```javascript
const url = 'http://localhost:8000/api/recommendations';
const payload = {
  skill: 'python programming',
  difficulty: 'beginner',
  max_results: 10,
  preferences: ['web development']
};

fetch(url, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload)
})
  .then(response => response.json())
  .then(data => {
    data.recommendations.forEach(course => {
      console.log(`${course.title} - ${course.provider}`);
    });
  });
```

**New Code:**
```javascript
const url = 'http://localhost:8000/api/batch-recommendations';
const payload = {
  skills: [
    {
      skill: 'python programming',
      preferences: ['web development']
    }
  ],
  max_results: 10,
  language: 'en'
};

fetch(url, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload)
})
  .then(response => response.json())
  .then(data => {
    data.results.forEach(skillResult => {
      console.log(`Skill: ${skillResult.skill}`);
      skillResult.recommendations.forEach(course => {
        console.log(`  ${course.title} - ${course.provider}`);
      });
    });
  });
```

## Enhanced Preferences

The new API supports richer preference types:

### Career Goals
```json
{
    "skill": "python",
    "preferences": ["Backend Developer", "Data Scientist", "ML Engineer"]
}
```

### Learning Styles
```json
{
    "skill": "javascript",
    "preferences": ["project-based", "hands-on", "interactive"]
}
```

### Time Commitment
```json
{
    "skill": "docker",
    "preferences": ["quick tutorials", "comprehensive course"]
}
```

### Technologies (existing)
```json
{
    "skill": "python",
    "preferences": ["FastAPI", "Django", "Flask"]
}
```

### Combined Preferences
```json
{
    "skill": "python",
    "preferences": [
        "Backend Developer",
        "project-based",
        "FastAPI",
        "quick tutorials"
    ]
}
```

## Language Filtering

The new API supports language filtering using ISO 639-1 codes:

```json
{
    "skills": [
        {
            "skill": "python",
            "preferences": ["web development"]
        }
    ],
    "max_results": 10,
    "language": "es"  // Spanish content
}
```

**Supported Language Codes:**
- `en` - English
- `es` - Spanish
- `fr` - French
- `de` - German
- `hi` - Hindi
- `ja` - Japanese
- `zh` - Chinese
- `ar` - Arabic
- And many more (see ISO 639-1 standard)

## Migration Strategy

### Phase 1: Parallel Operation (Recommended)
1. Deploy v2 API alongside v1
2. Update new features to use v2 endpoint
3. Gradually migrate existing integrations
4. Monitor usage of v1 endpoint

### Phase 2: Deprecation
1. Mark v1 endpoint as deprecated in documentation
2. Add deprecation warnings in API responses
3. Set sunset date for v1 endpoint
4. Notify all API consumers

### Phase 3: Removal
1. Remove v1 endpoint after sunset date
2. All clients using v2 batch endpoint

## Backward Compatibility

The v1 endpoint (`/api/recommendations`) remains available for backward compatibility. However, we recommend migrating to v2 for:
- Better performance with multiple skills
- Enhanced preference support
- Language filtering capabilities
- Future feature updates

## Error Handling

### Validation Errors (422)

**Empty skills list:**
```json
{
    "detail": [
        {
            "loc": ["body", "skills"],
            "msg": "ensure this value has at least 1 items",
            "type": "value_error.list.min_items"
        }
    ]
}
```

**Invalid language code:**
```json
{
    "detail": [
        {
            "loc": ["body", "language"],
            "msg": "Invalid language code: xyz. Must be a valid ISO 639-1 code",
            "type": "value_error"
        }
    ]
}
```

**Whitespace-only skill:**
```json
{
    "detail": [
        {
            "loc": ["body", "skills", 0, "skill"],
            "msg": "skill field cannot be empty or whitespace-only",
            "type": "value_error"
        }
    ]
}
```

## Testing Your Migration

### 1. Test Single Skill
```bash
curl -X POST "http://localhost:8000/api/batch-recommendations" \
  -H "Content-Type: application/json" \
  -d '{
    "skills": [{"skill": "python"}],
    "max_results": 5
  }'
```

### 2. Test Multiple Skills
```bash
curl -X POST "http://localhost:8000/api/batch-recommendations" \
  -H "Content-Type: application/json" \
  -d '{
    "skills": [
      {"skill": "python", "preferences": ["Backend Developer"]},
      {"skill": "docker", "preferences": ["microservices"]}
    ],
    "max_results": 5,
    "language": "en"
  }'
```

### 3. Test Language Filtering
```bash
curl -X POST "http://localhost:8000/api/batch-recommendations" \
  -H "Content-Type: application/json" \
  -d '{
    "skills": [{"skill": "python"}],
    "max_results": 5,
    "language": "es"
  }'
```

## Support

If you encounter issues during migration:
1. Check the API documentation at `/docs` (Swagger UI)
2. Review error messages for validation issues
3. Test with the examples provided in this guide
4. Contact support with specific error details

## Summary

**To migrate from v1 to v2:**
1. Wrap your skill in a `skills` array
2. Move `preferences` inside the skill object
3. Remove `difficulty` parameter
4. Add optional `language` parameter
5. Update response parsing to access `results[0].recommendations`
6. Remove references to `difficulty`, `duration`, `rating`, `thumbnail` fields

The v2 API provides more flexibility and better performance, especially when requesting recommendations for multiple skills.
