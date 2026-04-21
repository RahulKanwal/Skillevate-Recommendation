"""
Ranking engine — scores and sorts courses using a multi-signal approach.

Composite score (before multiplicative penalties):
  relevance  0.45  — keyword match (title + description + tags), spam- and coherence-penalized
  quality    0.25  — provider-specific (views/likes, playlist size, stars/forks, reactions)
  authority  0.20  — official channel / trusted org (see core/authority.py); capped when relevance is low
  recency    0.10  — exponential decay by publish date

Additional multipliers: meta-content, difficulty mismatch, shallow-format vs depth preferences,
GitHub awesome/roadmap vs hands-on preferences.
"""

import math
import re
import logging
from datetime import datetime, timezone
from typing import List, Union, Optional

from models.schemas import Course, DifficultyLevel
from models.batch_models import SimplifiedCourse
from core.authority import get_youtube_authority, get_github_authority
from core.skill_taxonomy import expand_skill

logger = logging.getLogger(__name__)

# Approximate upper bounds for log-normalization
_MAX_STARS = 200_000
_MAX_FORKS = 50_000
_MAX_VIEWS = 10_000_000
_MAX_LIKES = 200_000
_MAX_PLAYLIST_ITEMS = 120

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

        # Filter out results with very low relevance — catches completely off-topic content
        # High-authority content (institutes, official channels) gets a lower threshold
        def _passes_threshold(c) -> bool:
            authority = self._authority_score(c, skill)
            threshold = 0.15 if authority >= 0.8 else 0.20
            return c.relevance_score >= threshold

        courses = [c for c in courses if _passes_threshold(c)]

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
        # Prevent viral off-topic content: popularity cannot rescue low topical match
        if relevance < 0.25:
            quality = min(quality, 0.32 + relevance * 2.15)
        authority = self._authority_score(course, skill)
        recency   = self._recency_score(course)
        difficulty_multiplier = self._difficulty_mismatch_penalty(course, preferences)
        meta_multiplier       = self._meta_content_penalty(course)
        depth_multiplier      = self._depth_format_penalty(course, preferences)
        github_list_multiplier = self._github_curated_list_penalty(course, preferences)

        score = (
            relevance * 0.45
            + quality  * 0.25
            + authority * 0.20
            + recency  * 0.10
        )
        # Authority should boost relevant content, not rescue irrelevant content
        # If relevance is very low, cap the authority contribution
        if relevance < 0.2:
            score = relevance * 0.45 + quality * 0.25 + min(authority, 0.3) * 0.20 + recency * 0.10
        combined = (
            score
            * difficulty_multiplier
            * meta_multiplier
            * depth_multiplier
            * github_list_multiplier
        )
        yt = getattr(course, "_yt_internal", None) or {}
        if yt.get("kind") == "playlist" and preferences:
            pj = " ".join(preferences).lower()
            if any(
                k in pj
                for k in (
                    "comprehensive",
                    "full course",
                    "complete course",
                    "course series",
                    "playlist",
                    "deep dive",
                    "in-depth",
                    "in depth",
                )
            ):
                combined = min(combined * 1.12 + 0.02, 1.0)
        return round(min(combined, 1.0), 4)

    # ── 1. Relevance (keyword match + spam penalty + coherence) ───────────────

    def _relevance_score(
        self,
        course: Union[Course, SimplifiedCourse],
        skill: str,
        preferences: List[str],
    ) -> float:
        # Expand skill to related terms for broader matching
        expanded_terms = expand_skill(skill, preferences)

        title_score = self._keyword_match_score(course.title, skill, preferences, expanded_terms)
        desc_score  = self._keyword_match_score(course.description, skill, preferences, expanded_terms)
        tag_score   = self._tag_match_score(course.tags, skill, preferences, expanded_terms)

        raw = title_score * 0.5 + desc_score * 0.35 + tag_score * 0.15

        spam_multiplier = self._spam_penalty(f"{course.title} {course.description}", skill)
        coherence = self._coherence_score(course.title, course.description)

        return min(raw * spam_multiplier * coherence, 1.0)

    def _keyword_match_score(self, text: str, skill: str, preferences: List[str], expanded_terms: List[str] = None) -> float:
        if not text:
            return 0.0

        text_lower  = text.lower()
        skill_lower = skill.lower()

        # Exact skill match
        if skill_lower in text_lower:
            score = 0.4
        else:
            # Check expanded terms — partial credit for related terms
            expansion_match = 0.0
            if expanded_terms:
                for term in expanded_terms[1:]:  # skip index 0 (original skill)
                    if term in text_lower:
                        expansion_match = 0.25
                        break
            skill_words = skill_lower.split()
            word_match = (sum(1 for w in skill_words if w in text_lower) / len(skill_words)) * 0.3 if skill_words else 0.0
            score = max(word_match, expansion_match)

        # Preference matching — weighted more heavily (up to 0.6)
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
            score += min((pref_matches / len(preferences)) * 0.6, 0.6)

        return min(score, 1.0)

    def _tag_match_score(self, tags: List[str], skill: str, preferences: List[str], expanded_terms: List[str] = None) -> float:
        if not tags:
            return 0.0

        tags_lower  = [t.lower() for t in tags]
        skill_lower = skill.lower()

        skill_match = 0.5 if skill_lower in tags_lower else (
            sum(1 for w in skill_lower.split() if any(w in t for t in tags_lower))
            / max(len(skill_lower.split()), 1) * 0.3
        )

        # Boost if any expanded term appears in tags
        if not skill_match and expanded_terms:
            for term in expanded_terms[1:]:
                if any(term in t for t in tags_lower):
                    skill_match = 0.2
                    break

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
        Quality signals per provider:
          GitHub  — log-normalized stars + forks
          YouTube — views/likes for videos; playlist size for playlists
          Dev.to  — log-normalized reactions + comments
        """
        yt_meta = getattr(course, "_yt_internal", None) or {}
        if course.provider == "YouTube" and yt_meta.get("kind") == "playlist":
            n = int(yt_meta.get("item_count") or 0)
            item_score = math.log1p(n) / math.log1p(_MAX_PLAYLIST_ITEMS)
            return min(0.28 + item_score * 0.72, 1.0)

        # YouTube videos
        view_count = getattr(course, "view_count", None)
        like_count = getattr(course, "like_count", None)
        if view_count is not None:
            view_score = math.log1p(view_count) / math.log1p(_MAX_VIEWS)
            like_score = math.log1p(like_count or 0) / math.log1p(_MAX_LIKES)
            return min(view_score * 0.6 + like_score * 0.4, 1.0)

        # Dev.to — stars field holds reactions, forks holds comments
        if course.provider == "Dev.to":
            reactions = course.stars or 0
            comments  = course.forks or 0
            _MAX_REACTIONS = 2_000
            _MAX_COMMENTS  = 200
            r_score = math.log1p(reactions) / math.log1p(_MAX_REACTIONS)
            c_score = math.log1p(comments)  / math.log1p(_MAX_COMMENTS)
            return min(r_score * 0.7 + c_score * 0.3, 1.0)

        # GitHub quality
        if hasattr(course, "stars") and course.stars is not None:
            stars = course.stars or 0
            forks = course.forks or 0
            star_score = math.log1p(stars) / math.log1p(_MAX_STARS)
            fork_score = math.log1p(forks) / math.log1p(_MAX_FORKS)
            return min(star_score * 0.7 + fork_score * 0.3, 1.0)

        # Legacy Course object with rating
        if hasattr(course, "rating") and course.rating:
            return min(course.rating / 5.0, 1.0)

        return 0.5  # neutral fallback

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

        # Dev.to articles — neutral authority (community content, no whitelist)
        if course.provider == "Dev.to":
            return 0.0

        return 0.0

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _meta_content_penalty(self, course: Union[Course, SimplifiedCourse]) -> float:
        """
        Penalizes meta-content — videos/repos that are *about* learning resources
        rather than being learning resources themselves.

        Examples of penalized content:
          - "I Tried 50 Python Courses. Here Are Top 5."
          - "Stanford's FREE data science book and course are the best yet"
          - "Best Python Resources for 2024"
          - "Is this course worth it?"

        Returns:
          0.1  — strong meta-content signal (review/list/recommendation video)
          0.5  — moderate signal
          1.0  — no signal, no penalty
        """
        title = course.title.lower()
        desc  = (course.description or "").lower()[:300]
        text  = f"{title} {desc}"

        # Strong meta-content patterns — these are almost never actual courses
        strong_patterns = [
            r"i tried \d+",
            r"top \d+ (courses|resources|tutorials|books|videos)",
            r"best \d+ (courses|resources|tutorials|books|videos)",
            r"\d+ (courses|resources|tutorials|books) (you|to|for|that)",
            r"(courses|resources|tutorials) (you should|to learn|for \d+)",
            r"(free|best|top) .{0,30} (book|course|resource) .{0,20} (best|yet|ever|review|excellent|amazing|great)",
            r"is .{0,30} (course|tutorial|book) worth",
            r"(review|reviewed|reviewing) .{0,30} (course|tutorial|book)",
            r"(ranked|ranking) .{0,30} (courses|tutorials|resources)",
            r"(free|paid) .{0,20} (courses?|tutorials?) .{0,20} (are|is) .{0,20} (excellent|great|amazing|best|good)",
            r"(harvard|stanford|mit|coursera|udemy).{0,30}(free|best).{0,30}(course|tutorial)",
        ]

        # Moderate patterns — could be meta or could be legitimate
        moderate_patterns = [
            r"(best|top) (python|javascript|docker|kubernetes|react|fastapi|django).{0,20}(courses|resources|tutorials)",
            r"(free|paid) (courses|resources|tutorials) for",
            r"how i (learned|learn|studied|study)",
            r"my (learning|study) (journey|path|roadmap)",
            r"(roadmap|path) (for|to) (learn|become|master)",
            r"(learn|master) .{0,20} (fast|quickly|in \d+|in one|overnight)",
            r"you need to learn",
            r"why you (should|need to|must) learn",
            r"(stop|start) (learning|using|doing)",
        ]

        for pattern in strong_patterns:
            if re.search(pattern, text):
                logger.debug(f"Strong meta-content penalty: '{course.title}'")
                return 0.1

        for pattern in moderate_patterns:
            if re.search(pattern, text):
                logger.debug(f"Moderate meta-content penalty: '{course.title}'")
                return 0.5

        return 1.0

    def _depth_format_penalty(
        self,
        course: Union[Course, SimplifiedCourse],
        preferences: List[str],
    ) -> float:
        """
        When preferences ask for depth (intermediate/advanced/senior), downrank
        ultra-short explainers ("in 5 minutes", "explained in 10 minutes").
        """
        if not preferences:
            return 1.0
        joined = " ".join(preferences).lower()
        wants_depth = any(
            w in joined
            for w in (
                "intermediate",
                "advanced",
                "senior",
                "experienced",
                "professional",
                "working developer",
                "in-depth",
                "in depth",
                "comprehensive",
            )
        )
        if not wants_depth:
            return 1.0
        blob = f"{course.title} {(course.description or '')[:400]}".lower()
        if re.search(
            r"\bin \d+\s*(min|minute|mins)|explained in \d+|"
            r"\d+\s*(min|minute|mins) (!|\.|\||#|$)|#shorts",
            blob,
        ):
            return 0.35
        return 1.0

    def _github_curated_list_penalty(
        self,
        course: Union[Course, SimplifiedCourse],
        preferences: List[str],
    ) -> float:
        """
        When the user wants hands-on / project work, slightly deprioritize
        generic awesome-lists and roadmaps (still useful, but not primary learning).
        """
        if course.provider != "GitHub":
            return 1.0
        if not preferences:
            return 1.0
        joined = " ".join(preferences).lower()
        wants_hands_on = any(
            w in joined
            for w in (
                "project",
                "hands-on",
                "hands on",
                "build",
                "practice",
                "coding",
            )
        )
        if not wants_hands_on:
            return 1.0
        name = course.title.lower()
        if any(
            k in name
            for k in ("awesome", "roadmap", "resources", "learning-resources", "curated")
        ):
            return 0.68
        return 1.0

    def _difficulty_mismatch_penalty(
        self,
        course: Union[Course, SimplifiedCourse],
        preferences: List[str],
    ) -> float:
        """
        Detects difficulty level requested in preferences and penalizes content
        that signals a conflicting difficulty level.

        Returns a multiplier:
          1.0  — no difficulty preference, or content matches, or no signal in content
          0.5  — soft mismatch (e.g. user wants advanced, content says "beginner")
          0.25 — hard mismatch (e.g. user wants advanced, content says "for absolute beginners")
        """
        if not preferences:
            return 1.0

        # Difficulty keyword groups
        BEGINNER_SIGNALS = {
            "beginner", "beginners", "introduction", "intro", "basics",
            "basic", "getting started", "crash course", "for dummies",
            "absolute beginner", "zero to hero", "from scratch", "101",
            "no experience", "first steps", "start here",
        }
        ADVANCED_SIGNALS = {
            "advanced", "expert", "deep dive", "in depth", "internals",
            "under the hood", "production", "architecture", "senior",
            "mastery", "master class", "professional",
        }
        INTERMEDIATE_SIGNALS = {
            "intermediate", "mid level", "next level", "beyond basics",
            "practical", "real world", "hands on",
        }

        # Detect requested difficulty from preferences
        requested = None
        for pref in preferences:
            p = pref.lower().strip()
            if p in {"beginner", "beginners", "basic", "basics", "introduction", "intro"}:
                requested = "beginner"
                break
            if p in {"advanced", "expert", "senior"}:
                requested = "advanced"
                break
            if p in {"intermediate", "mid", "mid-level"}:
                requested = "intermediate"
                break

        if requested is None:
            return 1.0  # no difficulty preference expressed

        # Detect content difficulty from title + description
        content = f"{course.title} {course.description}".lower()

        def _has_signal(signals: set) -> bool:
            return any(s in content for s in signals)

        content_is_beginner     = _has_signal(BEGINNER_SIGNALS)
        content_is_advanced     = _has_signal(ADVANCED_SIGNALS)
        content_is_intermediate = _has_signal(INTERMEDIATE_SIGNALS)

        # Apply penalty for mismatch
        if requested == "advanced":
            if content_is_beginner:
                return 0.1  # very strong mismatch
            if content_is_intermediate:
                return 0.5
            if content_is_advanced:
                return 1.0

        elif requested == "beginner":
            if content_is_advanced:
                return 0.1
            if content_is_intermediate:
                return 0.6
            if content_is_beginner:
                return 1.0

        elif requested == "intermediate":
            if content_is_beginner:
                return 0.3  # stronger penalty than before
            if content_is_advanced:
                return 0.5
            if content_is_intermediate:
                return 1.0

        return 1.0  # no detectable signal in content — no penalty

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
