"""
Content-based similarity module using TF-IDF + Maximal Marginal Relevance (MMR).

Pipeline:
  1. Build TF-IDF matrix from all candidate courses (title + description + tags)
  2. Build a query vector from skill + preferences
  3. Compute cosine similarity between query and each course
  4. Blend TF-IDF similarity with existing relevance_score
  5. Apply MMR to re-rank for diversity — avoids returning near-duplicate results

MMR formula:
  score(d) = λ * sim(d, query) - (1 - λ) * max_sim(d, already_selected)

  λ = 0.7 → 70% relevance, 30% diversity
"""

import logging
from typing import List, Union

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from models.schemas import Course
from models.batch_models import SimplifiedCourse

logger = logging.getLogger(__name__)

# MMR lambda: higher = more relevance-focused, lower = more diverse
_MMR_LAMBDA = 0.7

# Weight for blending TF-IDF score into existing relevance_score
_TFIDF_BLEND_WEIGHT = 0.3


def _build_document(course: Union[Course, SimplifiedCourse]) -> str:
    """Combine title, description, and tags into a single text document."""
    tags_text = " ".join(course.tags) if course.tags else ""
    return f"{course.title} {course.title} {course.description} {tags_text}".strip()


def rerank_with_tfidf(
    courses: List[Union[Course, SimplifiedCourse]],
    skill: str,
    preferences: List[str],
    top_n: int,
) -> List[Union[Course, SimplifiedCourse]]:
    """
    Re-rank courses using TF-IDF similarity + MMR diversity.

    Args:
        courses: Already-ranked list from the ranking engine
        skill: The skill being searched
        preferences: User preferences
        top_n: Number of results to return

    Returns:
        Diversified list of up to top_n courses
    """
    if len(courses) <= 1:
        return courses[:top_n]

    # Build corpus — title is doubled to give it more weight
    documents = [_build_document(c) for c in courses]
    query = f"{skill} {' '.join(preferences or [])}"

    try:
        vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words="english",
            ngram_range=(1, 2),  # unigrams + bigrams
            min_df=1,
        )

        # Fit on corpus + query together so query terms are in the vocabulary
        all_texts = documents + [query]
        tfidf_matrix = vectorizer.fit_transform(all_texts)

        course_vectors = tfidf_matrix[:-1]   # all but last
        query_vector   = tfidf_matrix[-1:]   # last row

        # Cosine similarity between query and each course
        tfidf_scores = cosine_similarity(query_vector, course_vectors).flatten()

        # Blend TF-IDF score with existing relevance_score
        for i, course in enumerate(courses):
            blended = (
                (1 - _TFIDF_BLEND_WEIGHT) * course.relevance_score
                + _TFIDF_BLEND_WEIGHT * float(tfidf_scores[i])
            )
            course.relevance_score = round(min(blended, 1.0), 4)

        # MMR re-ranking for diversity
        return _mmr(courses, course_vectors, tfidf_scores, top_n)

    except Exception as e:
        logger.warning(f"TF-IDF re-ranking failed, falling back to original order: {e}")
        return courses[:top_n]


def _mmr(
    courses: List[Union[Course, SimplifiedCourse]],
    vectors,
    relevance_scores: np.ndarray,
    top_n: int,
) -> List[Union[Course, SimplifiedCourse]]:
    """
    Maximal Marginal Relevance selection.
    Iteratively picks the course that best balances relevance and diversity.
    """
    selected_indices = []
    remaining = list(range(len(courses)))

    # Precompute pairwise cosine similarity between all courses
    pairwise_sim = cosine_similarity(vectors).tolist()

    while len(selected_indices) < top_n and remaining:
        if not selected_indices:
            # First pick: highest relevance score
            best = max(remaining, key=lambda i: relevance_scores[i])
        else:
            # MMR: balance relevance vs similarity to already-selected
            def mmr_score(i):
                rel = float(relevance_scores[i])
                max_sim = max(pairwise_sim[i][j] for j in selected_indices)
                return _MMR_LAMBDA * rel - (1 - _MMR_LAMBDA) * max_sim

            best = max(remaining, key=mmr_score)

        selected_indices.append(best)
        remaining.remove(best)

    return [courses[i] for i in selected_indices]
