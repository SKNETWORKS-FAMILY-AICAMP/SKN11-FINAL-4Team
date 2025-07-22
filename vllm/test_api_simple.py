#!/usr/bin/env python3
"""
Simple API test script to check endpoint availability
"""

import requests
import json

def test_health():
    """Test health endpoint"""
    try:
        response = requests.get("http://localhost:8000/health")
        print(f"Health check status: {response.status_code}")
        if response.status_code == 200:
            print(f"Health response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_speech_endpoint():
    """Test speech generation endpoint"""
    test_character = {
        "name": "테스트",
        "description": "테스트 캐릭터",
        "age_range": "20-25세",
        "gender": "FEMALE",
        "personality": "친근함",
        "mbti": "ENFP"
    }
    
    try:
        # Test with correct structure
        payload = {"character": test_character}
        
        response = requests.post(
            "http://localhost:8000/speech/generate_qa_fast",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\nSpeech endpoint status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("Success! Response structure:")
            print(f"- Question: {result.get('question', 'N/A')[:50]}...")
            print(f"- Generation time: {result.get('generation_time_seconds', 'N/A')}s")
            print(f"- Number of responses: {len(result.get('responses', {}))}")
        else:
            print(f"Error response: {response.text}")
            
        return response.status_code
        
    except Exception as e:
        print(f"Speech endpoint test failed: {e}")
        return None

if __name__ == "__main__":
    print("=" * 50)
    print("🧪 Simple API Test")
    print("=" * 50)
    
    # Test health endpoint
    print("\n1. Testing health endpoint...")
    health_ok = test_health()
    
    # Test speech endpoint
    print("\n2. Testing speech generation endpoint...")
    speech_status = test_speech_endpoint()
    
    print("\n" + "=" * 50)
    print("Summary:")
    print(f"- Health check: {'✅ OK' if health_ok else '❌ Failed'}")
    print(f"- Speech endpoint: {f'✅ Status {speech_status}' if speech_status == 200 else f'❌ Status {speech_status}'}")