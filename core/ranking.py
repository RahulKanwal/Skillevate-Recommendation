from typing import List, Union
from models.schemas import Course, DifficultyLevel
from models.batch_models import SimplifiedCourse
import re
import logging

logger = logging.getLogger(__name__)

class RankingEngine:
    """
    Ranks and filters courses based on relevance, popularity, and user preferences.
    """
    
    def rank_courses(
        self, 
        courses: Union[List[Course], List[SimplifiedCourse]], 
        skill: str,
        preferences: List[str],
        difficulty: DifficultyLevel = None
    ) -> Union[List[Course], List[SimplifiedCourse]]:
        """
        Rank courses using a weighted scoring algorithm.
        
        Args:
            courses: List of Course or SimplifiedCourse objects
            skill: The skill being searched
            preferences: User preferences (career goals, learning styles, etc.)
            difficulty: Optional difficulty filter (only used with Course objects)
        
        Returns:
            Ranked list of courses (same type as input)
        """
        if not courses:
            return []
        
        # Calculate scores for each course
        for course in courses:
            course.relevance_score = self._calculate_score(course, skill, preferences)
        
        # Filter by difficulty if specified (only for Course objects with difficulty field)
        if difficulty and difficulty != DifficultyLevel.ALL:
            # Check if courses have difficulty attribute
            if hasattr(courses[0], 'difficulty'):
                courses = [c for c in courses if self._matches_difficulty(c, difficulty)]
        
        # Remove duplicates (same title from different providers)
        courses = self._deduplicate(courses)
        
        # Sort by relevance score
        courses.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return courses
    
    def _calculate_score(self, course: Union[Course, SimplifiedCourse], skill: str, preferences: List[str]) -> float:
        """
        Calculate relevance score based on multiple factors.
        All preference types (career goals, learning styles, time commitments, technologies)
        are treated equally in keyword matching.
        """
        score = 0.0
        
        # Keyword matching in title (40% weight)
        title_score = self._keyword_match_score(course.title, skill, preferences)
        score += title_score * 0.4
        
        # Keyword matching in description (30% weight)
        desc_score = self._keyword_match_score(course.description, skill, preferences)
        score += desc_score * 0.3
        
        # Popularity score (20% weight)
        # For SimplifiedCourse, rating is not available, so this contributes 0
        if hasattr(course, 'rating') and course.rating:
            popularity_score = min(course.rating / 5.0, 1.0)
            score += popularity_score * 0.2
        
        # Tag matching (10% weight)
        tag_score = self._tag_match_score(course.tags, skill, preferences)
        score += tag_score * 0.1
        
        return min(score, 1.0)
    
    def _keyword_match_score(self, text: str, skill: str, preferences: List[str]) -> float:
        """
        Calculate keyword match score for a text field.
        Enhanced to give more weight to preference matches.
        """
        if not text:
            return 0.0
        
        text_lower = text.lower()
        skill_lower = skill.lower()
        
        # Check for exact skill match
        if skill_lower in text_lower:
            score = 0.6  # Reduced from 0.8 to give more room for preferences
        else:
            # Check for partial word matches
            skill_words = skill_lower.split()
            matches = sum(1 for word in skill_words if word in text_lower)
            score = (matches / len(skill_words)) * 0.5 if skill_words else 0.0
        
        # Enhanced preference matching with higher weight
        if preferences:
            pref_matches = 0
            for pref in preferences:
                pref_lower = pref.lower()
                # Check for exact phrase match
                if pref_lower in text_lower:
                    pref_matches += 1
                else:
                    # Check for partial word matches in preference
                    pref_words = pref_lower.split()
                    if any(word in text_lower for word in pref_words):
                        pref_matches += 0.5
            
            # Preferences can add up to 0.4 to the score (increased from 0.2)
            pref_score = min((pref_matches / len(preferences)) * 0.4, 0.4)
            score += pref_score
        
        return min(score, 1.0)
    
    def _tag_match_score(self, tags: List[str], skill: str, preferences: List[str]) -> float:
        """
        Calculate tag matching score with enhanced preference matching.
        """
        if not tags:
            return 0.0
        
        tags_lower = [tag.lower() for tag in tags]
        skill_lower = skill.lower()
        
        # Check skill match in tags
        skill_match = 0.0
        if skill_lower in tags_lower:
            skill_match = 0.5
        else:
            # Check for partial skill word matches
            skill_words = skill_lower.split()
            matches = sum(1 for word in skill_words if any(word in tag for tag in tags_lower))
            skill_match = (matches / len(skill_words)) * 0.3 if skill_words else 0.0
        
        # Check preference matches in tags (higher weight)
        pref_match = 0.0
        if preferences:
            for pref in preferences:
                pref_lower = pref.lower()
                if pref_lower in tags_lower:
                    pref_match += 1
                else:
                    # Check for partial matches
                    pref_words = pref_lower.split()
                    if any(word in tag for word in pref_words for tag in tags_lower):
                        pref_match += 0.5
            
            pref_match = (pref_match / len(preferences)) * 0.5
        
        return min(skill_match + pref_match, 1.0)
    
    def _matches_difficulty(self, course: Course, difficulty: DifficultyLevel) -> bool:
        """
        Check if course matches the requested difficulty level.
        """
        if not course.difficulty:
            return True  # Include courses without difficulty info
        
        return course.difficulty.lower() == difficulty.value.lower()
    
    def _deduplicate(self, courses: Union[List[Course], List[SimplifiedCourse]]) -> Union[List[Course], List[SimplifiedCourse]]:
        """
        Remove duplicate courses based on title similarity.
        """
        seen_titles = set()
        unique_courses = []
        
        for course in courses:
            # Normalize title for comparison
            normalized_title = re.sub(r'[^\w\s]', '', course.title.lower())
            
            if normalized_title not in seen_titles:
                seen_titles.add(normalized_title)
                unique_courses.append(course)
        
        return unique_courses
