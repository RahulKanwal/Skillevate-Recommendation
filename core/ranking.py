"""
Ranking engine — scores and sorts courses using a multi-signal approach.

Scoring breakdown (must sum to 1.0):
  relevance_score  0.35  — keyword match (title + description + tags), spam-penalized
  quality_score    0.35  — GitHub stars/forks (log-normalized); YouTube uses recency as proxy
  authority_score  0.20  — official channel / trusted org boost (see core/authority.py)
  recency_score    0.10  — exponential decay based on last updated / published date

Improvements over the previous version:
  1. Quality signals  — GitHub stars + forks fed into score (were ignored before)
  2. Spam penalty     — keyword density check caps abusive title/description stuffing
  3. Recency decay    — older content scores lower on fast-moving topics
  4. Coherence check  — title/description word overlap; incoherent content penalized
  5. Authority boost  — official channels/orgs rank above random creators
"""

import math
import re
import logging
from datetime import datetime, timezone
from typing import List, Union, Optional

from models.schemas import Course, DifficultyLevel
from models.batch_models import SimplifiedCourse
from core.authority import get_youtube_authority, get_github_authority

logger = logging.getLogger(__name__)

# Approximate upper bounds for log-normalization
_MAX_STARS = 200_000
_MAX_FORKS = 50_000

# Recency half-life in days (~1 year decay)
_RECENCY_HALF_LIFE_DAYS = 365


class RankingEngine:
    """
    Ranks and filters courses using a weighted multi-signal scoring algorithm.
    """

    def rank_courses(
        self,
        courses: Union[List[Course], List[SimplifiedCourse]],
        skill: str,
        preferences: List[str],
        difficulty: DifficultyLevel = None,
    ) -> Union[List[Course], List[SimplifiedCourse]]:
        if not courses:
            return []

        for course in courses:
            course.relevance_score = self._calculate_score(course, skill, preferences)

        # Difficulty filter (Course objects only)
        if difficulty and difficulty != DifficultyLevel.ALL:
            if hasattr(courses[0], "difficulty"):
                courses = [c for c in courses if self._matches_difficulty(c, difficulty)]

        courses = self._deduplicate(courses)
        courses.sort(key=lambda x: x.relevance_score, reverse=True)
        return courses

    # ── Main score ────────────────────────────────────────────────────────────

    def _calculate_score(
        self,
        course: Union[Course, SimplifiedCourse],
        skill: str,
        preferences: List[str],
    ) -> float:
        relevance = self._relevance_score(course, skill, preferences)
        quality   = self._quality_score(course)
        authority = self._authority_score(course, skill)
        recency   = self._recency_score(course)

        score = (
            relevance * 0.35
            + quality  * 0.35
            + authority * 0.20
            + recency  * 0.10
        )
        return round(min(score, 1.0), 4)

    # ── 1. Relevance (keyword match + spam penalty + coherence) ───────────────

    def _relevance_score(
        self,
        course: Union[Course, SimplifiedCourse],
        skill: str,
        preferences: List[str],
    ) -> float:
        title_score = self._keyword_match_score(course.title, skill, preferences)
        desc_score  = self._keyword_match_score(course.description, skill, preferences)
        tag_score   = self._tag_match_score(course.tags, skill, preferences)

        raw = title_score * 0.5 + desc_score * 0.35 + tag_score * 0.15

        # Spam penalty: if keyword density in title+desc is suspiciously high, halve it
        spam_multiplier = self._spam_penalty(
            f"{course.title} {course.description}", skill
        )

        # Coherence: title and description should share meaningful words
        coherence = self._coherence_score(course.title, course.description)

        return min(raw * spam_multiplier * coherence, 1.0)

    def _keyword_match_score(self, text: str, skill: str, preferences: List[str]) -> float:
        if not text:
            return 0.0

        text_lower  = text.lower()
        skill_lower = skill.lower()

        # Exact skill match
        if skill_lower in text_lower:
            score = 0.6
        else:
            skill_words = skill_lower.split()
            matches = sum(1 for w in skill_words if w in text_lower)
            score = (matches / len(skill_words)) * 0.5 if skill_words else 0.0

        # Preference matching (adds up to 0.4)
        if preferences:
            pref_matches = 0.0
            for pref in preferences:
                pref_lower = pref.lower()
                if pref_lower in text_lower:
                    pref_matches += 1
                else:
                    pref_words = pref_lower.split()
                    if any(w in text_lower for w in pref_words):
                        pref_matches += 0.5
            score += min((pref_matches / len(preferences)) * 0.4, 0.4)

        return min(score, 1.0)

    def _tag_match_score(self, tags: List[str], skill: str, preferences: List[str]) -> float:
        if not tags:
            return 0.0

        tags_lower  = [t.lower() for t in tags]
        skill_lower = skill.lower()

        skill_match = 0.5 if skill_lower in tags_lower else (
            sum(1 for w in skill_lower.split() if any(w in t for t in tags_lower))
            / max(len(skill_lower.split()), 1) * 0.3
        )

        pref_match = 0.0
        if preferences:
            for pref in preferences:
                pref_lower = pref.lower()
                if pref_lower in tags_lower:
                    pref_match += 1
                else:
                    pref_words = pref_lower.split()
                    if any(w in t for w in pref_words for t in tags_lower):
                        pref_match += 0.5
            pref_match = (pref_match / len(preferences)) * 0.5

        return min(skill_match + pref_match, 1.0)

    def _spam_penalty(self, text: str, skill: str) -> float:
        """
        Improvement #2 — Spam/keyword stuffing penalty.
        If the skill keyword makes up >10% of all words, halve the relevance score.
        """
        if not text or not skill:
            return 1.0
        words      = text.lower().split()
        word_count = max(len(words), 1)
        skill_words = skill.lower().split()
        # Count how many words in the text are skill words
        matches = sum(1 for w in words if w in skill_words)
        density = matches / word_count
        if density > 0.10:
            logger.debug(f"Spam penalty applied: density={density:.2f}")
            return 0.5
        return 1.0

    def _coherence_score(self, title: str, description: str) -> float:
        """
        Improvement #4 — Title/description coherence.
        Measures word overlap between title and description.
        A title that shares no words with its description is suspicious.
        Returns a multiplier between 0.7 and 1.0 (never fully zeroes out).
        """
        if not title or not description:
            return 1.0

        stop_words = {"the", "a", "an", "and", "or", "for", "to", "in", "of", "with", "how", "is"}
        title_words = {w for w in re.sub(r"[^\w\s]", "", title.lower()).split() if w not in stop_words}
        desc_words  = {w for w in re.sub(r"[^\w\s]", "", description.lower()).split() if w not in stop_words}

        if not title_words:
            return 1.0

        overlap = len(title_words & desc_words) / len(title_words)
        # Map overlap [0, 1] → coherence multiplier [0.7, 1.0]
        return 0.7 + overlap * 0.3

    # ── 2. Quality (stars, forks for GitHub; recency proxy for YouTube) ───────

    def _quality_score(self, course: Union[Course, SimplifiedCourse]) -> float:
        """
        Improvement #1 — Quality signals.
        GitHub: log-normalized stars + forks.
        YouTube: no rating available from search API, returns neutral 0.5.
        """
        if not hasattr(course, "stars") or course.stars is None:
            # Course objects (legacy) or YouTube without stats — neutral
            if hasattr(course, "rating") and course.rating:
                return min(course.rating / 5.0, 1.0)
            return 0.5

        stars = course.stars or 0
        forks = course.forks or 0

        star_score = math.log1p(stars) / math.log1p(_MAX_STARS)
        fork_score = math.log1p(forks) / math.log1p(_MAX_FORKS)

        return min(star_score * 0.7 + fork_score * 0.3, 1.0)

    # ── 3. Recency ────────────────────────────────────────────────────────────

    def _recency_score(self, course: Union[Course, SimplifiedCourse]) -> float:
        """
        Improvement #3 — Recency decay.
        Exponential decay with ~1 year half-life.
        Content updated today → 1.0; content from 3 years ago → ~0.1.
        """
        published_at = getattr(course, "published_at", None)
        if not published_at:
            return 0.5  # unknown date → neutral

        try:
            # Handle both "2023-01-15T10:00:00Z" and "2023-01-15T10:00:00.000Z"
            date_str = published_at.replace("Z", "+00:00")
            dt = datetime.fromisoformat(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            days_old = (datetime.now(timezone.utc) - dt).days
            return math.exp(-days_old / _RECENCY_HALF_LIFE_DAYS)
        except (ValueError, AttributeError):
            return 0.5

    # ── 4. Authority ──────────────────────────────────────────────────────────

    def _authority_score(self, course: Union[Course, SimplifiedCourse], skill: str) -> float:
        """
        Improvement #5 — Authority boost.
        Delegates to core/authority.py which holds the whitelists.
        """
        if course.provider == "YouTube":
            channel_id   = getattr(course, "channel_id", None)
            channel_name = getattr(course, "channel_name", None)
            return get_youtube_authority(channel_id, channel_name, skill)

        if course.provider == "GitHub":
            org_login = getattr(course, "org_login", None)
            return get_github_authority(org_login, skill)

        return 0.0

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _matches_difficulty(self, course: Course, difficulty: DifficultyLevel) -> bool:
        if not course.difficulty:
            return True
        return course.difficulty.lower() == difficulty.value.lower()

    def _deduplicate(
        self, courses: Union[List[Course], List[SimplifiedCourse]]
    ) -> Union[List[Course], List[SimplifiedCourse]]:
        seen_titles = set()
        unique = []
        for course in courses:
            normalized = re.sub(r"[^\w\s]", "", course.title.lower())
            if normalized not in seen_titles:
                seen_titles.add(normalized)
                unique.append(course)
        return unique
