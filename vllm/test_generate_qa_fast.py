#!/usr/bin/env python3
"""
Test script for /generate_qa_fast endpoint
"""

import asyncio
import aiohttp
import json
import time

async def test_generate_qa_fast():
    """Test the improved /generate_qa_fast endpoint"""
    
    # Test character data
    test_character = {
        "name": "루나",
        "description": "밝고 활발한 20대 여성, 새로운 것을 좋아함",
        "age_range": "20-25세",
        "gender": "FEMALE",
        "personality": "친근하고 긍정적이며 호기심이 많음",
        "mbti": "ENFP"
    }
    
    # API endpoint
    url = "http://localhost:8000/speech/generate_qa_fast"
    
    print("🚀 Testing /generate_qa_fast endpoint...")
    print(f"📝 Character: {test_character['name']}")
    print("-" * 50)
    
    try:
        async with aiohttp.ClientSession() as session:
            # Send request
            start_time = time.time()
            
            async with session.post(url, json={"character": test_character}) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    end_time = time.time()
                    total_time = end_time - start_time
                    
                    print(f"✅ Success! Total time: {total_time:.2f}s")
                    print(f"⚡ API reported time: {result.get('generation_time_seconds', 'N/A'):.2f}s")
                    print(f"📝 Generated question: {result['question']}")
                    print("-" * 50)
                    
                    # Display responses
                    for tone_name, tone_responses in result['responses'].items():
                        print(f"\n🎭 {tone_name}:")
                        for response in tone_responses:
                            print(f"   Text: {response['text']}")
                            print(f"   Hashtags: {response.get('hashtags', 'N/A')}")
                            print(f"   Description: {response.get('description', 'N/A')}")
                    
                else:
                    error_text = await response.text()
                    print(f"❌ Error {response.status}: {error_text}")
                    
    except aiohttp.ClientError as e:
        print(f"❌ Connection error: {e}")
        print("Make sure the FastAPI server is running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

async def test_single_endpoint():
    """Test the /generate_qa_fast endpoint performance"""
    
    test_character = {
        "name": "알렉스",
        "description": "차분하고 지적인 30대 남성",
        "age_range": "30-35세",
        "gender": "MALE",
        "personality": "논리적이고 분석적이며 신중함",
        "mbti": "INTJ"
    }
    
    base_url = "http://localhost:8000/speech"
    
    print("🚀 Testing /generate_qa_fast endpoint performance...")
    print("-" * 50)
    
    async with aiohttp.ClientSession() as session:
        # Test fast endpoint
        print("📊 Testing /generate_qa_fast...")
        start_fast = time.time()
        
        try:
            async with session.post(f"{base_url}/generate_qa_fast", json={"character": test_character}) as response:
                if response.status == 200:
                    fast_result = await response.json()
                    fast_time = time.time() - start_fast
                    api_time = fast_result.get('generation_time_seconds', 0)
                    print(f"✅ Fast endpoint: {fast_time:.2f}s (API reported: {api_time:.2f}s)")
                else:
                    print(f"❌ Fast endpoint error: {response.status}")
                    fast_time = None
        except Exception as e:
            print(f"❌ Fast endpoint failed: {e}")
            fast_time = None
        
        # Show performance results
        if fast_time:
            print(f"\n📈 Performance Summary:")
            print(f"⚡ Total request time: {fast_time:.2f}s")
            print(f"⏱️  API processing time: {api_time:.2f}s")
            print(f"🌐 Network overhead: {fast_time - api_time:.2f}s")

if __name__ == "__main__":
    print("=" * 50)
    print("🧪 vLLM Speech Generation Test")
    print("=" * 50)
    
    # Run tests
    asyncio.run(test_generate_qa_fast())
    
    print("\n" + "=" * 50)
    
    # Run performance test
    asyncio.run(test_single_endpoint())