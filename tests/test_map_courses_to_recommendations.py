"""
Unit tests for _map_courses_to_recommendations in api/user_recommendations.py.

Covers:
- Output length equals total input courses across all skill results
- status="recommended" on every output object
- xp_value == round(relevance_score * 100) for boundary values (0.0, 0.5, 1.0)
- linked_gap equals the gap string that produced the course
"""

import pytest
from models.batch_models import SimplifiedCourse, SkillRecommendationResult
from api.user_recommendations import _map_courses_to_recommendations


def make_course(
    course_id: str = "course-1",
    title: str = "Test Course",
    provider: str = "YouTube",
    url: str = "https://example.com",
    description: str = "A test course",
    tags: list = None,
    relevance_score: float = 0.5,
) -> SimplifiedCourse:
    return SimplifiedCourse(
        id=course_id,
        title=title,
        provider=provider,
        url=url,
        description=description,
        tags=tags or [],
        relevance_score=relevance_score,
    )


def make_skill_result(skill: str, courses: list) -> SkillRecommendationResult:
    return SkillRecommendationResult(
        skill=skill,
        total_results=len(courses),
        recommendations=courses,
    )


# ---------------------------------------------------------------------------
# Output length tests
# ---------------------------------------------------------------------------

class TestOutputLength:
    def test_empty_skill_results_returns_empty_list(self):
        result = _map_courses_to_recommendations([])
        assert result == []

    def test_single_skill_single_course(self):
        skill_results = [make_skill_result("Python", [make_course()])]
        result = _map_courses_to_recommendations(skill_results)
        assert len(result) == 1

    def test_single_skill_multiple_courses(self):
        courses = [make_course(f"c{i}") for i in range(5)]
        skill_results = [make_skill_result("Docker", courses)]
        result = _map_courses_to_recommendations(skill_results)
        assert len(result) == 5

    def test_multiple_skills_total_count(self):
        skill_results = [
            make_skill_result("Python", [make_course("c1"), make_course("c2")]),
            make_skill_result("Docker", [make_course("c3")]),
            make_skill_result("Kubernetes", [make_course("c4"), make_course("c5"), make_course("c6")]),
        ]
        result = _map_courses_to_recommendations(skill_results)
        assert len(result) == 6

    def test_skill_with_no_courses_contributes_zero(self):
        skill_results = [
            make_skill_result("Python", [make_course("c1")]),
            make_skill_result("Empty Skill", []),
            make_skill_result("Docker", [make_course("c2")]),
        ]
        result = _map_courses_to_recommendations(skill_results)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# status field tests
# ---------------------------------------------------------------------------

class TestStatusField:
    def test_status_is_recommended_for_single_course(self):
        skill_results = [make_skill_result("Python", [make_course()])]
        result = _map_courses_to_recommendations(skill_results)
        assert result[0].status == "recommended"

    def test_status_is_recommended_for_all_courses(self):
        courses = [make_course(f"c{i}", relevance_score=i * 0.1) for i in range(1, 6)]
        skill_results = [make_skill_result("Python", courses)]
        result = _map_courses_to_recommendations(skill_results)
        assert all(r.status == "recommended" for r in result)

    def test_status_is_recommended_across_multiple_skills(self):
        skill_results = [
            make_skill_result("Python", [make_course("c1"), make_course("c2")]),
            make_skill_result("Docker", [make_course("c3")]),
        ]
        result = _map_courses_to_recommendations(skill_results)
        assert all(r.status == "recommended" for r in result)


# ---------------------------------------------------------------------------
# xp_value derivation tests (boundary values)
# ---------------------------------------------------------------------------

class TestXpValueDerivation:
    def test_xp_value_at_zero(self):
        course = make_course(relevance_score=0.0)
        skill_results = [make_skill_result("Python", [course])]
        result = _map_courses_to_recommendations(skill_results)
        assert result[0].xp_value == 0

    def test_xp_value_at_half(self):
        course = make_course(relevance_score=0.5)
        skill_results = [make_skill_result("Python", [course])]
        result = _map_courses_to_recommendations(skill_results)
        assert result[0].xp_value == 50

    def test_xp_value_at_one(self):
        course = make_course(relevance_score=1.0)
        skill_results = [make_skill_result("Python", [course])]
        result = _map_courses_to_recommendations(skill_results)
        assert result[0].xp_value == 100

    def test_xp_value_rounds_correctly(self):
        # round(0.875 * 100) = round(87.5) = 88 (Python banker's rounding)
        course = make_course(relevance_score=0.875)
        skill_results = [make_skill_result("Python", [course])]
        result = _map_courses_to_recommendations(skill_results)
        assert result[0].xp_value == round(0.875 * 100)

    def test_xp_value_matches_formula_for_various_scores(self):
        scores = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
        courses = [make_course(f"c{i}", relevance_score=s) for i, s in enumerate(scores)]
        skill_results = [make_skill_result("Python", courses)]
        result = _map_courses_to_recommendations(skill_results)
        for rec, score in zip(result, scores):
            assert rec.xp_value == round(score * 100)


# ---------------------------------------------------------------------------
# linked_gap tests
# ---------------------------------------------------------------------------

class TestLinkedGap:
    def test_linked_gap_matches_skill_string(self):
        skill_results = [make_skill_result("Python async programming", [make_course()])]
        result = _map_courses_to_recommendations(skill_results)
        assert result[0].linked_gap == "Python async programming"

    def test_linked_gap_correct_for_multiple_skills(self):
        skill_results = [
            make_skill_result("Python", [make_course("c1"), make_course("c2")]),
            make_skill_result("Docker", [make_course("c3")]),
        ]
        result = _map_courses_to_recommendations(skill_results)
        assert result[0].linked_gap == "Python"
        assert result[1].linked_gap == "Python"
        assert result[2].linked_gap == "Docker"

    def test_linked_gap_preserves_exact_gap_string(self):
        gap = "Docker containerisation & orchestration"
        skill_results = [make_skill_result(gap, [make_course()])]
        result = _map_courses_to_recommendations(skill_results)
        assert result[0].linked_gap == gap


# ---------------------------------------------------------------------------
# recommendation_id field tests
# ---------------------------------------------------------------------------

class TestRecommendationId:
    def test_recommendation_id_matches_course_id(self):
        course = make_course(course_id="yt-abc123")
        skill_results = [make_skill_result("Python", [course])]
        result = _map_courses_to_recommendations(skill_results)
        assert result[0].recommendation_id == "yt-abc123"

    def test_recommendation_id_preserved_across_multiple_courses(self):
        courses = [make_course(f"id-{i}") for i in range(3)]
        skill_results = [make_skill_result("Python", courses)]
        result = _map_courses_to_recommendations(skill_results)
        for i, rec in enumerate(result):
            assert rec.recommendation_id == f"id-{i}"


# ---------------------------------------------------------------------------
# Field passthrough tests
# ---------------------------------------------------------------------------

class TestFieldPassthrough:
    def test_title_is_preserved(self):
        course = make_course(title="Advanced Python Async")
        skill_results = [make_skill_result("Python", [course])]
        result = _map_courses_to_recommendations(skill_results)
        assert result[0].title == "Advanced Python Async"

    def test_provider_is_preserved(self):
        course = make_course(provider="GitHub")
        skill_results = [make_skill_result("Python", [course])]
        result = _map_courses_to_recommendations(skill_results)
        assert result[0].provider == "GitHub"

    def test_url_is_preserved(self):
        course = make_course(url="https://github.com/example/repo")
        skill_results = [make_skill_result("Python", [course])]
        result = _map_courses_to_recommendations(skill_results)
        assert result[0].url == "https://github.com/example/repo"

    def test_tags_are_preserved(self):
        course = make_course(tags=["python", "async", "asyncio"])
        skill_results = [make_skill_result("Python", [course])]
        result = _map_courses_to_recommendations(skill_results)
        assert result[0].tags == ["python", "async", "asyncio"]

    def test_relevance_score_is_preserved(self):
        course = make_course(relevance_score=0.87)
        skill_results = [make_skill_result("Python", [course])]
        result = _map_courses_to_recommendations(skill_results)
        assert result[0].relevance_score == 0.87
