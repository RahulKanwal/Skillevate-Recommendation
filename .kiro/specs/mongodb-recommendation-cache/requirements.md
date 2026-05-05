# Requirements Document

## Introduction

This feature adds a MongoDB-backed recommendation caching layer to the Skillevate Recommendation API. When a user's analysis is ready (gaps identified, recommendations empty), the new `POST /api/user-recommendations` endpoint checks MongoDB for existing cached recommendations and returns them immediately if present. If no cache exists, it calls the internal batch-recommendations engine, stores the results back into the `Analyses` collection, and returns them to the caller. Cache invalidation is handled automatically by the teammate's upstream workflow: when a new resume/JD is uploaded, the old analysis is marked `is_latest: false` and a new one is created with `recommendations: []`, which causes the cache-miss path to run on the next request.

---

## Glossary

- **Cache_Layer**: The new endpoint and supporting modules that implement the check-then-generate-then-store flow.
- **Analyses**: The MongoDB collection storing per-user analysis documents, including gap lists and recommendation arrays.
- **Users**: The MongoDB collection storing user identity documents keyed by `auth0_id`.
- **Recommendation**: A single learning resource object stored inside `Analyses.recommendations[]`, containing fields `recommendation_id`, `title`, `provider`, `url`, `description`, `tags`, `relevance_score`, `status`, `xp_value`, and `linked_gap`.
- **Active_Analysis**: The `Analyses` document for a given user where `is_latest = true`.
- **Cache_Hit**: The condition where the Active_Analysis document exists and its `recommendations` array is non-empty.
- **Cache_Miss**: The condition where the Active_Analysis document exists and its `recommendations` array is empty.
- **Batch_Engine**: The existing internal `get_batch_recommendations` function in `api/batch_recommendations.py`.
- **MongoDB_Client**: The async Motor client used to connect to the `skillevate_user` database via `MONGODB_URI`.

---

## Requirements

### Requirement 1: MongoDB Connection Layer

**User Story:** As a backend developer, I want a dedicated MongoDB connection module, so that all database interactions use a single managed async client without opening redundant connections.

#### Acceptance Criteria

1. THE `MongoDB_Client` SHALL be initialised once at application startup using the `MONGODB_URI` environment variable.
2. THE `MongoDB_Client` SHALL be closed gracefully at application shutdown.
3. WHEN `MONGODB_URI` is not set or is empty at startup, THE `Cache_Layer` SHALL raise a `RuntimeError` with a descriptive message before the application accepts requests.
4. THE `MongoDB_Client` SHALL expose the `skillevate_user` database as a module-level accessor so all other modules can import it without re-reading environment variables.

---

### Requirement 2: Analyses Collection Schema Extension

**User Story:** As a backend developer, I want the `Analyses` document schema to include a typed `recommendations` array, so that stored recommendations are validated and consistently structured.

#### Acceptance Criteria

1. THE `Cache_Layer` SHALL define a `Recommendation` Pydantic model with fields: `recommendation_id` (str), `title` (str), `provider` (str), `url` (str), `description` (str), `tags` (list of str), `relevance_score` (float, 0.0–1.0), `status` (str), `xp_value` (int), and `linked_gap` (str).
2. THE `Cache_Layer` SHALL define an `AnalysisDocument` Pydantic model that includes `_id` (ObjectId), `user_id` (ObjectId), `results` containing `gaps` (list of str), `recommendations` (list of `Recommendation`), and `is_latest` (bool).
3. WHEN a `Recommendation` object is constructed with a `relevance_score` outside the range 0.0–1.0, THE `Cache_Layer` SHALL raise a `ValidationError`.

---

### Requirement 3: Request and Response Models

**User Story:** As a frontend developer, I want clearly defined request and response schemas for the new endpoint, so that I can integrate without ambiguity.

#### Acceptance Criteria

1. THE `Cache_Layer` SHALL define a `UserRecommendationRequest` Pydantic model with a required field `user_id` (str, valid 24-hex MongoDB ObjectId) and an optional field `analysis_id` (str, valid 24-hex MongoDB ObjectId, default `None`).
2. WHEN `user_id` is not a valid 24-character hexadecimal string, THE `Cache_Layer` SHALL return HTTP 422 with a descriptive validation error.
3. THE `Cache_Layer` SHALL define a `UserRecommendationResponse` Pydantic model containing `analysis_id` (str), `user_id` (str), `gaps` (list of str), `recommendations` (list of `Recommendation`), and `cached` (bool indicating whether the result was served from cache).

---

### Requirement 4: Cache-Check Logic

**User Story:** As a user, I want my previously generated recommendations returned instantly on repeat requests, so that I do not wait for redundant API calls to external providers.

#### Acceptance Criteria

1. WHEN a request is received with a valid `user_id`, THE `Cache_Layer` SHALL query the `Analyses` collection for a document matching `user_id = ObjectId(user_id)` AND `is_latest = true`.
2. WHEN `analysis_id` is provided in the request, THE `Cache_Layer` SHALL additionally filter by `_id = ObjectId(analysis_id)`.
3. WHEN no Active_Analysis document is found for the given `user_id`, THE `Cache_Layer` SHALL return HTTP 404 with the message `"No active analysis found for this user"`.
4. WHEN a Cache_Hit is detected, THE `Cache_Layer` SHALL return the stored `recommendations` array with `cached = true` without calling the `Batch_Engine`.
5. WHEN a Cache_Miss is detected and `gaps` is non-empty, THE `Cache_Layer` SHALL call the `Batch_Engine` and proceed to Requirement 5.
6. WHEN a Cache_Miss is detected and `gaps` is empty, THE `Cache_Layer` SHALL return an empty `recommendations` array with `cached = false` without calling the `Batch_Engine`.

---

### Requirement 5: Recommendation Generation and Write-Back

**User Story:** As a user, I want freshly generated recommendations stored so that subsequent requests are served from cache.

#### Acceptance Criteria

1. WHEN the `Batch_Engine` is called, THE `Cache_Layer` SHALL construct one `SkillRequest` per gap string from the Active_Analysis `gaps` array, using default preferences.
2. WHEN the `Batch_Engine` returns results, THE `Cache_Layer` SHALL map each `SimplifiedCourse` to a `Recommendation` object, setting `status = "recommended"`, `xp_value = round(relevance_score * 100)` (range 0–100, derived from the course's `relevance_score`), and `linked_gap` to the gap string that produced the course.
3. WHEN the mapping is complete, THE `Cache_Layer` SHALL update the Active_Analysis document in MongoDB by setting `recommendations` to the mapped array using an atomic `$set` operation.
4. WHEN the MongoDB write-back succeeds, THE `Cache_Layer` SHALL return the recommendations with `cached = false`.
5. IF the MongoDB write-back fails, THEN THE `Cache_Layer` SHALL log the error and still return the generated recommendations to the caller with `cached = false`, so the user is not blocked.
6. WHEN the `Batch_Engine` raises an exception, THE `Cache_Layer` SHALL log the error and return HTTP 502 with the message `"Recommendation engine unavailable"`.

---

### Requirement 6: POST /api/user-recommendations Endpoint

**User Story:** As a frontend developer, I want a single endpoint that handles the full cache-check and generation flow, so that I do not need to orchestrate multiple API calls.

#### Acceptance Criteria

1. THE `Cache_Layer` SHALL expose a `POST /api/user-recommendations` route registered on the FastAPI application in `main.py`.
2. WHEN the endpoint receives a valid request, THE `Cache_Layer` SHALL return HTTP 200 with a `UserRecommendationResponse` body.
3. WHEN the endpoint encounters an unhandled exception, THE `Cache_Layer` SHALL return HTTP 500 with a descriptive error message and log the full traceback.
4. THE endpoint SHALL be documented with a summary and description visible in the OpenAPI schema at `/docs`.

---

### Requirement 7: CORS Configuration

**User Story:** As a frontend developer, I want the API to accept requests from all local development origins, so that I can develop against the API from any local port.

#### Acceptance Criteria

1. THE FastAPI application SHALL read allowed CORS origins from the `CORS_ORIGINS` environment variable, which contains a comma-separated list of origin URLs.
2. WHEN `CORS_ORIGINS` is set, THE FastAPI application SHALL replace the current wildcard `"*"` origin with the parsed list of origins.
3. WHEN `CORS_ORIGINS` is not set, THE FastAPI application SHALL fall back to allowing `"*"` as the origin so existing behaviour is preserved.
4. THE FastAPI application SHALL accept `http://localhost:3000`, `http://localhost:3001`, `http://localhost:3002`, and `http://localhost:3003` as valid origins when those values are present in `CORS_ORIGINS`.
