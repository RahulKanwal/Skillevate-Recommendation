import asyncio
import logging
from typing import List
from models.schemas import RecommendationRequest, RecommendationResponse, Course
from models.batch_models import SimplifiedCourse
from providers.youtube_provider import YouTubeProvider
from providers.github_provider import GitHubProvider
from core.ranking import RankingEngine

logger = logging.getLogger(__name__)


def simplified_to_course(simplified: SimplifiedCourse) -> Course:
    """Convert SimplifiedCourse to Course for backward compatibility"""
    return Course(
        id=simplified.id,
        title=simplified.title,
        provider=simplified.provider,
        url=simplified.url,
        description=simplified.description,
        tags=simplified.tags,
        relevance_score=simplified.relevance_score,
        difficulty=None,
        duration=None,
        rating=None,
        thumbnail=None
    )


async def get_recommendations(request: RecommendationRequest) -> RecommendationResponse:
    """
    Fetch and aggregate recommendations from multiple providers.
    """
    # Initialize providers
    youtube = YouTubeProvider()
    github = GitHubProvider()
    
    # Fetch from all providers concurrently
    logger.info(f"Fetching recommendations for: {request.skill}")
    
    results = await asyncio.gather(
        youtube.fetch_courses(request.skill, request.max_results),
        github.fetch_courses(request.skill, request.max_results),
        return_exceptions=True
    )
    
    # Aggregate results (convert SimplifiedCourse to Course for backward compatibility)
    all_courses: List[Course] = []
    provider_stats = {}
    
    for idx, result in enumerate(results):
        provider_name = ["YouTube", "GitHub"][idx]
        if isinstance(result, Exception):
            logger.error(f"Error fetching from {provider_name}: {str(result)}")
            provider_stats[provider_name] = {"status": "error", "count": 0}
        else:
            # Convert SimplifiedCourse objects to Course objects
            courses = [simplified_to_course(sc) for sc in result]
            all_courses.extend(courses)
            provider_stats[provider_name] = {"status": "success", "count": len(result)}
    
    # Rank and filter results
    ranking_engine = RankingEngine()
    ranked_courses = ranking_engine.rank_courses(
        all_courses, 
        request.skill,
        request.preferences or [],
        request.difficulty
    )
    
    # Apply max_results limit
    final_courses = ranked_courses[:request.max_results]
    
    logger.info(f"Returning {len(final_courses)} recommendations")
    
    return RecommendationResponse(
        skill=request.skill,
        total_results=len(final_courses),
        recommendations=final_courses,
        metadata={
            "providers": provider_stats,
            "total_fetched": len(all_courses),
            "filtered_count": len(ranked_courses)
        }
    )
