import httpx
from typing import List, Optional
from models.schemas import Course
from models.batch_models import SimplifiedCourse
from core.skill_taxonomy import get_search_query_terms
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
        Build a GitHub search query. Preferences take priority over taxonomy expansion.
        """
        parts = [skill]

        if preferences:
            tech_prefs = [p for p in preferences if len(p.split()) <= 2]
            tech_prefs.sort(key=lambda p: len(p.split()))
            parts.extend(tech_prefs[:1])  # one preference for GitHub to keep query tight
        else:
            terms = get_search_query_terms(skill, None)
            if len(terms) > 1:
                parts.append(terms[1])

        base = " ".join(parts)
        return f"{base} tutorial OR {base} course OR {base} learning"

    def _parse_response(self, data: dict, skill: str, language: Optional[str] = None) -> List[SimplifiedCourse]:
        """Parse GitHub API response into SimplifiedCourse objects."""
        import re as _re
        courses = []

        for item in data.get("items", []):
            name_lower = item["name"].lower()
            desc_lower = (item.get("description") or "").lower()

            # Language filter — must come first to avoid processing non-English repos
            if language == "en":
                name_and_desc = f"{item['name']} {item.get('description', '')}"
                non_latin = sum(1 for c in name_and_desc[:300] if ord(c) > 0x024F)
                if non_latin > 3:
                    continue

            # Minimum star threshold
            if item.get("stargazers_count", 0) < 10:
                continue

            # Educational keyword must appear in the repo NAME (not just description)
            # This prevents app repos that mention "learning" in their description
            edu_in_name = any(k in name_lower for k in [
                "tutorial", "course", "learn", "guide", "awesome",
                "roadmap", "cheatsheet", "example", "notes", "resources"
            ])

            # If not in name, check description but require stronger signal
            if not edu_in_name:
                edu_in_desc = any(k in desc_lower for k in [
                    "tutorial", "course", "guide", "awesome",
                    "roadmap", "cheatsheet", "resources"
                ])
                # "learn" in description only counts if it's a standalone word
                learn_standalone = bool(_re.search(r'\blearn\b', desc_lower))
                if not edu_in_desc and not learn_standalone:
                    continue

                # Extra check: if only educational signal is in description,
                # make sure it's not an app repo using the skill
                app_signals = ["app", "system", "scanner", "detector", "tracker",
                               "manager", "dashboard", "service", "platform", "tool"]
                if any(k in name_lower for k in app_signals):
                    continue

            course = SimplifiedCourse(
                id=f"github_{item['id']}",
                title=item["name"],
                provider="GitHub",
                url=item["html_url"],
                description=item.get("description", "No description available"),
                tags=item.get("topics", []),
                relevance_score=0.5,
                stars=item.get("stargazers_count", 0),
                forks=item.get("forks_count", 0),
                published_at=item.get("pushed_at"),
                org_login=item.get("owner", {}).get("login"),
            )
            courses.append(course)

        return courses
