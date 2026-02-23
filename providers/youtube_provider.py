import httpx
import os
from typing import List, Optional
from models.schemas import Course
from models.batch_models import SimplifiedCourse
import logging

logger = logging.getLogger(__name__)

class YouTubeProvider:
    """
    YouTube Data API v3 provider for educational content.
    """
    
    def __init__(self):
        self.api_key = os.getenv("YOUTUBE_API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3"
    
    async def fetch_courses(self, skill: str, max_results: int = 10, language: Optional[str] = None) -> List[SimplifiedCourse]:
        """
        Fetch educational videos from YouTube.
        
        Args:
            skill: The skill to search for
            max_results: Maximum number of results
            language: ISO 639-1 language code (e.g., 'en', 'es', 'fr')
        """
        if not self.api_key:
            logger.warning("YouTube API key not configured, skipping YouTube provider")
            return []
        
        query = f"{skill} tutorial"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                params = {
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": min(max_results, 25),
                    "key": self.api_key,
                    "videoDuration": "medium",  # Filter for substantial content
                }
                
                # Add language filter if provided
                if language:
                    params["relevanceLanguage"] = language
                else:
                    params["relevanceLanguage"] = "en"
                
                response = await client.get(
                    f"{self.base_url}/search",
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                
                return self._parse_response(data)
        
        except httpx.HTTPError as e:
            logger.error(f"YouTube API error: {str(e)}")
            return []
    
    def _parse_response(self, data: dict) -> List[SimplifiedCourse]:
        """
        Parse YouTube API response into SimplifiedCourse objects.
        """
        courses = []
        
        for item in data.get("items", []):
            video_id = item["id"].get("videoId")
            snippet = item["snippet"]
            
            course = SimplifiedCourse(
                id=f"youtube_{video_id}",
                title=snippet["title"],
                provider="YouTube",
                url=f"https://www.youtube.com/watch?v={video_id}",
                description=snippet["description"],
                tags=[skill.lower() for skill in snippet.get("tags", [])],
                relevance_score=0.5  # Will be adjusted by ranking engine
            )
            courses.append(course)
        
        return courses
