# Skillevate Recommendation System

A FastAPI-based recommendation system that provides personalized learning content from multiple providers.

## Features

- **Batch recommendations**: Get recommendations for multiple skills in a single request
- **Async API calls** to multiple content providers (YouTube, GitHub)
- **Intelligent ranking** based on relevance, popularity, and user preferences
- **Language filtering**: Filter content by preferred language (ISO 639-1 codes)
- **Enhanced preferences**: Support for career goals, learning styles, time commitments, and technologies
- **Deduplication and filtering**
- **RESTful API** with OpenAPI documentation
- **Extensible architecture** for adding more providers

## What's New in v2.0

- **Multi-skill batch processing**: Request recommendations for multiple skills at once
- **Per-skill preferences**: Each skill can have its own preferences
- **Language support**: Filter content by language (en, es, fr, de, hi, ja, zh, ar, etc.)
- **Simplified response**: Removed unused fields (difficulty, duration, rating, thumbnail)
- **Backward compatible**: Old `/api/recommendations` endpoint still works

See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for details on migrating from v1 to v2.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure API keys:
```bash
cp .env.example .env
# Edit .env and add your YouTube API key
```

3. Run the server:
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## API Endpoints

### Batch Recommendations (v2) - Recommended

```bash
POST /api/batch-recommendations
```

Get recommendations for multiple skills in a single request.

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/batch-recommendations" \
  -H "Content-Type: application/json" \
  -d '{
    "skills": [
      {
        "skill": "python",
        "preferences": ["Backend Developer", "FastAPI", "project-based"]
      },
      {
        "skill": "docker",
        "preferences": ["Backend Developer", "microservices"]
      }
    ],
    "max_results": 10,
    "language": "en"
  }'
```

**Example Response:**
```json
{
  "results": [
    {
      "skill": "python",
      "total_results": 10,
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
    },
    {
      "skill": "docker",
      "total_results": 8,
      "recommendations": [...]
    }
  ],
  "metadata": {
    "total_skills": 2,
    "language": "en"
  }
}
```

### Single Skill Recommendations (v1) - Legacy

```bash
POST /api/recommendations
```

Get recommendations for a single skill (maintained for backward compatibility).

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/recommendations" \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "python programming",
    "difficulty": "beginner",
    "max_results": 10,
    "preferences": ["web development"]
  }'
```

## Usage Examples

### Python

```python
import requests

url = "http://localhost:8000/api/batch-recommendations"
payload = {
    "skills": [
        {
            "skill": "python",
            "preferences": ["Backend Developer", "FastAPI"]
        },
        {
            "skill": "docker",
            "preferences": ["microservices"]
        }
    ],
    "max_results": 10,
    "language": "en"
}

response = requests.post(url, json=payload)
data = response.json()

for skill_result in data['results']:
    print(f"\nSkill: {skill_result['skill']}")
    print(f"Found {skill_result['total_results']} recommendations")
    for course in skill_result['recommendations']:
        print(f"  - {course['title']} ({course['provider']})")
        print(f"    Score: {course['relevance_score']:.2f}")
```

### JavaScript

```javascript
const url = 'http://localhost:8000/api/batch-recommendations';
const payload = {
  skills: [
    {
      skill: 'python',
      preferences: ['Backend Developer', 'FastAPI']
    },
    {
      skill: 'docker',
      preferences: ['microservices']
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
      console.log(`\nSkill: ${skillResult.skill}`);
      console.log(`Found ${skillResult.total_results} recommendations`);
      skillResult.recommendations.forEach(course => {
        console.log(`  - ${course.title} (${course.provider})`);
        console.log(`    Score: ${course.relevance_score.toFixed(2)}`);
      });
    });
  });
```

## Request Parameters

### BatchRecommendationRequest

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `skills` | Array[SkillRequest] | Yes | List of skills to get recommendations for (min: 1) |
| `max_results` | Integer | No | Maximum results per skill (default: 10, range: 1-50) |
| `language` | String | No | ISO 639-1 language code (e.g., 'en', 'es', 'fr', 'hi') |

### SkillRequest

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `skill` | String | Yes | The skill or topic to learn (min length: 1) |
| `preferences` | Array[String] | No | Career goals, learning styles, time commitments, or technologies |

## Preference Types

The API supports various preference types:

- **Career Goals**: "Backend Developer", "Data Scientist", "ML Engineer", "Frontend Developer"
- **Learning Styles**: "project-based", "theoretical", "hands-on", "interactive"
- **Time Commitment**: "quick tutorials", "comprehensive courses", "short videos"
- **Technologies**: "FastAPI", "Django", "React", "Docker", "Kubernetes"

All preference types are treated equally in the ranking algorithm.

## Language Support

The API supports content filtering by language using ISO 639-1 codes:

- `en` - English
- `es` - Spanish  
- `fr` - French
- `de` - German
- `hi` - Hindi
- `ja` - Japanese
- `zh` - Chinese
- `ar` - Arabic
- And many more...

## Project Structure

```
.
├── main.py                      # FastAPI application entry point
├── api/
│   ├── recommendations.py       # Single-skill endpoint (v1)
│   └── batch_recommendations.py # Batch endpoint (v2)
├── models/
│   ├── schemas.py              # Legacy data models
│   └── batch_models.py         # New batch data models
├── providers/
│   ├── youtube_provider.py     # YouTube Data API integration
│   └── github_provider.py      # GitHub API integration
├── core/
│   └── ranking.py              # Ranking algorithm
├── requirements.txt
├── MIGRATION_GUIDE.md          # v1 to v2 migration guide
└── README.md
```

## Getting YouTube API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable YouTube Data API v3
4. Create credentials (API Key)
5. Add the key to your `.env` file

## Future Enhancements

- **LLM integration** for query enhancement and semantic search
- **Additional providers** (Coursera, edX, Khan Academy, Udemy)
- **Skill taxonomy** for better related skill recommendations
- **User preference learning** based on interaction history
- **Caching layer** (Redis) for improved performance
- **Rate limiting** and retry logic
- **Analytics** for popular skill combinations

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License
