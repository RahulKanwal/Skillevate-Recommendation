#!/usr/bin/env python3
"""
Test script for the Skillevate Batch Recommendation API (v2)
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"


def test_health():
    """Test health endpoint"""
    response = requests.get(f"{BASE_URL}/health")
    print("Health Check:", response.json())
    return response.status_code == 200


def test_batch_recommendations_single_skill():
    """Test batch endpoint with single skill"""
    payload = {
        "skills": [
            {
                "skill": "python",
                "preferences": ["Backend Developer", "FastAPI"]
            }
        ],
        "max_results": 5,
        "language": "en"
    }
    
    print("\n" + "=" * 60)
    print("TEST: Single Skill Batch Request")
    print("=" * 60)
    print(f"Request: {json.dumps(payload, indent=2)}\n")
    
    response = requests.post(
        f"{BASE_URL}/api/batch-recommendations",
        json=payload
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success! Received {len(data['results'])} skill results\n")
        
        for skill_result in data['results']:
            print(f"Skill: {skill_result['skill']}")
            print(f"Total Results: {skill_result['total_results']}\n")
            
            for idx, course in enumerate(skill_result['recommendations'][:3], 1):
                print(f"  {idx}. {course['title']}")
                print(f"     Provider: {course['provider']}")
                print(f"     URL: {course['url']}")
                print(f"     Score: {course['relevance_score']:.2f}")
                print(f"     Tags: {', '.join(course['tags'][:5])}")
                print()
        
        print(f"Metadata: {json.dumps(data['metadata'], indent=2)}")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return False


def test_batch_recommendations_multiple_skills():
    """Test batch endpoint with multiple skills"""
    payload = {
        "skills": [
            {
                "skill": "python",
                "preferences": ["Backend Developer", "project-based"]
            },
            {
                "skill": "docker",
                "preferences": ["Backend Developer", "microservices"]
            },
            {
                "skill": "postgresql",
                "preferences": ["database optimization"]
            }
        ],
        "max_results": 3,
        "language": "en"
    }
    
    print("\n" + "=" * 60)
    print("TEST: Multiple Skills Batch Request")
    print("=" * 60)
    print(f"Request: {json.dumps(payload, indent=2)}\n")
    
    response = requests.post(
        f"{BASE_URL}/api/batch-recommendations",
        json=payload
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success! Received {len(data['results'])} skill results\n")
        
        for skill_result in data['results']:
            print(f"Skill: {skill_result['skill']}")
            print(f"Total Results: {skill_result['total_results']}")
            
            for idx, course in enumerate(skill_result['recommendations'], 1):
                print(f"  {idx}. {course['title']} ({course['provider']}) - Score: {course['relevance_score']:.2f}")
            print()
        
        print(f"Metadata: {json.dumps(data['metadata'], indent=2)}")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return False


def test_validation_errors():
    """Test validation error handling"""
    print("\n" + "=" * 60)
    print("TEST: Validation Errors")
    print("=" * 60)
    
    # Test 1: Empty skills list
    print("\n1. Testing empty skills list...")
    response = requests.post(
        f"{BASE_URL}/api/batch-recommendations",
        json={"skills": [], "max_results": 10}
    )
    if response.status_code == 422:
        print("✅ Correctly rejected empty skills list")
    else:
        print(f"❌ Expected 422, got {response.status_code}")
    
    # Test 2: Whitespace-only skill
    print("\n2. Testing whitespace-only skill...")
    response = requests.post(
        f"{BASE_URL}/api/batch-recommendations",
        json={"skills": [{"skill": "   "}], "max_results": 10}
    )
    if response.status_code == 422:
        print("✅ Correctly rejected whitespace-only skill")
    else:
        print(f"❌ Expected 422, got {response.status_code}")
    
    # Test 3: Invalid language code
    print("\n3. Testing invalid language code...")
    response = requests.post(
        f"{BASE_URL}/api/batch-recommendations",
        json={"skills": [{"skill": "python"}], "max_results": 10, "language": "xyz"}
    )
    if response.status_code == 422:
        print("✅ Correctly rejected invalid language code")
        print(f"   Error: {response.json()['detail'][0]['msg']}")
    else:
        print(f"❌ Expected 422, got {response.status_code}")
    
    # Test 4: max_results out of range
    print("\n4. Testing max_results out of range...")
    response = requests.post(
        f"{BASE_URL}/api/batch-recommendations",
        json={"skills": [{"skill": "python"}], "max_results": 100}
    )
    if response.status_code == 422:
        print("✅ Correctly rejected max_results > 50")
    else:
        print(f"❌ Expected 422, got {response.status_code}")


def test_old_endpoint_still_works():
    """Test that old v1 endpoint still works"""
    payload = {
        "skill": "python programming",
        "difficulty": "beginner",
        "max_results": 3
    }
    
    print("\n" + "=" * 60)
    print("TEST: Old v1 Endpoint (Backward Compatibility)")
    print("=" * 60)
    print(f"Request: {json.dumps(payload, indent=2)}\n")
    
    response = requests.post(
        f"{BASE_URL}/api/recommendations",
        json=payload
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Old endpoint still works!")
        print(f"   Found {data['total_results']} recommendations")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Skillevate Batch Recommendation API Test Suite")
    print("=" * 60)
    
    # Test health
    if test_health():
        print("\n✅ Server is healthy\n")
    else:
        print("\n❌ Server health check failed. Is the server running?")
        print("   Start with: uvicorn main:app --reload")
        exit(1)
    
    # Run tests
    test_batch_recommendations_single_skill()
    test_batch_recommendations_multiple_skills()
    test_validation_errors()
    test_old_endpoint_still_works()
    
    print("\n" + "=" * 60)
    print("Test Suite Complete!")
    print("=" * 60)
