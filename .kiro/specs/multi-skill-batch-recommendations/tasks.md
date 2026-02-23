# Implementation Plan: Multi-Skill Batch Recommendations

## Overview

This implementation plan converts the approved design into discrete coding tasks for building the multi-skill batch recommendations feature. The implementation maintains the existing async architecture while introducing new data models, a batch orchestrator, and enhanced provider interfaces. Tasks are organized to build incrementally, with testing integrated throughout to validate correctness early.

## Tasks

- [x] 1. Create new data models for batch requests and simplified responses
  - Create `models/batch_models.py` with SkillRequest, BatchRecommendationRequest, SimplifiedCourse, SkillRecommendationResult, and BatchRecommendationResponse models
  - Add Pydantic validation for skill field (min_length=1), preferences (optional list of strings), max_results (1-50), and language (ISO 639-1 codes)
  - Add transformation function to convert existing Course objects to SimplifiedCourse objects
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 5.1, 5.4, 6.3, 7.1, 7.2, 7.3, 7.4_

- [ ]* 1.1 Write property test for batch request validation
  - **Property 1: Batch request accepts list of skill objects**
  - **Validates: Requirements 1.1, 1.3**

- [ ]* 1.2 Write property test for whitespace skill rejection
  - **Property 2: Whitespace-only skills are rejected**
  - **Validates: Requirements 2.3**

- [ ]* 1.3 Write property test for preferences type validation
  - **Property 3: Preferences type validation**
  - **Validates: Requirements 1.4**

- [ ]* 1.4 Write property test for missing preferences default
  - **Property 4: Missing preferences default to empty list**
  - **Validates: Requirements 1.5**

- [ ]* 1.5 Write property test for SimplifiedCourse field validation
  - **Property 15: SimplifiedCourse contains only specified fields**
  - **Validates: Requirements 7.3, 7.4, 6.3**

- [ ] 2. Modify provider interfaces to support language filtering
  - [x] 2.1 Update YouTubeProvider.fetch_courses() to accept optional language parameter
    - Add language parameter to method signature
    - Add relevanceLanguage parameter to YouTube API call when language is provided
    - Update method to return SimplifiedCourse objects instead of Course objects
    - _Requirements: 4.3, 6.3, 7.3_

  - [x] 2.2 Update GitHubProvider.fetch_courses() to accept optional language parameter
    - Add language parameter to method signature
    - Implement post-processing language filtering based on repository description
    - Update method to return SimplifiedCourse objects instead of Course objects
    - _Requirements: 4.3, 6.3, 7.3_

  - [ ]* 2.3 Write property test for language filter application
    - **Property 8: Language filter applies to all skills**
    - **Validates: Requirements 4.2**

  - [ ]* 2.4 Write property test for provider language parameter
    - **Property 9: Provider receives language parameter**
    - **Validates: Requirements 4.3**

  - [ ]* 2.5 Write unit tests for provider language filtering
    - Test YouTube provider with valid language codes
    - Test GitHub provider with language filtering
    - Test providers with no language parameter (default behavior)
    - _Requirements: 4.3, 4.4_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Modify RankingEngine to remove difficulty filtering and support enhanced preferences
  - [x] 4.1 Update rank_courses() method signature
    - Remove difficulty parameter from method signature
    - Remove all difficulty filtering logic
    - Update method to accept SimplifiedCourse objects
    - _Requirements: 6.1, 6.2, 6.4, 6.5_

  - [x] 4.2 Update _calculate_score() to handle all preference types equally
    - Ensure career goals, learning styles, time commitments, and technologies are treated equally in keyword matching
    - Remove any difficulty-based scoring adjustments
    - Update popularity scoring to work without rating field (use placeholder or provider-specific metrics)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 12.1, 12.4_

  - [ ]* 4.3 Write property test for preference scoring equality
    - **Property 7: All preference types affect scoring equally**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 12.4**

  - [ ]* 4.4 Write property test for no difficulty filtering
    - **Property 13: No difficulty filtering occurs**
    - **Validates: Requirements 6.2, 6.4**

  - [ ]* 4.5 Write property test for weighted scoring algorithm
    - **Property 19: Weighted scoring algorithm preserved**
    - **Validates: Requirements 12.1**

  - [ ]* 4.6 Write property test for keyword matching
    - **Property 20: Keyword matching preserved**
    - **Validates: Requirements 12.2**

  - [ ]* 4.7 Write property test for deduplication
    - **Property 21: Deduplication preserved**
    - **Validates: Requirements 12.3**

  - [ ]* 4.8 Write unit tests for ranking engine modifications
    - Test scoring with different preference types
    - Test that difficulty field is not used in scoring
    - Test deduplication with SimplifiedCourse objects
    - _Requirements: 3.5, 6.2, 12.3_

- [ ] 5. Implement batch orchestrator module
  - [x] 5.1 Create api/batch_recommendations.py module
    - Implement get_batch_recommendations() function to orchestrate batch processing
    - Implement process_single_skill() function to handle individual skill processing
    - Use asyncio.gather() for parallel processing at both skill and provider levels
    - Implement error handling with return_exceptions=True to isolate failures
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 5.2 Add error handling and metadata generation
    - Handle exceptions from individual skill processing
    - Generate metadata with total_skills, language, and skill_errors
    - Return empty recommendations for failed skills instead of failing entire request
    - _Requirements: 10.5, 11.1, 11.2, 11.3, 11.4, 11.5_

  - [ ]* 5.3 Write property test for skill processing independence
    - **Property 6: Skill processing independence**
    - **Validates: Requirements 2.5, 8.4**

  - [ ]* 5.4 Write property test for error isolation
    - **Property 17: Error isolation between skills**
    - **Validates: Requirements 8.3, 8.5**

  - [ ]* 5.5 Write property test for preferences flow through
    - **Property 5: Preferences flow through to ranking**
    - **Validates: Requirements 2.4**

  - [ ]* 5.6 Write unit tests for batch orchestrator
    - Test parallel processing of multiple skills
    - Test error handling when one skill fails
    - Test error handling when all providers fail for a skill
    - Test metadata generation
    - _Requirements: 8.3, 8.5, 11.4, 11.5_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Create FastAPI endpoint for batch recommendations
  - [x] 7.1 Add /api/batch-recommendations endpoint to main.py
    - Create POST endpoint accepting BatchRecommendationRequest
    - Return BatchRecommendationResponse
    - Add error handling for validation errors (422) and server errors (500)
    - Add logging for batch requests
    - _Requirements: 1.1, 1.2, 9.1, 10.1, 10.2, 10.3, 10.4_

  - [ ]* 7.2 Write property test for max results per skill
    - **Property 12: Max results applies per skill**
    - **Validates: Requirements 5.2, 5.5**

  - [ ]* 7.3 Write property test for response structure
    - **Property 14: Response structure matches specification**
    - **Validates: Requirements 7.1, 7.2**

  - [ ]* 7.4 Write property test for metadata fields
    - **Property 16: Metadata contains required fields**
    - **Validates: Requirements 7.5, 11.1, 11.2, 11.3**

  - [ ]* 7.5 Write property test for valid language codes
    - **Property 10: Valid language codes are accepted**
    - **Validates: Requirements 4.5**

  - [ ]* 7.6 Write property test for invalid language codes
    - **Property 11: Invalid language codes are rejected**
    - **Validates: Requirements 10.4**

  - [ ]* 7.7 Write property test for provider failure metadata
    - **Property 18: Provider failure metadata**
    - **Validates: Requirements 11.4, 11.5**

  - [ ]* 7.8 Write integration tests for batch endpoint
    - Test end-to-end batch request with multiple skills
    - Test language filtering across all skills
    - Test max_results applies per skill
    - Test validation errors (empty skills list, empty skill field, invalid max_results)
    - Test partial results when some skills fail
    - _Requirements: 1.2, 4.2, 5.2, 10.1, 10.2, 10.3, 10.5_

- [ ] 8. Add request validation and error responses
  - [x] 8.1 Implement custom validation for ISO 639-1 language codes
    - Create validator function for language codes
    - Add validation to BatchRecommendationRequest model
    - _Requirements: 4.5, 10.4_

  - [x] 8.2 Add detailed error messages for validation failures
    - Ensure error messages include skill index for skill-specific errors
    - Ensure error messages are clear and actionable
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ]* 8.3 Write unit tests for validation errors
    - Test empty skills list returns 422
    - Test empty skill field returns 422 with skill index
    - Test max_results out of range returns 422
    - Test invalid language code returns 422
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [ ] 9. Create migration documentation and examples
  - [x] 9.1 Create migration guide document
    - Document conversion from single-skill to batch format
    - Document breaking changes (difficulty removal, response structure changes)
    - Provide code examples for old vs new format
    - Document response mapping for accessing results
    - _Requirements: 9.2, 9.4, 9.5_

  - [x] 9.2 Add API documentation with examples
    - Add OpenAPI/Swagger documentation for new endpoint
    - Include example requests for single skill, multiple skills, and error cases
    - Document all request and response fields
    - _Requirements: 9.2, 9.4_

- [x] 10. Final checkpoint - Ensure all tests pass and documentation is complete
  - Ensure all tests pass, ask the user if questions arise.
  - Verify migration guide is complete and accurate
  - Verify API documentation is comprehensive

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation throughout implementation
- Property tests validate universal correctness properties with minimum 100 iterations each
- Unit tests validate specific examples, edge cases, and error conditions
- The implementation maintains backward compatibility by creating a new endpoint
- All async operations use asyncio.gather() for parallel processing
- Error isolation ensures partial results are returned when some operations fail
