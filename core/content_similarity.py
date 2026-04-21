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
    Re-rank courses using TF-IDF similarity + MMR diversity,
    with a per-provider cap to ensure balanced results.
    """
    if len(courses) <= 1:
        return courses[:top_n]

    # Per-provider caps: soft targets so one source (often Dev.to) cannot fill
    # the entire list when YouTube/GitHub also returned candidates.
    providers_present = {c.provider for c in courses}
    has_yt = "YouTube" in providers_present
    has_gh = "GitHub" in providers_present
    has_dev = "Dev.to" in providers_present

    if has_yt or has_gh:
        dev_cap = max(1, min(round(top_n * 0.38), top_n))
    else:
        dev_cap = top_n

    provider_caps = {
        "YouTube": max(2, round(top_n * 0.42)),
        "GitHub": max(1, round(top_n * 0.32)),
        "Dev.to": dev_cap if has_dev else top_n,
    }

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

        # Drop anything that still scores too low after blending
        filtered = [(i, c) for i, c in enumerate(courses) if c.relevance_score >= 0.18]
        if not filtered:
            return courses[:top_n]
        indices, courses = zip(*filtered)
        courses = list(courses)
        course_vectors = course_vectors[list(indices)]
        tfidf_scores = tfidf_scores[list(indices)]

        # MMR re-ranking for diversity with provider caps
        return _mmr(courses, course_vectors, tfidf_scores, top_n, provider_caps)

    except Exception as e:
        logger.warning(f"TF-IDF re-ranking failed, falling back to original order: {e}")
        return courses[:top_n]


def _mmr(
    courses: List[Union[Course, SimplifiedCourse]],
    vectors,
    relevance_scores: np.ndarray,
    top_n: int,
    provider_caps: dict = None,
) -> List[Union[Course, SimplifiedCourse]]:
    """
    Maximal Marginal Relevance selection with optional per-provider caps.
    Iteratively picks the course that best balances relevance and diversity.
    """
    selected_indices = []
    remaining = list(range(len(courses)))
    provider_counts: dict = {}

    # Precompute pairwise cosine similarity between all courses
    pairwise_sim = cosine_similarity(vectors).tolist()

    while len(selected_indices) < top_n and remaining:
        if not selected_indices:
            best = max(remaining, key=lambda i: relevance_scores[i])
        else:
            def mmr_score(i):
                rel = float(relevance_scores[i])
                max_sim = max(pairwise_sim[i][j] for j in selected_indices)
                return _MMR_LAMBDA * rel - (1 - _MMR_LAMBDA) * max_sim

            best = max(remaining, key=mmr_score)

        provider = courses[best].provider
        cap = provider_caps.get(provider, top_n) if provider_caps else top_n
        current_count = provider_counts.get(provider, 0)

        if current_count >= cap:
            # Provider cap reached — skip and try next best from eligible providers
            remaining.remove(best)
            eligible = [i for i in remaining
                        if provider_counts.get(courses[i].provider, 0)
                        < (provider_caps.get(courses[i].provider, top_n) if provider_caps else top_n)]
            if not eligible:
                # All providers at cap — fill remaining from any provider
                eligible = remaining
            if not eligible:
                break
            if not selected_indices:
                best = max(eligible, key=lambda i: relevance_scores[i])
            else:
                best = max(eligible, key=mmr_score)
            remaining.remove(best)
            provider = courses[best].provider

        else:
            remaining.remove(best)

        selected_indices.append(best)
        provider_counts[provider] = provider_counts.get(provider, 0) + 1

    return [courses[i] for i in selected_indices]
