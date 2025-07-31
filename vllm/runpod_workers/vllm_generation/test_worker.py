"""
vLLM Worker 테스트 스크립트
"""
import requests
import json
import time
import sys

# 테스트 서버 URL
BASE_URL = "http://localhost:8000"

def test_sync_generation():
    """동기 생성 테스트"""
    print("\n=== 동기 생성 테스트 ===")
    
    payload = {
        "prompt": "인공지능의 장점 3가지를 설명해주세요.",
        "max_tokens": 200,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(f"{BASE_URL}/generate", json=payload)
        result = response.json()
        
        if result.get("status") == "success":
            print(f"✅ 성공!")
            print(f"생성된 텍스트:\n{result['generated_text']}")
            print(f"사용된 모델: {result.get('model')}")
            print(f"토큰 수: {result.get('max_tokens')}")
        else:
            print(f"❌ 실패: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ 요청 오류: {e}")

def test_async_generation():
    """비동기 생성 테스트 (멀티 요청)"""
    print("\n=== 비동기 생성 테스트 (멀티 요청) ===")
    
    payloads = [
        {
            "prompt": "Python의 장점을 설명해주세요.",
            "max_tokens": 150,
            "temperature": 0.6
        },
        {
            "prompt": "머신러닝이란 무엇인가요?",
            "max_tokens": 150,
            "temperature": 0.6
        },
        {
            "prompt": "클라우드 컴퓨팅의 미래는?",
            "max_tokens": 150,
            "temperature": 0.6
        }
    ]
    
    # 동시에 여러 요청 전송
    import concurrent.futures
    
    def send_request(payload):
        try:
            response = requests.post(f"{BASE_URL}/generate/async", json=payload)
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(send_request, p) for p in payloads]
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            print(f"\n요청 {i+1}:")
            if result.get("status") == "success":
                print(f"✅ 성공!")
                print(f"생성된 텍스트: {result['generated_text'][:100]}...")
            else:
                print(f"❌ 실패: {result.get('error')}")

def test_chat_format():
    """채팅 형식 테스트"""
    print("\n=== 채팅 형식 테스트 ===")
    
    payload = {
        "messages": [
            {"role": "system", "content": "당신은 Python 전문가입니다."},
            {"role": "user", "content": "리스트 컴프리헨션을 설명해주세요."}
        ],
        "max_tokens": 200,
        "temperature": 0.5
    }
    
    try:
        response = requests.post(f"{BASE_URL}/generate", json=payload)
        result = response.json()
        
        if result.get("status") == "success":
            print(f"✅ 성공!")
            print(f"생성된 텍스트:\n{result['generated_text']}")
        else:
            print(f"❌ 실패: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ 요청 오류: {e}")

def test_influencer_mode():
    """인플루언서 모드 테스트"""
    print("\n=== 인플루언서 모드 테스트 ===")
    
    payload = {
        "prompt": "오늘 코딩하면서 느낀 점을 공유해볼게요.",
        "influencer_name": "개발자 김코딩",
        "system_message": "당신은 열정적인 개발자 인플루언서입니다. 긍정적이고 동기부여가 되는 톤으로 대화합니다.",
        "max_tokens": 200,
        "temperature": 0.8
    }
    
    try:
        response = requests.post(f"{BASE_URL}/generate", json=payload)
        result = response.json()
        
        if result.get("status") == "success":
            print(f"✅ 성공!")
            print(f"생성된 텍스트:\n{result['generated_text']}")
        else:
            print(f"❌ 실패: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ 요청 오류: {e}")

def test_lora_adapter():
    """LoRA 어댑터 테스트"""
    print("\n=== LoRA 어댑터 테스트 ===")
    
    payload = {
        "prompt": "딥러닝 모델 최적화 방법을 설명해주세요.",
        "lora_adapter": "hf://example/test-adapter",  # 실제 어댑터로 변경 필요
        "max_tokens": 200,
        "temperature": 0.6
    }
    
    try:
        response = requests.post(f"{BASE_URL}/generate", json=payload)
        result = response.json()
        
        if result.get("status") == "success":
            print(f"✅ 성공!")
            print(f"생성된 텍스트:\n{result['generated_text']}")
            print(f"사용된 LoRA: {result.get('lora_adapter')}")
        elif result.get("error_type") == "adapter_not_found":
            print(f"⚠️ LoRA 어댑터를 찾을 수 없음: {result.get('error')}")
            print("베이스 모델로 재시도...")
            
            # 베이스 모델로 재시도
            del payload["lora_adapter"]
            response = requests.post(f"{BASE_URL}/generate", json=payload)
            result = response.json()
            
            if result.get("status") == "success":
                print(f"✅ 베이스 모델로 성공!")
                print(f"생성된 텍스트:\n{result['generated_text']}")
        else:
            print(f"❌ 실패: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ 요청 오류: {e}")

def test_performance():
    """성능 테스트"""
    print("\n=== 성능 테스트 ===")
    
    payload = {
        "prompt": "Hello, world!",
        "max_tokens": 50,
        "temperature": 0.5
    }
    
    # 첫 번째 요청 (콜드 스타트)
    start_time = time.time()
    response = requests.post(f"{BASE_URL}/generate", json=payload)
    cold_time = time.time() - start_time
    
    print(f"콜드 스타트 시간: {cold_time:.2f}초")
    
    # 두 번째 요청 (웜 스타트)
    start_time = time.time()
    response = requests.post(f"{BASE_URL}/generate", json=payload)
    warm_time = time.time() - start_time
    
    print(f"웜 스타트 시간: {warm_time:.2f}초")
    print(f"속도 향상: {(cold_time / warm_time):.1f}배")

def main():
    """메인 테스트 함수"""
    print("vLLM Worker 테스트 시작")
    print(f"테스트 서버: {BASE_URL}")
    
    # 헬스체크
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ 서버 상태: 정상")
        else:
            print("❌ 서버 상태: 비정상")
            return
    except:
        print("❌ 서버에 연결할 수 없습니다.")
        print("Docker 컨테이너가 실행 중인지 확인하세요.")
        return
    
    # 테스트 실행
    tests = [
        test_sync_generation,
        test_chat_format,
        test_influencer_mode,
        test_async_generation,
        test_lora_adapter,
        test_performance
    ]
    
    for test in tests:
        try:
            test()
            time.sleep(1)  # 테스트 간 간격
        except Exception as e:
            print(f"❌ 테스트 실패: {e}")
    
    print("\n=== 모든 테스트 완료 ===")

if __name__ == "__main__":
    main()