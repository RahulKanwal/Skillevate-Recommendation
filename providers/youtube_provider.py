import asyncio
import httpx
import os
from typing import List, Optional, Dict
from models.schemas import Course
from models.batch_models import SimplifiedCourse
import logging

logger = logging.getLogger(__name__)

# Upper bounds for log-normalization of YouTube engagement signals
_MAX_VIEWS = 10_000_000
_MAX_LIKES = 200_000


class YouTubeProvider:
    """
    YouTube Data API v3 provider for educational content.
    """

    def __init__(self):
        self.api_key = os.getenv("YOUTUBE_API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3"

    async def fetch_courses(self, skill: str, max_results: int = 10, language: Optional[str] = None, preferences: Optional[List[str]] = None) -> List[SimplifiedCourse]:
        """
        Fetch educational videos from YouTube, enriched with view/like statistics.

        Args:
            skill: The skill to search for
            max_results: Maximum number of results
            language: ISO 639-1 language code (e.g., 'en', 'es', 'fr')
            preferences: Optional context keywords (e.g. ["Backend Developer", "FastAPI"])
        """
        if not self.api_key:
            logger.warning("YouTube API key not configured, skipping YouTube provider")
            return []

        query = self._build_query(skill, preferences)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Run preference-based query and institute query in parallel
                institute_query = f"{skill} lecture course MIT Stanford Harvard"
                per_query_results = min(max_results, 20)

                search_params_main = {
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": per_query_results,
                    "key": self.api_key,
                    "videoDuration": "medium",
                    "relevanceLanguage": language or "en",
                }
                search_params_institute = {**search_params_main, "q": institute_query}

                main_resp, inst_resp = await asyncio.gather(
                    client.get(f"{self.base_url}/search", params=search_params_main),
                    client.get(f"{self.base_url}/search", params=search_params_institute),
                )
                main_resp.raise_for_status()
                inst_resp.raise_for_status()

                courses = self._parse_search_response(main_resp.json())
                inst_courses = self._parse_search_response(inst_resp.json())

                # Merge, deduplicate by video ID
                seen_ids = {c.id for c in courses}
                for c in inst_courses:
                    if c.id not in seen_ids:
                        courses.append(c)
                        seen_ids.add(c.id)

                if not courses:
                    return courses

                # Batch-fetch statistics for all video IDs
                video_ids = [c.id.replace("youtube_", "") for c in courses]
                stats = await self._fetch_statistics(client, video_ids)

                for course in courses:
                    vid_id = course.id.replace("youtube_", "")
                    if vid_id in stats:
                        course.view_count = stats[vid_id].get("viewCount")
                        course.like_count = stats[vid_id].get("likeCount")

                return courses

        except httpx.HTTPError as e:
            logger.error(f"YouTube API error: {str(e)}")
            return []

    async def _fetch_statistics(self, client: httpx.AsyncClient, video_ids: List[str]) -> Dict[str, dict]:
        """
        Batch-fetch statistics (viewCount, likeCount) for a list of video IDs.
        Returns a dict keyed by video ID.
        """
        try:
            stats_resp = await client.get(
                f"{self.base_url}/videos",
                params={
                    "part": "statistics",
                    "id": ",".join(video_ids),
                    "key": self.api_key,
                },
            )
            stats_resp.raise_for_status()
            stats_data = stats_resp.json()

            result = {}
            for item in stats_data.get("items", []):
                vid_id = item["id"]
                raw = item.get("statistics", {})
                result[vid_id] = {
                    "viewCount": int(raw["viewCount"]) if raw.get("viewCount") else None,
                    "likeCount": int(raw["likeCount"]) if raw.get("likeCount") else None,
                }
            return result

        except (httpx.HTTPError, KeyError, ValueError) as e:
            logger.warning(f"Failed to fetch YouTube statistics: {e}")
            return {}

    def _build_query(self, skill: str, preferences: Optional[List[str]]) -> str:
        """
        Build a YouTube search query that incorporates preferences.
        e.g. skill="python", preferences=["Backend Developer", "FastAPI"]
             → "python FastAPI tutorial"
        We pick the most specific preference (shortest, most likely a technology)
        to avoid making the query too broad.
        """
        if not preferences:
            return f"{skill} tutorial"

        # Prefer technology/tool names over role names for query specificity
        # Heuristic: shorter tokens are usually tool names ("FastAPI" vs "Backend Developer")
        tech_prefs = sorted(preferences, key=lambda p: len(p.split()))
        top_pref = tech_prefs[0]  # most specific preference

        return f"{skill} {top_pref} tutorial"

    def _parse_search_response(self, data: dict) -> List[SimplifiedCourse]:
        """Parse YouTube search API response into SimplifiedCourse objects."""
        courses = []

        for item in data.get("items", []):
            video_id = item["id"].get("videoId")
            if not video_id:
                continue
            snippet = item["snippet"]

            course = SimplifiedCourse(
                id=f"youtube_{video_id}",
                title=snippet["title"],
                provider="YouTube",
                url=f"https://www.youtube.com/watch?v={video_id}",
                description=snippet.get("description", ""),
                tags=[t.lower() for t in snippet.get("tags", [])],
                relevance_score=0.5,
                published_at=snippet.get("publishedAt"),
                channel_id=snippet.get("channelId"),
                channel_name=snippet.get("channelTitle"),
            )
            courses.append(course)

        return courses
