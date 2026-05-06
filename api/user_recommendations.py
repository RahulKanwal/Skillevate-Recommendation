"""
Cache orchestration logic for POST /api/user-recommendations.

Implements the check-then-generate-then-store flow:
  1. Fetch the active analysis document from MongoDB.
  2. Return cached recommendations immediately on a cache hit.
  3. On a cache miss, call the batch engine, map results, write back, and return.
"""

import logging
from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from api.batch_recommendations import get_batch_recommendations
from db.mongodb import get_database
from models.batch_models import BatchRecommendationRequest, SkillRequest, SkillRecommendationResult
from models.user_recommendation_models import (
    Recommendation,
    UserRecommendationRequest,
    UserRecommendationResponse,
)

logger = logging.getLogger(__name__)


async def _fetch_active_analysis(
    db: AsyncIOMotorDatabase,
    user_id: str,
    analysis_id: Optional[str],
) -> Optional[dict]:
    """
    Query the Analyses collection for the active analysis document.

    Applies ``user_id=ObjectId(user_id)`` and ``is_latest=True`` filters.
    When *analysis_id* is provided, additionally filters by ``_id=ObjectId(analysis_id)``.

    Returns:
        Raw MongoDB document dict, or ``None`` if no matching document exists.
    """
    query: dict = {
        "user_id": user_id,
        "is_latest": True,
    }

    if analysis_id is not None:
        query["_id"] = ObjectId(analysis_id)

    logger.info(f"Querying analyses with: {query}")
    document = await db["analyses"].find_one(query)
    logger.info(f"Query result: {document}")

    # If not found, log all documents for this user to help debug
    if document is None:
        logger.warning(f"No document found. Checking all docs for user_id={user_id}")
        collections = await db.list_collection_names()
        logger.warning(f"Collections in database: {collections}")
        async for doc in db["analyses"].find({"user_id": user_id}):
            logger.warning(f"Found doc with user_id match (ignoring is_latest): _id={doc.get('_id')}, is_latest={doc.get('is_latest')}")
        async for doc in db["analyses"].find({}):
            logger.warning(f"All analyses docs: _id={doc.get('_id')}, user_id={doc.get('user_id')}, is_latest={doc.get('is_latest')}")
    return document


def _map_courses_to_recommendations(
    skill_results: List[SkillRecommendationResult],
) -> List[Recommendation]:
    """
    Convert batch engine output to a flat list of ``Recommendation`` objects.

    For each ``SkillRecommendationResult``, every ``SimplifiedCourse`` in its
    ``recommendations`` list is mapped to a ``Recommendation`` with:

    - ``recommendation_id`` — the course's ``id`` field
    - ``status`` — ``"recommended"``
    - ``xp_value`` — ``round(relevance_score * 100)``
    - ``linked_gap`` — the ``skill`` string from the enclosing ``SkillRecommendationResult``

    Returns:
        Flat list of ``Recommendation`` objects (one per course across all skills).
    """
    recommendations: List[Recommendation] = []

    for skill_result in skill_results:
        for course in skill_result.recommendations:
            recommendations.append(
                Recommendation(
                    recommendation_id=course.id,
                    title=course.title,
                    provider=course.provider,
                    url=course.url,
                    description=course.description,
                    tags=course.tags,
                    relevance_score=course.relevance_score,
                    status="recommended",
                    xp_value=round(course.relevance_score * 100),
                    linked_gap=skill_result.skill,
                )
            )

    return recommendations


async def _write_back_recommendations(
    db: AsyncIOMotorDatabase,
    analysis_id: str,
    recommendations: List[Recommendation],
) -> None:
    """
    Atomically update the Analyses document with the generated recommendations.

    Performs a ``$set`` on ``results.recommendations`` using Motor's
    ``update_one``.  Any exception is caught, logged at ERROR level, and
    swallowed so the caller can still return results to the user.
    """
    try:
        await db["analyses"].update_one(
            {"_id": ObjectId(analysis_id)},
            {"$set": {"results.recommendations": [r.model_dump() for r in recommendations]}},
        )
        logger.info(f"Successfully wrote {len(recommendations)} recommendations for analysis_id={analysis_id}")
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to write recommendations back to MongoDB for analysis_id=%s: %s",
            analysis_id,
            exc,
            exc_info=True,
        )


async def get_user_recommendations(
    request: UserRecommendationRequest,
) -> UserRecommendationResponse:
    """
    Orchestrate cache-check → generate → write-back → return.

    Flow:
    1. Fetch the active analysis document from MongoDB.
    2. If not found → HTTP 404.
    3. If ``results.recommendations`` is non-empty → cache hit, return immediately.
    4. If ``results.gaps`` is empty → return empty recommendations (no batch call).
    5. Otherwise → call batch engine, map results, write back, return.

    Raises:
        HTTPException(404): No active analysis found for the given ``user_id``.
        HTTPException(502): Batch engine raised an unhandled exception.
        HTTPException(500): Any other unhandled exception.
    """
    try:
        db: AsyncIOMotorDatabase = get_database()

        # Step 1: Fetch active analysis
        doc = await _fetch_active_analysis(db, request.user_id, request.analysis_id)

        # Step 2: Not found → 404
        if doc is None:
            raise HTTPException(
                status_code=404,
                detail="No active analysis found for this user",
            )

        analysis_id = str(doc["_id"])
        results_subdoc = doc.get("results", {})
        cached_recommendations: list = results_subdoc.get("recommendations", [])
        gaps: list = results_subdoc.get("gaps", [])

        # Step 3: Cache hit — recommendations already stored
        if cached_recommendations:
            recommendations = [
                Recommendation(**rec) for rec in cached_recommendations
            ]
            return UserRecommendationResponse(
                analysis_id=analysis_id,
                user_id=request.user_id,
                gaps=[g["skill"] for g in gaps] if gaps and isinstance(gaps[0], dict) else gaps,
                recommendations=recommendations,
                cached=True,
            )

        # Step 4: Cache miss with empty gaps — nothing to generate
        if not gaps:
            return UserRecommendationResponse(
                analysis_id=analysis_id,
                user_id=request.user_id,
                gaps=[],
                recommendations=[],
                cached=False,
            )

        # Step 5: Cache miss with non-empty gaps — call batch engine
        # Support both old flat string format and new {skill, preferences} format
        if isinstance(gaps[0], dict):
            skill_requests = [
                SkillRequest(
                    skill=g["skill"],
                    preferences=g.get("preferences") or request.preferences
                )
                for g in gaps
            ]
            gap_labels = [g["skill"] for g in gaps]
        else:
            skill_requests = [
                SkillRequest(skill=g, preferences=request.preferences)
                for g in gaps
            ]
            gap_labels = gaps

        batch_request = BatchRecommendationRequest(
            skills=skill_requests,
            max_results=request.max_results,
            language=request.language,
        )

        try:
            batch_response = await get_batch_recommendations(batch_request)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Batch engine failed for user_id=%s: %s",
                request.user_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=502,
                detail="Recommendation engine unavailable",
            ) from exc

        # Map courses → Recommendation objects
        recommendations = _map_courses_to_recommendations(batch_response.results)

        # Write back to MongoDB (failure is logged and swallowed)
        await _write_back_recommendations(db, analysis_id, recommendations)

        return UserRecommendationResponse(
            analysis_id=analysis_id,
            user_id=request.user_id,
            gaps=gap_labels,
            recommendations=recommendations,
            cached=False,
        )

    except HTTPException:
        # Re-raise HTTP exceptions without wrapping them
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Unhandled exception in get_user_recommendations for user_id=%s: %s",
            request.user_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc
