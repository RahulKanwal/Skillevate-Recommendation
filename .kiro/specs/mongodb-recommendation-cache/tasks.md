# Implementation Plan: mongodb-recommendation-cache

## Overview

Add a MongoDB-backed recommendation caching layer to the Skillevate Recommendation API. The implementation introduces three new modules (`db/mongodb.py`, `models/user_recommendation_models.py`, `api/user_recommendations.py`), modifies `main.py` and `requirements.txt`, and adds property-based and integration tests using Hypothesis and FastAPI's `TestClient`.

All new code is async-first, using Motor (`motor[asyncio]`) to avoid blocking the FastAPI event loop.

## Tasks

- [x] 1. Add dependencies to requirements.txt
  - Add `motor[asyncio]>=3.3.0` for the async MongoDB driver
  - Add `pymongo>=4.6.0` for ObjectId utilities used by Motor
  - Add `hypothesis>=6.100.0` for property-based tests
  - _Requirements: 1.1_

- [x] 2. Create `db/mongodb.py` — Motor client lifecycle and database accessor
  - Create `db/__init__.py` (empty) to make `db` a package
  - Implement module-level `_client: AsyncIOMotorClient | None = None`
  - Implement `connect_to_mongo()`: reads `MONGODB_URI` from env, raises `RuntimeError` if absent/empty, initialises `_client`
  - Implement `close_mongo_connection()`: closes `_client` gracefully if set
  - Implement `get_database()`: returns the `skillevate_user` database handle; raises `RuntimeError` if called before `connect_to_mongo()`
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 3. Create `models/user_recommendation_models.py` — Pydantic models
  - Implement `Recommendation` with fields: `recommendation_id` (str), `title` (str), `provider` (str), `url` (str), `description` (str), `tags` (List[str], default `[]`), `relevance_score` (float, `ge=0.0, le=1.0`), `status` (str), `xp_value` (int, `ge=0, le=100`), `linked_gap` (str)
  - Implement `AnalysisDocument` with fields: `id` (str, alias `_id`), `user_id` (str), `is_latest` (bool), `gaps` (List[str], default `[]`), `recommendations` (List[Recommendation], default `[]`); use `model_config = ConfigDict(populate_by_name=True)`
  - Implement `UserRecommendationRequest` with `user_id` (str, `pattern=r"^[0-9a-fA-F]{24}$"`) and optional `analysis_id` (str, same pattern, default `None`)
  - Implement `UserRecommendationResponse` with `analysis_id` (str), `user_id` (str), `gaps` (List[str]), `recommendations` (List[Recommendation]), `cached` (bool)
  - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3_

- [x] 4. Create `api/user_recommendations.py` — cache orchestration logic
  - Implement `_fetch_active_analysis(db, user_id, analysis_id)`: queries `Analyses` collection with `user_id=ObjectId(user_id)` and `is_latest=True`; adds `_id` filter when `analysis_id` is provided; returns raw document dict or `None`
  - Implement `_map_courses_to_recommendations(skill_results)`: iterates `SkillRecommendationResult` objects, maps each `SimplifiedCourse` to a `Recommendation` with `status="recommended"`, `xp_value=round(relevance_score * 100)`, `linked_gap=skill`
  - Implement `_write_back_recommendations(db, analysis_id, recommendations)`: performs atomic `$set` on `results.recommendations` via `update_one`; wraps in `try/except`, logs error and returns normally on failure
  - Implement `get_user_recommendations(request)`: orchestrates fetch → cache-hit check → batch engine call → mapping → write-back → return; raises `HTTPException(404)` when no active analysis found; raises `HTTPException(502)` when batch engine raises; wraps entire handler in `try/except` for `HTTPException(500)`
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.3_

  - [ ]* 4.1 Write unit tests for `_map_courses_to_recommendations`
    - Test that output length equals total input courses across all skill results
    - Test `status="recommended"` on every output object
    - Test `xp_value == round(relevance_score * 100)` for boundary values (0.0, 0.5, 1.0)
    - Test `linked_gap` equals the gap string that produced the course
    - _Requirements: 5.1, 5.2_

- [x] 5. Checkpoint — verify models and core logic compile cleanly
  - Ensure all imports resolve and `python -m py_compile` passes on `db/mongodb.py`, `models/user_recommendation_models.py`, and `api/user_recommendations.py`
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Modify `main.py` — lifespan, CORS, and new endpoint registration
  - Add `from contextlib import asynccontextmanager` and `import os`
  - Import `connect_to_mongo`, `close_mongo_connection` from `db.mongodb`
  - Import `get_user_recommendations` from `api.user_recommendations`
  - Import `UserRecommendationRequest`, `UserRecommendationResponse` from `models.user_recommendation_models`
  - Replace the current `app = FastAPI(...)` with a `lifespan` context manager that calls `connect_to_mongo()` on startup and `close_mongo_connection()` on shutdown; pass `lifespan=lifespan` to `FastAPI(...)`
  - Replace the hardcoded `allow_origins=["*"]` with CORS origin parsing: read `CORS_ORIGINS` env var, split on commas, strip whitespace, fall back to `["*"]` when empty
  - Register `POST /api/user-recommendations` route with `response_model=UserRecommendationResponse`, summary, and description visible in OpenAPI
  - _Requirements: 1.1, 1.2, 6.1, 6.2, 6.4, 7.1, 7.2, 7.3, 7.4_

- [x] 7. Update `.env.example` with new environment variables
  - Add `MONGODB_URI=mongodb://localhost:27017` with a comment explaining the variable
  - Add `MONGODB_DATABASE=skillevate_user` with a comment
  - Add `CORS_ORIGINS=http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003` with a comment
  - Add `APP_NAME=Skillevate Recommendation API` with a comment
  - Add `APP_ENV=development` with a comment
  - _Requirements: 1.1, 7.1, 7.4_

- [ ] 8. Write property-based tests using Hypothesis
  - Create `tests/__init__.py` (empty) and `tests/test_properties.py`
  - Each test tagged with `# Feature: mongodb-recommendation-cache, Property N: <property_text>`

  - [ ]* 8.1 Write property test for ObjectId validation (Property 1)
    - Use `hypothesis.strategies` to generate arbitrary strings; assert valid 24-hex strings pass `UserRecommendationRequest` construction and all others raise `ValidationError`
    - **Property 1: ObjectId validation rejects invalid inputs**
    - **Validates: Requirements 3.1, 3.2**

  - [ ]* 8.2 Write property test for xp_value derivation (Property 2)
    - Generate floats in `[0.0, 1.0]` via `st.floats(min_value=0.0, max_value=1.0)`; assert `xp_value == round(score * 100)` and `0 <= xp_value <= 100`
    - **Property 2: xp_value derivation is correct and bounded**
    - **Validates: Requirements 5.2**

  - [ ]* 8.3 Write property test for recommendation mapping completeness (Property 3)
    - Generate lists of `SimplifiedCourse` objects with gap labels; call `_map_courses_to_recommendations`; assert output length equals total input courses, every item has `status="recommended"`, `xp_value=round(relevance_score * 100)`, and `linked_gap` matches the source gap
    - **Property 3: Recommendation mapping is complete and correct**
    - **Validates: Requirements 5.1, 5.2**

  - [ ]* 8.4 Write property test for cache-hit path (Property 4)
    - Generate non-empty `Recommendation` lists; mock `_fetch_active_analysis` to return a document with those recommendations; assert response has `cached=True` and batch engine is never called
    - **Property 4: Cache-hit returns stored recommendations unchanged**
    - **Validates: Requirements 4.4**

  - [ ]* 8.5 Write property test for cache-miss with non-empty gaps (Property 5)
    - Generate non-empty gap lists; mock `_fetch_active_analysis` to return a document with empty recommendations and those gaps; mock batch engine; assert batch engine called with exactly one `SkillRequest` per gap and response has `cached=False`
    - **Property 5: Cache-miss with non-empty gaps triggers generation**
    - **Validates: Requirements 4.5, 5.1**

  - [ ]* 8.6 Write property test for Recommendation round-trip serialisation (Property 6)
    - Generate valid `Recommendation` objects; assert `Recommendation(**rec.model_dump()) == rec`
    - **Property 6: Recommendation round-trip serialisation preserves data**
    - **Validates: Requirements 2.1**

  - [ ]* 8.7 Write property test for write-back failure resilience (Property 7)
    - Generate recommendation lists; mock `_write_back_recommendations` to raise an exception; assert the endpoint still returns HTTP 200 with the full recommendations list and `cached=False`
    - **Property 7: Write-back failure does not block the user**
    - **Validates: Requirements 5.5**

  - [ ]* 8.8 Write property test for CORS origin parsing (Property 8)
    - Generate lists of URL strings; join with commas; set as `CORS_ORIGINS` env var; assert parsed origins list matches the input exactly (trimmed, non-empty, no duplicates introduced)
    - **Property 8: CORS origin parsing is correct**
    - **Validates: Requirements 7.1, 7.2**

- [ ] 9. Write integration tests for all HTTP paths
  - Create `tests/test_user_recommendations_integration.py`
  - Use FastAPI `TestClient` with `mongomock` (or `unittest.mock.AsyncMock`) to avoid requiring a live MongoDB instance

  - [ ]* 9.1 Write integration test for cache-hit path
    - Pre-populate mock `Analyses` with a document containing non-empty `recommendations`; POST to `/api/user-recommendations`; assert HTTP 200, `cached=True`, and recommendations match stored data
    - _Requirements: 4.4_

  - [ ]* 9.2 Write integration test for cache-miss path
    - Pre-populate mock `Analyses` with empty `recommendations` and non-empty `gaps`; mock batch engine; POST to `/api/user-recommendations`; assert HTTP 200, `cached=False`, and write-back was called
    - _Requirements: 4.5, 5.3, 5.4_

  - [ ]* 9.3 Write integration test for 404 path
    - POST with an unknown `user_id`; assert HTTP 404 with message `"No active analysis found for this user"`
    - _Requirements: 4.3_

  - [ ]* 9.4 Write integration test for 502 path
    - Mock batch engine to raise an exception; POST with a valid `user_id` that has empty recommendations and non-empty gaps; assert HTTP 502 with message `"Recommendation engine unavailable"`
    - _Requirements: 5.6_

  - [ ]* 9.5 Write integration test for write-back failure resilience
    - Mock `update_one` to raise; POST with a valid cache-miss scenario; assert HTTP 200 is still returned with the full recommendations list
    - _Requirements: 5.5_

- [x] 10. Final checkpoint — ensure all tests pass
  - Run `pytest tests/ -v` and confirm all non-optional tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- The `results` sub-document nesting in MongoDB (`doc["results"]["gaps"]`, `doc["results"]["recommendations"]`) must be respected in `_fetch_active_analysis` and `_write_back_recommendations`
- Property tests use Hypothesis with a minimum of 100 iterations per property (`@settings(max_examples=100)`)
- Integration tests use `unittest.mock.AsyncMock` / `mongomock` to avoid requiring a live MongoDB instance
- The `lifespan` context manager replaces the deprecated `on_event` pattern; `connect_to_mongo` raises `RuntimeError` before `yield` if `MONGODB_URI` is missing, preventing the app from starting
