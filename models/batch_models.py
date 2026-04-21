from pydantic import BaseModel, Field, PrivateAttr, field_validator
from typing import List, Optional


# Common ISO 639-1 language codes
VALID_LANGUAGE_CODES = {
    'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh',
    'ar', 'hi', 'bn', 'pa', 'te', 'mr', 'ta', 'ur', 'gu', 'kn',
    'ml', 'or', 'as', 'ne', 'si', 'my', 'km', 'lo', 'th', 'vi',
    'id', 'ms', 'tl', 'nl', 'pl', 'uk', 'cs', 'sk', 'hu', 'ro',
    'bg', 'hr', 'sr', 'sl', 'mk', 'sq', 'lt', 'lv', 'et', 'fi',
    'sv', 'no', 'da', 'is', 'ga', 'cy', 'gd', 'eu', 'ca', 'gl',
    'he', 'yi', 'fa', 'ps', 'ku', 'tr', 'az', 'ka', 'hy', 'el',
    'sw', 'am', 'om', 'so', 'ha', 'yo', 'ig', 'zu', 'xh', 'af'
}


class SkillRequest(BaseModel):
    """Individual skill with optional preferences"""
    skill: str = Field(..., min_length=1, description="Skill or topic to learn")
    preferences: Optional[List[str]] = Field(
        default=None,
        description=(
            "Career goals, technologies, learning style, and audience. "
            "Examples: 'beginner', 'senior developer', 'quick tutorials', "
            "'comprehensive courses', 'project-based', 'FastAPI'."
        ),
    )
    
    @field_validator('skill')
    @classmethod
    def skill_not_whitespace(cls, v: str) -> str:
        """Ensure skill is not just whitespace"""
        if not v.strip():
            raise ValueError('skill field cannot be empty or whitespace-only')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "skill": "python",
                "preferences": ["Backend Developer", "FastAPI", "project-based"]
            }
        }


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
        description="ISO 639-1 language code (e.g., 'en', 'es', 'fr', 'hi')"
    )
    
    @field_validator('language')
    @classmethod
    def validate_language_code(cls, v: Optional[str]) -> Optional[str]:
        """Validate ISO 639-1 language code"""
        if v is None:
            return v
        
        v_lower = v.lower()
        if v_lower not in VALID_LANGUAGE_CODES:
            raise ValueError(
                f'Invalid language code: {v}. Must be a valid ISO 639-1 code '
                f'(e.g., en, es, fr, de, hi, ja, zh, ar, etc.)'
            )
        return v_lower

    class Config:
        json_schema_extra = {
            "example": {
                "skills": [
                    {
                        "skill": "python",
                        "preferences": ["Backend Developer", "FastAPI"]
                    },
                    {
                        "skill": "docker",
                        "preferences": ["Backend Developer", "microservices"]
                    }
                ],
                "max_results": 10,
                "language": "en"
            }
        }


class SimplifiedCourse(BaseModel):
    """Simplified course object without difficulty, duration, rating, thumbnail"""
    id: str
    title: str
    provider: str
    url: str
    description: str
    tags: List[str] = []
    relevance_score: float = Field(ge=0.0, le=1.0)

    # Quality signals — used by ranking engine, not exposed in API response
    stars: Optional[int] = None          # GitHub stars
    forks: Optional[int] = None          # GitHub forks
    published_at: Optional[str] = None   # ISO date string (YouTube publishedAt / GitHub pushed_at)
    view_count: Optional[int] = None     # YouTube view count
    like_count: Optional[int] = None     # YouTube like count

    # Authority signals — used by ranking engine, not exposed in API response
    channel_id: Optional[str] = None     # YouTube channel ID
    channel_name: Optional[str] = None   # YouTube channel name
    org_login: Optional[str] = None      # GitHub org/user login

    # Internal-only metadata for ranking (not serialized in API responses)
    _yt_internal: dict = PrivateAttr(default_factory=dict)


class SkillRecommendationResult(BaseModel):
    """Recommendations for a single skill"""
    skill: str
    total_results: int
    recommendations: List[SimplifiedCourse]


class BatchRecommendationResponse(BaseModel):
    """Response containing results for all skills"""
    results: List[SkillRecommendationResult]
    metadata: dict = Field(default_factory=dict)


def course_to_simplified(course) -> SimplifiedCourse:
    """
    Convert existing Course object to SimplifiedCourse.
    
    Args:
        course: Course object from models.schemas
        
    Returns:
        SimplifiedCourse object with only essential fields
    """
    return SimplifiedCourse(
        id=course.id,
        title=course.title,
        provider=course.provider,
        url=course.url,
        description=course.description,
        tags=course.tags,
        relevance_score=course.relevance_score
    )
