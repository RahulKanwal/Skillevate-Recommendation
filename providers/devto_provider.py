"""
Dev.to provider — fetches technical articles via the Forem public API.

API docs: https://developers.forem.com/api/v0
No API key required for read operations.

Quality signals used:
  - public_reactions_count  (like GitHub stars — community upvotes)
  - comments_count          (engagement signal)
  - reading_time_minutes    (proxy for depth/substance)
"""

import httpx
from typing import List, Optional
from models.batch_models import SimplifiedCourse
import logging

logger = logging.getLogger(__name__)

# Upper bounds for log-normalization
_MAX_REACTIONS = 2_000
_MAX_COMMENTS  = 200

# Minimum reading time to filter out very short posts (< 4 min = likely not a tutorial)
_MIN_READING_TIME = 4

# Minimum reactions to filter out low-quality/no-engagement articles
_MIN_REACTIONS = 10


class DevToProvider:
    """
    Dev.to provider for technical articles and tutorials.
    Uses the public Forem API — no authentication required.
    """

    BASE_URL = "https://dev.to/api"

    async def fetch_courses(
        self,
        skill: str,
        max_results: int = 10,
        language: Optional[str] = None,
        preferences: Optional[List[str]] = None,
    ) -> List[SimplifiedCourse]:
        """
        Fetch technical articles from Dev.to by tag and keyword search.

        Strategy:
          1. Search by skill as a tag (most precise)
          2. Search by preference tags if available
          Merge and deduplicate results.
        """
        tags = self._build_tags(skill, preferences)
        per_page = min(max_results * 2, 30)  # fetch extra to allow filtering

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                all_items = []
                seen_ids: set = set()

                for tag in tags[:2]:  # max 2 tag queries to avoid rate limits
                    items = await self._fetch_by_tag(client, tag, per_page)
                    for item in items:
                        if item["id"] not in seen_ids:
                            seen_ids.add(item["id"])
                            all_items.append(item)

                return self._parse_response(all_items, skill, language, max_results)

        except httpx.HTTPError as e:
            logger.error(f"Dev.to API error: {e}")
            return []

    async def _fetch_by_tag(
        self, client: httpx.AsyncClient, tag: str, per_page: int
    ) -> list:
        """Fetch articles for a single tag, sorted by relevance (top articles)."""
        try:
            resp = await client.get(
                f"{self.BASE_URL}/articles",
                params={
                    "tag": tag.lower().replace(" ", ""),
                    "per_page": per_page,
                    "top": 90,  # top articles from last 90 days — wider pool for filtering
                },
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.warning(f"Dev.to tag fetch failed for '{tag}': {e}")
            return []

    def _build_tags(self, skill: str, preferences: Optional[List[str]]) -> List[str]:
        """
        Build a list of Dev.to tags to query.
        Dev.to tags are lowercase, no spaces (e.g. "machinelearning", "fastapi").
        """
        # Primary tag: skill normalized
        primary = skill.lower().replace(" ", "").replace(".", "").replace("+", "plus")

        tags = [primary]

        # Add preference-based tags if they look like tech terms
        if preferences:
            for pref in preferences:
                pref_tag = pref.lower().replace(" ", "").replace(".", "")
                if len(pref_tag) <= 20 and pref_tag not in tags:
                    tags.append(pref_tag)

        return tags

    def _parse_response(
        self,
        items: list,
        skill: str,
        language: Optional[str],
        max_results: int,
    ) -> List[SimplifiedCourse]:
        """Parse Dev.to API response into SimplifiedCourse objects."""
        courses = []
        skill_lower = skill.lower()

        for item in items:
            # Filter by minimum reading time — very short posts aren't tutorials
            if item.get("reading_time_minutes", 0) < _MIN_READING_TIME:
                continue

            # Filter by minimum reactions — low engagement = low quality signal
            if (item.get("public_reactions_count", 0) or 0) < _MIN_REACTIONS:
                continue

            # Language filter — Dev.to returns a language field
            if language and item.get("language") and item["language"] != language:
                continue

            title = item.get("title", "")
            description = item.get("description", "")
            tags = [t.lower() for t in item.get("tag_list", [])]
            title_lower = title.lower()
            desc_lower = description.lower()

            # Skill must appear in the title for strong relevance signal
            # (tag-only matches are too loose — "python" tag appears on everything)
            if skill_lower not in title_lower:
                continue

            # Must have clear educational intent in the title
            edu_title_keywords = [
                "tutorial", "guide", "how to", "introduction", "getting started",
                "deep dive", "explained", "walkthrough", "step by step", "build",
                "implement", "create", "tips", "best practices", "cheatsheet",
                "roadmap", "overview", "fundamentals", "learn", "course",
            ]
            if not any(k in title_lower for k in edu_title_keywords):
                logger.debug(f"Dev.to: no educational signal in title, skipping: '{title}'")
                continue

            reactions = item.get("public_reactions_count", 0) or 0
            comments  = item.get("comments_count", 0) or 0

            course = SimplifiedCourse(
                id=f"devto_{item['id']}",
                title=title,
                provider="Dev.to",
                url=item.get("url", ""),
                description=description,
                tags=tags,
                relevance_score=0.5,
                # Quality signals — reactions ≈ stars, comments ≈ forks
                stars=reactions,   # reuse stars field for reactions
                forks=comments,    # reuse forks field for comments
                published_at=item.get("published_at"),
            )
            courses.append(course)

            if len(courses) >= max_results * 2:
                break

        return courses
