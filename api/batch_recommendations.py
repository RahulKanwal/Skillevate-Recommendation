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
from providers.devto_provider import DevToProvider
from core.ranking import RankingEngine
from core.content_similarity import rerank_with_tfidf

logger = logging.getLogger(__name__)

# Words/phrases to filter out from preferences (related to gap analysis and priority levels)
PREFERENCE_FILTER_KEYWORDS = {
    "critical gap",
    "high priority",
    "skill gap",
    "medium priority",
    "low priority",
    "gap",
    "priority",
    "critical",
    "high",
    "medium",
    "low"
}


def _filter_preferences(preferences: Optional[List[str]]) -> List[str]:
    """
    Filter out preference words related to gap analysis and priority levels.
    
    Args:
        preferences: List of preference strings
        
    Returns:
        Filtered list of preferences without gap/priority-related keywords
    """
    if not preferences:
        return []
    
    filtered = []
    for pref in preferences:
        pref_lower = pref.lower().strip()
        # Check if the entire preference matches a filter keyword
        if pref_lower not in PREFERENCE_FILTER_KEYWORDS:
            filtered.append(pref)
    
    return filtered


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
    # Filter out gap/priority-related preference keywords
    filtered_preferences = _filter_preferences(preferences)
    
    # Initialize providers
    youtube = YouTubeProvider()
    github = GitHubProvider()
    devto = DevToProvider()
    
    # Fetch a larger pool per provider so that after the multi-layer filtering
    # (skill match, educational signal, relevance threshold, TF-IDF re-ranking)
    # there are still enough candidates to fill max_results.
    # The final output is capped at max_results by rerank_with_tfidf.
    fetch_size = max(max_results * 3, 30)

    logger.info(f"Fetching recommendations for skill: {skill} (fetch_size={fetch_size})")

    provider_results = await asyncio.gather(
        youtube.fetch_courses(skill, fetch_size, language, filtered_preferences),
        github.fetch_courses(skill, fetch_size, language, filtered_preferences),
        devto.fetch_courses(skill, fetch_size, language, filtered_preferences),
        return_exceptions=True
    )
    
    # Aggregate courses
    all_courses: List[SimplifiedCourse] = []
    provider_stats = {}
    
    for idx, result in enumerate(provider_results):
        provider_name = ["YouTube", "GitHub", "Dev.to"][idx]
        if isinstance(result, Exception):
            logger.error(f"Error fetching from {provider_name} for skill {skill}: {result}")
            provider_stats[provider_name] = {"status": "error", "message": str(result)}
        else:
            all_courses.extend(result)
            provider_stats[provider_name] = {"status": "success", "count": len(result)}
    
    # If no courses were fetched, return empty result
    if not all_courses:
        logger.warning(f"No courses fetched for skill: {skill}")
        return SkillRecommendationResult(
            skill=skill,
            total_results=0,
            recommendations=[]
        )
    
    # Rank courses using filtered preferences
    ranking_engine = RankingEngine()
    ranked_courses = ranking_engine.rank_courses(
        all_courses,
        skill,
        filtered_preferences
    )

    # TF-IDF re-ranking with MMR diversity using filtered preferences
    final_courses = rerank_with_tfidf(ranked_courses, skill, filtered_preferences, max_results)
    
    # Ensure at least 1 result per skill if any courses exist
    # Strategy: prefer ranked courses, then all_courses if ranking filtered everything
    if not final_courses:
        if ranked_courses:
            # Reranking filtered everything out, use top ranked course
            final_courses = ranked_courses[:1]
        else:
            # Ranking filtered everything out, score all_courses and take the best
            logger.info(f"Ranking filtered all courses for {skill}, recalculating scores...")
            for course in all_courses:
                course.relevance_score = ranking_engine._calculate_score(course, skill, filtered_preferences)
            all_courses_sorted = sorted(all_courses, key=lambda x: x.relevance_score, reverse=True)
            final_courses = all_courses_sorted[:1]
    
    logger.info(f"Returning {len(final_courses)} recommendations for skill: {skill}")
    
    return SkillRecommendationResult(
        skill=skill,
        total_results=len(final_courses),
        recommendations=final_courses
    )
