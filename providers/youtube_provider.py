import asyncio
import httpx
import os
from typing import List, Optional, Dict
from models.batch_models import SimplifiedCourse
from core.skill_taxonomy import get_search_query_terms
import logging

logger = logging.getLogger(__name__)

class YouTubeProvider:
    """
    YouTube Data API v3 — educational videos and playlists, with enriched metadata.
    """

    def __init__(self):
        self.api_key = os.getenv("YOUTUBE_API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3"

    async def fetch_courses(
        self,
        skill: str,
        max_results: int = 10,
        language: Optional[str] = None,
        preferences: Optional[List[str]] = None,
    ) -> List[SimplifiedCourse]:
        """
        Fetch videos and playlists, enrich with tags (videos) and item counts (playlists).
        """
        if not self.api_key:
            logger.warning("YouTube API key not configured, skipping YouTube provider")
            return []

        query = self._build_query(skill, preferences)
        playlist_query = self._build_playlist_query(skill, preferences)
        cfg = self._youtube_search_prefs(preferences)
        per = min(max(15, max_results * 2), 25)

        base_common = {
            "part": "snippet",
            "key": self.api_key,
            "relevanceLanguage": language or "en",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                tasks = [
                    self._search(
                        client,
                        {**base_common, "q": query, "type": "video", "maxResults": per, **cfg["video_params"]},
                    ),
                    self._search(
                        client,
                        {**base_common, "q": playlist_query, "type": "playlist", "maxResults": min(per, 18)},
                    ),
                ]
                if cfg["extra_long_video"]:
                    tasks.append(
                        self._search(
                            client,
                            {
                                **base_common,
                                "q": query,
                                "type": "video",
                                "maxResults": min(per, 15),
                                "videoDuration": "long",
                            },
                        )
                    )

                raw_results = await asyncio.gather(*tasks)
                courses: List[SimplifiedCourse] = []
                seen: set = set()

                for data in raw_results:
                    for c in self._parse_search_response(data):
                        if c.id in seen:
                            continue
                        seen.add(c.id)
                        courses.append(c)

                courses = [
                    c
                    for c in courses
                    if self._item_matches_skill(skill, preferences, c.title, c.description)
                ]

                if not courses:
                    return []

                await self._enrich_items(client, courses)

                return courses

        except httpx.HTTPError as e:
            logger.error(f"YouTube API error: {str(e)}")
            return []

    async def _search(self, client: httpx.AsyncClient, params: dict) -> dict:
        resp = await client.get(f"{self.base_url}/search", params=params)
        resp.raise_for_status()
        return resp.json()

    def _youtube_search_prefs(self, preferences: Optional[List[str]]) -> dict:
        """
        Map preferences to video search parameters.
        Users can pass e.g. 'quick tutorials', 'comprehensive courses', 'beginner', 'senior'.
        """
        pl = " ".join(preferences or []).lower()
        wants_quick = any(
            k in pl
            for k in [
                "quick tutorial",
                "quick tutorials",
                "short video",
                "short videos",
                "crash course",
                "in a hurry",
            ]
        )
        wants_long = any(
            k in pl
            for k in [
                "comprehensive",
                "full course",
                "complete course",
                "course series",
                "in-depth",
                "in depth",
                "deep dive",
                "long form",
            ]
        )
        extra_long = wants_long and not wants_quick

        if wants_quick and not wants_long:
            duration = "short"
        elif wants_long and not wants_quick:
            duration = "long"
        else:
            duration = "medium"

        return {
            "video_params": {"videoDuration": duration},
            "extra_long_video": extra_long,
        }

    def _build_playlist_query(self, skill: str, preferences: Optional[List[str]]) -> str:
        """Playlists: favor course/series phrasing over single-video 'tutorial'."""
        q = self._build_query(skill, preferences)
        if q.endswith(" tutorial"):
            return q[: -len(" tutorial")] + " full course tutorial playlist"
        return f"{q} playlist course"

    def _item_matches_skill(
        self, skill: str, preferences: Optional[List[str]], title: str, description: str
    ) -> bool:
        """Drop off-topic hits (e.g. prestigious channels unrelated to the skill)."""
        text = f"{title} {description}".lower()
        skill_l = skill.lower().strip()
        if skill_l and skill_l in text:
            return True
        for term in get_search_query_terms(skill, preferences):
            if len(term) >= 3 and term.lower() in text:
                return True
        for w in skill_l.split():
            if len(w) >= 4 and w in text:
                return True
        return False

    async def _enrich_items(self, client: httpx.AsyncClient, courses: List[SimplifiedCourse]) -> None:
        video_courses = [c for c in courses if not c.id.startswith("youtube_pl_")]
        playlist_courses = [c for c in courses if c.id.startswith("youtube_pl_")]

        vid_map = {c.id.replace("youtube_", "", 1): c for c in video_courses}

        for i in range(0, len(video_courses), 50):
            chunk = [c.id.replace("youtube_", "", 1) for c in video_courses[i : i + 50]]
            if not chunk:
                continue
            merged = await self._fetch_video_details(client, chunk)
            for vid_id, data in merged.items():
                c = vid_map.get(vid_id)
                if not c:
                    continue
                sn = data.get("snippet") or {}
                st = data.get("statistics") or {}
                tags = [t.lower() for t in sn.get("tags") or []]
                if tags:
                    c.tags = tags
                desc = sn.get("description") or c.description
                if len(desc) > len(c.description or ""):
                    c.description = desc
                if st.get("viewCount"):
                    c.view_count = int(st["viewCount"])
                if st.get("likeCount"):
                    c.like_count = int(st["likeCount"])
                c._yt_internal["kind"] = "video"

        pl_ids = [c.id.replace("youtube_pl_", "", 1) for c in playlist_courses]
        for i in range(0, len(pl_ids), 50):
            chunk = pl_ids[i : i + 50]
            details = await self._fetch_playlist_details(client, chunk)
            for c in playlist_courses:
                pid = c.id.replace("youtube_pl_", "", 1)
                if pid not in details:
                    continue
                d = details[pid]
                sn = d.get("snippet") or {}
                cd = d.get("contentDetails") or {}
                desc = sn.get("description") or c.description
                if len(desc) > len(c.description or ""):
                    c.description = desc
                item_count = int(cd.get("itemCount") or 0)
                c._yt_internal["kind"] = "playlist"
                c._yt_internal["item_count"] = item_count

    async def _fetch_video_details(
        self, client: httpx.AsyncClient, video_ids: List[str]
    ) -> Dict[str, dict]:
        if not video_ids:
            return {}
        try:
            resp = await client.get(
                f"{self.base_url}/videos",
                params={
                    "part": "snippet,statistics",
                    "id": ",".join(video_ids),
                    "key": self.api_key,
                },
            )
            resp.raise_for_status()
            out = {}
            for item in resp.json().get("items", []):
                out[item["id"]] = {
                    "snippet": item.get("snippet", {}),
                    "statistics": item.get("statistics", {}),
                }
            return out
        except (httpx.HTTPError, KeyError, ValueError) as e:
            logger.warning(f"Failed to fetch YouTube video details: {e}")
            return {}

    async def _fetch_playlist_details(
        self, client: httpx.AsyncClient, playlist_ids: List[str]
    ) -> Dict[str, dict]:
        if not playlist_ids:
            return {}
        try:
            resp = await client.get(
                f"{self.base_url}/playlists",
                params={
                    "part": "snippet,contentDetails",
                    "id": ",".join(playlist_ids),
                    "key": self.api_key,
                },
            )
            resp.raise_for_status()
            out = {}
            for item in resp.json().get("items", []):
                out[item["id"]] = {
                    "snippet": item.get("snippet", {}),
                    "contentDetails": item.get("contentDetails", {}),
                }
            return out
        except (httpx.HTTPError, KeyError, ValueError) as e:
            logger.warning(f"Failed to fetch YouTube playlist details: {e}")
            return {}

    def _build_query(self, skill: str, preferences: Optional[List[str]]) -> str:
        parts = [skill]

        if preferences:
            tech_prefs = [p for p in preferences if len(p.split()) <= 2]
            tech_prefs.sort(key=lambda p: len(p.split()))
            parts.extend(tech_prefs[:2])
        else:
            terms = get_search_query_terms(skill, None)
            if len(terms) > 1:
                parts.append(terms[1])

        parts.append("tutorial")
        return " ".join(parts)

    def _parse_search_response(self, data: dict) -> List[SimplifiedCourse]:
        courses = []
        for item in data.get("items", []):
            id_obj = item.get("id") or {}
            snippet = item.get("snippet") or {}

            video_id = id_obj.get("videoId")
            playlist_id = id_obj.get("playlistId")

            if video_id:
                course = SimplifiedCourse(
                    id=f"youtube_{video_id}",
                    title=snippet.get("title", ""),
                    provider="YouTube",
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    description=snippet.get("description", ""),
                    tags=[],
                    relevance_score=0.5,
                    published_at=snippet.get("publishedAt"),
                    channel_id=snippet.get("channelId"),
                    channel_name=snippet.get("channelTitle"),
                )
                course._yt_internal["kind"] = "video"
                courses.append(course)

            elif playlist_id:
                course = SimplifiedCourse(
                    id=f"youtube_pl_{playlist_id}",
                    title=snippet.get("title", ""),
                    provider="YouTube",
                    url=f"https://www.youtube.com/playlist?list={playlist_id}",
                    description=snippet.get("description", ""),
                    tags=[],
                    relevance_score=0.52,
                    published_at=snippet.get("publishedAt"),
                    channel_id=snippet.get("channelId"),
                    channel_name=snippet.get("channelTitle"),
                )
                course._yt_internal["kind"] = "playlist"
                courses.append(course)

        return courses
