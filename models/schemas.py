from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    ALL = "all"

class RecommendationRequest(BaseModel):
    skill: str = Field(..., description="The skill or topic to learn", min_length=1)
    difficulty: DifficultyLevel = Field(default=DifficultyLevel.ALL, description="Preferred difficulty level")
    max_results: int = Field(default=10, ge=1, le=50, description="Maximum number of recommendations")
    preferences: Optional[List[str]] = Field(default=None, description="Additional preferences or keywords")

    class Config:
        json_schema_extra = {
            "example": {
                "skill": "python programming",
                "difficulty": "beginner",
                "max_results": 10,
                "preferences": ["web development", "practical projects"]
            }
        }

class Course(BaseModel):
    id: str
    title: str
    provider: str
    url: str
    description: str
    difficulty: Optional[str] = None
    duration: Optional[str] = None
    rating: Optional[float] = None
    tags: List[str] = []
    relevance_score: float = Field(ge=0.0, le=1.0)
    thumbnail: Optional[str] = None

class RecommendationResponse(BaseModel):
    skill: str
    total_results: int
    recommendations: List[Course]
    metadata: dict = Field(default_factory=dict)
