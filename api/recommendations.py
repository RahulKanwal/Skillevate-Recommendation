import asyncio
import logging
from typing import List
from models.schemas import RecommendationRequest, RecommendationResponse, Course
from models.batch_models import SimplifiedCourse
from providers.youtube_provider import YouTubeProvider
from providers.github_provider import GitHubProvider
from providers.devto_provider import DevToProvider
from core.ranking import RankingEngine
from core.content_similarity import rerank_with_tfidf

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
    youtube = YouTubeProvider()
    github = GitHubProvider()
    devto = DevToProvider()

    logger.info(f"Fetching recommendations for: {request.skill}")

    results = await asyncio.gather(
        youtube.fetch_courses(request.skill, request.max_results, preferences=request.preferences),
        github.fetch_courses(request.skill, request.max_results, preferences=request.preferences),
        devto.fetch_courses(request.skill, request.max_results, preferences=request.preferences),
        return_exceptions=True,
    )

    all_simplified: List[SimplifiedCourse] = []
    provider_stats = {}

    for idx, result in enumerate(results):
        provider_name = ["YouTube", "GitHub", "Dev.to"][idx]
        if isinstance(result, Exception):
            logger.error(f"Error fetching from {provider_name}: {str(result)}")
            provider_stats[provider_name] = {"status": "error", "count": 0}
        else:
            all_simplified.extend(result)
            provider_stats[provider_name] = {"status": "success", "count": len(result)}

    ranking_engine = RankingEngine()
    ranked = ranking_engine.rank_courses(
        all_simplified,
        request.skill,
        request.preferences or [],
        request.difficulty,
    )

    reranked = rerank_with_tfidf(
        ranked,
        request.skill,
        request.preferences or [],
        request.max_results,
    )

    final_courses = [simplified_to_course(sc) for sc in reranked]

    logger.info(f"Returning {len(final_courses)} recommendations")
    
    return RecommendationResponse(
        skill=request.skill,
        total_results=len(final_courses),
        recommendations=final_courses,
        metadata={
            "providers": provider_stats,
            "total_fetched": len(all_simplified),
            "filtered_count": len(ranked),
        }
    )
