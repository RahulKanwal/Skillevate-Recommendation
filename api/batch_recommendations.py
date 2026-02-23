import asyncio
import logging
from typing import List, Optional
from models.batch_models import (
    BatchRecommendationRequest,
    BatchRecommendationResponse,
    SkillRecommendationResult,
    SimplifiedCourse
)
from providers.youtube_provider import YouTubeProvider
from providers.github_provider import GitHubProvider
from core.ranking import RankingEngine

logger = logging.getLogger(__name__)


async def get_batch_recommendations(
    request: BatchRecommendationRequest
) -> BatchRecommendationResponse:
    """
    Process multiple skills concurrently and return aggregated results.
    
    Args:
        request: BatchRecommendationRequest containing skills, max_results, and language
        
    Returns:
        BatchRecommendationResponse with results for each skill
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
    skill_errors = {}
    
    for idx, result in enumerate(skill_results):
        skill_name = request.skills[idx].skill
        if isinstance(result, Exception):
            # Log error and return empty result for this skill
            logger.error(f"Error processing skill {skill_name}: {result}")
            results.append(SkillRecommendationResult(
                skill=skill_name,
                total_results=0,
                recommendations=[]
            ))
            skill_errors[skill_name] = {
                "error": str(result),
                "status": "failed"
            }
        else:
            results.append(result)
    
    # Build metadata
    metadata = {
        "total_skills": len(request.skills),
    }
    
    if request.language:
        metadata["language"] = request.language
    
    if skill_errors:
        metadata["skill_errors"] = skill_errors
    
    return BatchRecommendationResponse(
        results=results,
        metadata=metadata
    )


async def process_single_skill(
    skill: str,
    preferences: List[str],
    max_results: int,
    language: Optional[str]
) -> SkillRecommendationResult:
    """
    Process a single skill: fetch from providers, rank, and return results.
    
    Args:
        skill: The skill to search for
        preferences: User preferences (career goals, learning styles, etc.)
        max_results: Maximum number of results to return
        language: Optional ISO 639-1 language code
        
    Returns:
        SkillRecommendationResult with ranked recommendations
    """
    # Initialize providers
    youtube = YouTubeProvider()
    github = GitHubProvider()
    
    # Fetch from providers in parallel
    logger.info(f"Fetching recommendations for skill: {skill}")
    
    provider_results = await asyncio.gather(
        youtube.fetch_courses(skill, max_results, language),
        github.fetch_courses(skill, max_results, language),
        return_exceptions=True
    )
    
    # Aggregate courses
    all_courses: List[SimplifiedCourse] = []
    provider_stats = {}
    
    for idx, result in enumerate(provider_results):
        provider_name = ["YouTube", "GitHub"][idx]
        if isinstance(result, Exception):
            logger.error(f"Error fetching from {provider_name} for skill {skill}: {result}")
            provider_stats[provider_name] = {"status": "error", "message": str(result)}
        else:
            all_courses.extend(result)
            provider_stats[provider_name] = {"status": "success", "count": len(result)}
    
    # Rank courses
    ranking_engine = RankingEngine()
    ranked_courses = ranking_engine.rank_courses(
        all_courses,
        skill,
        preferences
    )
    
    # Apply max_results limit
    final_courses = ranked_courses[:max_results]
    
    logger.info(f"Returning {len(final_courses)} recommendations for skill: {skill}")
    
    return SkillRecommendationResult(
        skill=skill,
        total_results=len(final_courses),
        recommendations=final_courses
    )
