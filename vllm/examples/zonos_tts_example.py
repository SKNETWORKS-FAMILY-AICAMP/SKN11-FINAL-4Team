#!/usr/bin/env python3
"""
Zonos TTS 엔드포인트 사용 예제 (S3 업로드 포함)
"""

import requests
import json
import os
from pathlib import Path

# API 엔드포인트 URL
BASE_URL = "http://localhost:8000"  # FastAPI 서버 URL을 환경에 맞게 수정하세요

# S3 설정 (환경 변수에서 읽거나 직접 설정)
S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME", "your-bucket-name")
S3_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

def test_simple_tts():
    """간단한 TTS 생성 테스트"""
    print("=== 간단한 TTS 생성 테스트 ===")
    
    response = requests.post(
        f"{BASE_URL}/zonos/generate_tts_simple",
        data={"text": "안녕하세요. 저는 Zonos TTS 시스템입니다."}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ TTS 생성 성공!")
        print(f"   오디오 파일 경로: {result['audio_path']}")
        print(f"   메시지: {result['message']}")
    else:
        print(f"❌ 오류 발생: {response.text}")

def test_advanced_tts():
    """고급 TTS 생성 테스트 (세부 설정 포함)"""
    print("\n=== 고급 TTS 생성 테스트 ===")
    
    request_data = {
        "text": "나는 정말 일어서면 안 되는데 내가 감정 표현하면 안 되는데 난 네가 너무 비겁하다",
        "language": "ko",
        "speaking_rate": 22.0,
        "pitch_std": 40.0,
        "cfg_scale": 4.0,
        "output_filename": "custom_tts_output.wav"
    }
    
    response = requests.post(
        f"{BASE_URL}/zonos/generate_tts",
        json=request_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ TTS 생성 성공!")
        print(f"   오디오 파일 경로: {result['audio_path']}")
        print(f"   메시지: {result['message']}")
        
        # 파일 다운로드
        download_url = f"{BASE_URL}/zonos/download_tts/{request_data['output_filename']}"
        print(f"   다운로드 URL: {download_url}")
    else:
        print(f"❌ 오류 발생: {response.text}")

def test_voice_clone_tts():
    """음성 클로닝을 사용한 TTS 생성 테스트"""
    print("\n=== 음성 클로닝 TTS 생성 테스트 ===")
    
    # 음성 파일이 있다고 가정 (실제 사용 시 경로 수정 필요)
    voice_file_path = "/path/to/your/voice.wav"
    
    if not Path(voice_file_path).exists():
        print("⚠️  음성 파일이 없어 테스트를 건너뜁니다.")
        print(f"   테스트하려면 {voice_file_path}에 음성 파일을 준비하세요.")
        return
    
    request_data = {
        "text": "이것은 음성 클로닝을 사용한 TTS 테스트입니다.",
        "language": "ko",
        "speaking_rate": 20.0,
        "pitch_std": 35.0,
        "cfg_scale": 4.5
    }
    
    with open(voice_file_path, 'rb') as f:
        files = {'voice_file': f}
        data = {key: str(value) for key, value in request_data.items()}
        
        response = requests.post(
            f"{BASE_URL}/zonos/generate_tts",
            data=data,
            files=files
        )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ 음성 클로닝 TTS 생성 성공!")
        print(f"   오디오 파일 경로: {result['audio_path']}")
        print(f"   메시지: {result['message']}")
    else:
        print(f"❌ 오류 발생: {response.text}")

def check_zonos_status():
    """Zonos 모델 상태 확인"""
    print("\n=== Zonos 모델 상태 확인 ===")
    
    response = requests.get(f"{BASE_URL}/zonos/zonos_status")
    
    if response.status_code == 200:
        status = response.json()
        print(f"✅ 모델 로드 상태: {'로드됨' if status['model_loaded'] else '로드되지 않음'}")
        print(f"   디바이스: {status['device']}")
        print(f"   CUDA 사용 가능: {status['available']}")
    else:
        print(f"❌ 상태 확인 실패: {response.text}")

def configure_s3():
    """S3 설정"""
    print("\n=== S3 설정 ===")
    
    if not S3_BUCKET_NAME or S3_BUCKET_NAME == "your-bucket-name":
        print("⚠️  S3 버킷 이름이 설정되지 않았습니다.")
        print("   AWS_S3_BUCKET_NAME 환경 변수를 설정하거나 코드에서 직접 수정하세요.")
        return False
    
    config_data = {
        "bucket_name": S3_BUCKET_NAME,
        "region_name": S3_REGION
    }
    
    # AWS 자격 증명이 있으면 추가
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        config_data["aws_access_key_id"] = AWS_ACCESS_KEY_ID
        config_data["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
    
    response = requests.post(
        f"{BASE_URL}/zonos/configure_s3",
        json=config_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ S3 설정 성공!")
        print(f"   버킷: {result['bucket']}")
        print(f"   리전: {result['region']}")
        return True
    else:
        print(f"❌ S3 설정 실패: {response.text}")
        return False

def test_tts_with_s3_upload():
    """S3 업로드를 포함한 TTS 생성 테스트"""
    print("\n=== S3 업로드 포함 TTS 생성 테스트 ===")
    
    request_data = {
        "text": "이 음성 파일은 자동으로 S3에 업로드됩니다.",
        "language": "ko",
        "speaking_rate": 22.0,
        "pitch_std": 40.0,
        "cfg_scale": 4.0,
        "output_filename": "s3_upload_test.wav",
        "upload_to_s3": True,
        "s3_folder_prefix": "zonos-tts/samples",
        "s3_public_read": True  # Public URL 생성
    }
    
    response = requests.post(
        f"{BASE_URL}/zonos/generate_tts",
        json=request_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ TTS 생성 및 S3 업로드 성공!")
        print(f"   로컬 파일: {result['audio_path']}")
        
        if result.get('s3_info'):
            s3_info = result['s3_info']
            print(f"   S3 정보:")
            print(f"     - 버킷: {s3_info['bucket']}")
            print(f"     - 키: {s3_info['key']}")
            print(f"     - URL: {s3_info['url']}")
        else:
            print("   ⚠️ S3 업로드 정보가 없습니다.")
    else:
        print(f"❌ 오류 발생: {response.text}")

def check_s3_status():
    """S3 연결 상태 확인"""
    print("\n=== S3 연결 상태 확인 ===")
    
    response = requests.get(f"{BASE_URL}/zonos/s3_status")
    
    if response.status_code == 200:
        status = response.json()
        if status['connected']:
            print(f"✅ S3 연결됨")
            print(f"   버킷: {status['bucket']}")
            print(f"   리전: {status['region']}")
        else:
            print(f"❌ S3 연결 안됨")
            print(f"   오류: {status.get('error', 'Unknown')}")
    else:
        print(f"❌ 상태 확인 실패: {response.text}")

if __name__ == "__main__":
    print("Zonos TTS API 테스트 시작 (S3 통합 포함)\n")
    
    # 서버 상태 확인
    check_zonos_status()
    
    # S3 설정
    s3_configured = configure_s3()
    
    # S3 상태 확인
    if s3_configured:
        check_s3_status()
    
    # 각 기능 테스트
    test_simple_tts()
    test_advanced_tts()
    
    # S3 업로드 테스트
    if s3_configured:
        test_tts_with_s3_upload()
    
    test_voice_clone_tts()
    
    print("\n테스트 완료!")