import httpx
from typing import List, Optional
from models.schemas import Course
from models.batch_models import SimplifiedCourse
import logging

logger = logging.getLogger(__name__)

class GitHubProvider:
    """
    GitHub API provider for learning repositories and tutorials.
    """
    
    def __init__(self):
        self.base_url = "https://api.github.com"
    
    async def fetch_courses(self, skill: str, max_results: int = 10, language: Optional[str] = None, preferences: Optional[List[str]] = None) -> List[SimplifiedCourse]:
        """
        Fetch educational repositories from GitHub.

        Args:
            skill: The skill to search for
            max_results: Maximum number of results
            language: ISO 639-1 language code
            preferences: Optional context keywords (e.g. ["Backend Developer", "FastAPI"])
        """
        query = self._build_query(skill, preferences)
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/search/repositories",
                    params={
                        "q": query,
                        "sort": "stars",
                        "order": "desc",
                        "per_page": min(max_results, 30)
                    },
                    headers={
                        "Accept": "application/vnd.github.v3+json",
                        "User-Agent": "Skillevate-Recommendation-System"
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                return self._parse_response(data, skill, language)
        
        except httpx.HTTPError as e:
            logger.error(f"GitHub API error: {str(e)}")
            return []
    
    def _build_query(self, skill: str, preferences: Optional[List[str]]) -> str:
        """
        Build a GitHub search query incorporating preferences.
        e.g. skill="python", preferences=["Backend Developer", "FastAPI"]
             → "python FastAPI tutorial OR python FastAPI course OR python FastAPI learning"
        """
        if not preferences:
            return f"{skill} tutorial OR {skill} course OR {skill} learning"

        tech_prefs = sorted(preferences, key=lambda p: len(p.split()))
        top_pref = tech_prefs[0]

        return (
            f"{skill} {top_pref} tutorial OR "
            f"{skill} {top_pref} course OR "
            f"{skill} {top_pref} learning"
        )

    def _parse_response(self, data: dict, skill: str, language: Optional[str] = None) -> List[SimplifiedCourse]:
        """
        Parse GitHub API response into SimplifiedCourse objects.
        
        Args:
            data: GitHub API response data
            skill: The skill being searched
            language: Optional language filter
        """
        courses = []
        
        for item in data.get("items", []):
            # Filter for educational content
            name_lower = item["name"].lower()
            desc_lower = (item.get("description") or "").lower()
            
            if not any(keyword in name_lower or keyword in desc_lower 
                      for keyword in ["tutorial", "course", "learn", "guide", "example"]):
                continue
            
            # Language filtering: skip if description contains non-Latin scripts when English is requested
            if language == "en":
                # Check for Chinese, Japanese, Korean, Arabic, Cyrillic characters
                if desc_lower and any(ord(char) > 0x3000 for char in item.get("description", "")[:200]):
                    # Skip repositories with significant non-Latin content in description
                    non_latin_count = sum(1 for char in item.get("description", "")[:200] if ord(char) > 0x3000)
                    if non_latin_count > 20:  # More than 20 non-Latin chars in first 200
                        logger.debug(f"Skipping {item['name']} - contains non-English content")
                        continue
            
            course = SimplifiedCourse(
                id=f"github_{item['id']}",
                title=item["name"],
                provider="GitHub",
                url=item["html_url"],
                description=item.get("description", "No description available"),
                tags=item.get("topics", []),
                relevance_score=0.5,  # Will be adjusted by ranking engine
                # Quality signals
                stars=item.get("stargazers_count", 0),
                forks=item.get("forks_count", 0),
                published_at=item.get("pushed_at"),  # last active date
                # Authority signal
                org_login=item.get("owner", {}).get("login"),
            )
            courses.append(course)
        
        return courses
