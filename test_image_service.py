"""
이미지 생성 서비스 테스트 스크립트

개인 백엔드 서버에서 로컬 이미지 저장 방식을 테스트합니다.
"""

import asyncio
import requests
import json
from pathlib import Path
import base64
from io import BytesIO
from PIL import Image

# 테스트 설정
BASE_URL = "http://127.0.0.1:8000"
API_BASE_URL = f"{BASE_URL}/api/v1"

# 테스트용 사용자 토큰 (실제 로그인 후 받은 토큰 사용)
# 이 부분은 실제 로그인을 통해 얻은 토큰으로 교체해야 합니다
TEST_TOKEN = "your-jwt-token-here"

def test_image_storage_service():
    """로컬 이미지 저장 서비스 단독 테스트"""
    print("=== 로컬 이미지 저장 서비스 테스트 ===")
    
    # 간단한 테스트 이미지 생성
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_data = img_bytes.getvalue()
    
    # 저장 테스트
    from app.services.image_storage_service import LocalImageStorage
    
    storage = LocalImageStorage()
    
    async def test_save():
        try:
            # 이미지 저장
            image_url = await storage.save_image(img_data, "test_image.png", "test_user")
            print(f"✅ 이미지 저장 성공: {image_url}")
            
            # 이미지 정보 조회
            image_info = await storage.get_image_info(image_url.replace('/api/v1/images/', ''))
            print(f"✅ 이미지 정보: {image_info}")
            
            return image_url
            
        except Exception as e:
            print(f"❌ 이미지 저장 실패: {e}")
            return None
    
    return asyncio.run(test_save())

def test_comfyui_service():
    """ComfyUI 서비스 단독 테스트"""
    print("\n=== ComfyUI 서비스 테스트 ===")
    
    from app.services.comfyui_service import get_comfyui_service, ImageGenerationRequest
    
    async def test_generate():
        try:
            comfyui_service = get_comfyui_service()
            
            request = ImageGenerationRequest(
                prompt="a beautiful landscape with mountains and lake",
                negative_prompt="low quality, blurry",
                width=512,
                height=512,
                steps=10,  # 빠른 테스트를 위해 적은 스텝
                cfg_scale=7.0
            )
            
            print("ComfyUI 이미지 생성 시작...")
            result = await comfyui_service.generate_image(request)
            
            print(f"✅ 생성 상태: {result.status}")
            print(f"✅ 생성된 이미지 수: {len(result.images)}")
            print(f"✅ 생성 시간: {result.generation_time}초")
            
            return result
            
        except Exception as e:
            print(f"❌ ComfyUI 생성 실패: {e}")
            return None
    
    return asyncio.run(test_generate())

def test_integrated_service():
    """통합 이미지 생성 서비스 테스트"""
    print("\n=== 통합 이미지 생성 서비스 테스트 ===")
    
    from app.services.integrated_image_service import (
        get_integrated_image_generation_service,
        IntegratedImageGenerationRequest
    )
    
    async def test_integrated():
        try:
            service = get_integrated_image_generation_service()
            
            request = IntegratedImageGenerationRequest(
                prompt="a cute cat sitting on a table",
                user_id="test_user_123",
                width=512,
                height=512,
                steps=10,
                save_to_storage=True,
                save_to_db=False  # DB 연결 없이 테스트
            )
            
            print("통합 이미지 생성 시작...")
            result = await service.generate_and_save_image(request, db=None)
            
            print(f"✅ 생성 성공: {result.success}")
            print(f"✅ 요청 ID: {result.request_id}")
            print(f"✅ 저장된 이미지 URL: {result.storage_urls}")
            print(f"✅ 선택된 이미지: {result.selected_image_url}")
            print(f"✅ 생성 시간: {result.generation_time}초")
            
            return result
            
        except Exception as e:
            print(f"❌ 통합 서비스 실패: {e}")
            return None
    
    return asyncio.run(test_integrated())

def test_api_endpoints():
    """API 엔드포인트 테스트"""
    print("\n=== API 엔드포인트 테스트 ===")
    
    # 헤더 설정
    headers = {
        "Authorization": f"Bearer {TEST_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 1. 이미지 생성 API 테스트
    print("\n1. 이미지 생성 API 테스트")
    
    generation_data = {
        "prompt": "a beautiful sunset over the ocean",
        "negative_prompt": "low quality, blurry",
        "width": 512,
        "height": 512,
        "steps": 10,
        "cfg_scale": 7.0,
        "style": "realistic",
        "save_to_storage": True
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/images/generate",
            headers=headers,
            json=generation_data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API 호출 성공: {result['success']}")
            print(f"✅ 요청 ID: {result['request_id']}")
            print(f"✅ 저장된 이미지: {len(result.get('storage_urls', []))}개")
            
            # 생성된 이미지 URL 테스트
            if result.get('storage_urls'):
                image_url = result['storage_urls'][0]
                print(f"\n2. 이미지 서빙 테스트: {image_url}")
                
                # 이미지 다운로드 테스트
                img_response = requests.get(f"{BASE_URL}{image_url}")
                if img_response.status_code == 200:
                    print("✅ 이미지 서빙 성공")
                    print(f"✅ 이미지 크기: {len(img_response.content)} bytes")
                else:
                    print(f"❌ 이미지 서빙 실패: {img_response.status_code}")
                    
        else:
            print(f"❌ API 호출 실패: {response.status_code}")
            print(f"오류 내용: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 네트워크 오류: {e}")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")

def test_file_upload():
    """파일 업로드 API 테스트"""
    print("\n=== 파일 업로드 API 테스트 ===")
    
    # 테스트용 이미지 생성
    img = Image.new('RGB', (200, 200), color='blue')
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_data = img_bytes.getvalue()
    
    headers = {
        "Authorization": f"Bearer {TEST_TOKEN}"
    }
    
    files = {
        "file": ("test_upload.png", img_data, "image/png")
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/images/upload",
            headers=headers,
            files=files
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 업로드 성공: {result['success']}")
            print(f"✅ 이미지 URL: {result['image_url']}")
            print(f"✅ 파일 크기: {result['size']} bytes")
        else:
            print(f"❌ 업로드 실패: {response.status_code}")
            print(f"오류 내용: {response.text}")
            
    except Exception as e:
        print(f"❌ 업로드 오류: {e}")

def test_server_health():
    """서버 상태 확인"""
    print("=== 서버 상태 확인 ===")
    
    try:
        # API 문서 접근 테스트
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("✅ Swagger 문서 접근 가능")
        else:
            print(f"❌ Swagger 문서 접근 실패: {response.status_code}")
            
        # 기본 API 테스트
        response = requests.get(f"{API_BASE_URL}/")
        print(f"API 기본 응답: {response.status_code}")
        
    except requests.exceptions.ConnectionError:
        print("❌ 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
        return False
    except Exception as e:
        print(f"❌ 서버 상태 확인 오류: {e}")
        return False
        
    return True

def run_all_tests():
    """모든 테스트 실행"""
    print("🚀 AIMEX 이미지 생성 서비스 종합 테스트 시작\n")
    
    # 1. 서버 상태 확인
    if not test_server_health():
        print("\n❌ 서버가 실행되지 않아 테스트를 중단합니다.")
        return
    
    print("\n" + "="*50)
    
    # 2. 로컬 저장소 테스트
    try:
        test_image_storage_service()
    except Exception as e:
        print(f"❌ 로컬 저장소 테스트 실패: {e}")
    
    print("\n" + "="*50)
    
    # 3. ComfyUI 서비스 테스트
    try:
        test_comfyui_service()
    except Exception as e:
        print(f"❌ ComfyUI 서비스 테스트 실패: {e}")
    
    print("\n" + "="*50)
    
    # 4. 통합 서비스 테스트
    try:
        test_integrated_service()
    except Exception as e:
        print(f"❌ 통합 서비스 테스트 실패: {e}")
    
    print("\n" + "="*50)
    
    # 5. API 엔드포인트 테스트 (토큰이 있는 경우에만)
    if TEST_TOKEN != "your-jwt-token-here":
        try:
            test_api_endpoints()
            test_file_upload()
        except Exception as e:
            print(f"❌ API 테스트 실패: {e}")
    else:
        print("\n⚠️  JWT 토큰이 설정되지 않아 API 테스트를 건너뜁니다.")
        print("실제 로그인 후 받은 토큰으로 TEST_TOKEN을 교체하세요.")
    
    print("\n🎉 테스트 완료!")
    print("\n📝 다음 단계:")
    print("1. 백엔드 서버 실행: cd backend && python run.py")
    print("2. 로그인하여 JWT 토큰 획득")
    print("3. 토큰으로 API 테스트 실행")
    print("4. 프론트엔드에서 이미지 생성 기능 테스트")

if __name__ == "__main__":
    run_all_tests()
