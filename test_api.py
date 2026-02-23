#!/usr/bin/env python3
"""
Simple test script for the Skillevate Recommendation API
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    """Test health endpoint"""
    response = requests.get(f"{BASE_URL}/health")
    print("Health Check:", response.json())
    return response.status_code == 200

def test_recommendations(skill, difficulty="all", max_results=5):
    """Test recommendations endpoint"""
    payload = {
        "skill": skill,
        "difficulty": difficulty,
        "max_results": max_results
    }
    
    print(f"\n🔍 Searching for: {skill}")
    print(f"Difficulty: {difficulty}, Max Results: {max_results}\n")
    
    response = requests.post(
        f"{BASE_URL}/api/recommendations",
        json=payload
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data['total_results']} recommendations\n")
        
        for idx, course in enumerate(data['recommendations'], 1):
            print(f"{idx}. {course['title']}")
            print(f"   Provider: {course['provider']}")
            print(f"   URL: {course['url']}")
            print(f"   Score: {course['relevance_score']:.2f}")
            if course.get('rating'):
                print(f"   Rating: {course['rating']:.1f}")
            print()
        
        print(f"Metadata: {json.dumps(data['metadata'], indent=2)}")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Skillevate Recommendation API Test")
    print("=" * 60)
    
    # Test health
    if test_health():
        print("\n✅ Server is healthy\n")
    
    # Test different skills
    test_recommendations("python programming", max_results=5)
    print("\n" + "-" * 60 + "\n")
    test_recommendations("machine learning", max_results=3)
