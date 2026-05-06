from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


class Recommendation(BaseModel):
    """A single learning resource recommendation stored in the Analyses collection."""

    recommendation_id: str
    title: str
    provider: str
    url: str
    description: str
    tags: List[str] = []
    relevance_score: float = Field(ge=0.0, le=1.0)
    status: str
    xp_value: int = Field(ge=0, le=100)
    linked_gap: str


class AnalysisResults(BaseModel):
    """The nested results sub-document inside an Analyses MongoDB document."""

    gaps: List[dict] = []  # List of {"skill": str, "preferences": List[str]}
    recommendations: List[Recommendation] = []


class AnalysisDocument(BaseModel):
    """Pydantic representation of an Analyses collection document."""

    id: str = Field(alias="_id")   # ObjectId serialised as str
    user_id: str                    # ObjectId serialised as str
    is_latest: bool
    results: AnalysisResults = Field(default_factory=AnalysisResults)

    model_config = ConfigDict(populate_by_name=True)


class UserRecommendationRequest(BaseModel):
    """Request body for POST /api/user-recommendations."""

    user_id: str = Field(
        ...,
        description="The user's ID as stored in the Users collection (e.g. auth0_id / _id)",
    )
    analysis_id: Optional[str] = Field(
        default=None,
        description="Optional ID of a specific analysis document",
    )
    preferences: Optional[List[str]] = Field(
        default=None,
        description="Career goals, learning styles, technologies. Applied to all gaps. E.g. ['Backend Developer', 'project-based']",
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of recommendations per skill gap",
    )
    language: Optional[str] = Field(
        default=None,
        description="ISO 639-1 language code to filter results (e.g. 'en', 'es')",
    )


class UserRecommendationResponse(BaseModel):
    """Response body for POST /api/user-recommendations."""

    analysis_id: Optional[str]
    user_id: str
    gaps: List[str]
    recommendations: List[Recommendation]
    cached: bool
