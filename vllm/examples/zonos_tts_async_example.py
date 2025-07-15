#!/usr/bin/env python3
"""
Zonos TTS 비동기 엔드포인트 사용 예제
"""

import asyncio
import aiohttp
import os
import json
import time
from pathlib import Path

# API 엔드포인트 URL
BASE_URL = "http://localhost:8000"

# S3 설정
S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME", "your-bucket-name")
S3_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

async def configure_s3(session):
    """S3 설정"""
    print("\n=== S3 설정 ===")
    
    config_data = {
        "bucket_name": S3_BUCKET_NAME,
        "region_name": S3_REGION
    }
    
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        config_data["aws_access_key_id"] = AWS_ACCESS_KEY_ID
        config_data["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
    
    async with session.post(
        f"{BASE_URL}/zonos/configure_s3",
        json=config_data
    ) as response:
        if response.status == 200:
            result = await response.json()
            print(f"✅ S3 설정 성공!")
            print(f"   버킷: {result['bucket']}")
            print(f"   리전: {result['region']}")
            return True
        else:
            print(f"❌ S3 설정 실패: {await response.text()}")
            return False

async def check_task_status(session, task_id):
    """작업 상태 확인"""
    async with session.get(f"{BASE_URL}/zonos/task_status/{task_id}") as response:
        if response.status == 200:
            return await response.json()
        else:
            return None

async def wait_for_task_completion(session, task_id, timeout=60):
    """작업 완료 대기"""
    start_time = time.time()
    last_progress = -1
    
    while time.time() - start_time < timeout:
        status = await check_task_status(session, task_id)
        
        if status:
            # 진행률 표시
            if status['progress'] != last_progress:
                print(f"\r진행률: {status['progress']}% - {status['message']}", end="", flush=True)
                last_progress = status['progress']
            
            if status['status'] == 'completed':
                print()  # 줄바꿈
                return status
            elif status['status'] == 'failed':
                print(f"\n❌ 작업 실패: {status.get('error', 'Unknown error')}")
                return status
        
        await asyncio.sleep(0.5)
    
    print("\n⏱️ 작업 시간 초과")
    return None

async def test_async_tts(session):
    """비동기 TTS 생성 테스트"""
    print("\n=== 비동기 TTS 생성 테스트 ===")
    
    request_data = {
        "text": "이것은 비동기 TTS 생성 테스트입니다. 백그라운드에서 처리됩니다.",
        "language": "ko",
        "speaking_rate": 22.0,
        "pitch_std": 40.0,
        "cfg_scale": 4.0,
        "output_filename": "async_test.wav",
        "async_mode": True
    }
    
    async with session.post(
        f"{BASE_URL}/zonos/generate_tts",
        json=request_data
    ) as response:
        if response.status == 200:
            result = await response.json()
            task_id = result['task_id']
            print(f"✅ 작업 시작됨: {task_id}")
            print(f"   상태: {result['status']}")
            print(f"   메시지: {result['message']}")
            
            # 작업 완료 대기
            print("\n작업 진행 상황:")
            final_status = await wait_for_task_completion(session, task_id)
            
            if final_status and final_status['status'] == 'completed':
                print(f"\n✅ TTS 생성 완료!")
                if final_status['result']:
                    print(f"   오디오 파일: {final_status['result']['audio_path']}")
                    if final_status['result'].get('s3_info'):
                        print(f"   S3 URL: {final_status['result']['s3_info']['url']}")
            
            return task_id
        else:
            print(f"❌ 오류 발생: {await response.text()}")
            return None

async def test_multiple_async_tts(session):
    """여러 TTS 동시 생성 테스트"""
    print("\n=== 다중 비동기 TTS 생성 테스트 ===")
    
    texts = [
        "첫 번째 비동기 TTS 테스트입니다.",
        "두 번째 테스트 문장입니다. 동시에 처리됩니다.",
        "세 번째 문장도 함께 처리됩니다.",
        "네 번째 문장입니다. 모든 작업이 병렬로 진행됩니다.",
        "다섯 번째이자 마지막 테스트 문장입니다."
    ]
    
    # 모든 작업 동시 시작
    tasks = []
    for i, text in enumerate(texts):
        request_data = {
            "text": text,
            "language": "ko",
            "output_filename": f"async_multi_{i+1}.wav",
            "async_mode": True,
            "upload_to_s3": True,
            "s3_folder_prefix": "zonos-tts/async-test"
        }
        
        task = session.post(
            f"{BASE_URL}/zonos/generate_tts",
            json=request_data
        )
        tasks.append(task)
    
    # 모든 응답 수집
    responses = await asyncio.gather(*tasks)
    task_ids = []
    
    for i, response in enumerate(responses):
        if response.status == 200:
            result = await response.json()
            task_ids.append(result['task_id'])
            print(f"✅ 작업 {i+1} 시작: {result['task_id']}")
        else:
            print(f"❌ 작업 {i+1} 실패")
    
    # 모든 작업 완료 대기
    print("\n모든 작업 진행 상황 모니터링...")
    
    completion_tasks = [
        wait_for_task_completion(session, task_id, timeout=120)
        for task_id in task_ids
    ]
    
    results = await asyncio.gather(*completion_tasks)
    
    # 결과 요약
    print("\n=== 작업 완료 요약 ===")
    success_count = 0
    for i, (task_id, result) in enumerate(zip(task_ids, results)):
        if result and result['status'] == 'completed':
            success_count += 1
            print(f"✅ 작업 {i+1} ({task_id[:8]}...): 성공")
            if result['result'].get('s3_info'):
                print(f"   S3 URL: {result['result']['s3_info']['url']}")
        else:
            print(f"❌ 작업 {i+1} ({task_id[:8]}...): 실패")
    
    print(f"\n총 {len(task_ids)}개 중 {success_count}개 성공")

async def test_task_management(session):
    """작업 관리 기능 테스트"""
    print("\n=== 작업 관리 기능 테스트 ===")
    
    # 작업 목록 조회
    async with session.get(f"{BASE_URL}/zonos/tasks?limit=5") as response:
        if response.status == 200:
            result = await response.json()
            print(f"최근 작업 목록 (총 {result['total']}개):")
            for task in result['tasks']:
                print(f"  - {task['task_id'][:8]}... : {task['status']} ({task['created_at']})")

async def test_sync_mode(session):
    """동기 모드 TTS 생성 테스트"""
    print("\n=== 동기 모드 TTS 생성 테스트 ===")
    
    request_data = {
        "text": "동기 모드로 즉시 처리되는 TTS입니다.",
        "language": "ko",
        "async_mode": False  # 동기 모드
    }
    
    start_time = time.time()
    
    async with session.post(
        f"{BASE_URL}/zonos/generate_tts",
        json=request_data
    ) as response:
        if response.status == 200:
            result = await response.json()
            elapsed_time = time.time() - start_time
            
            print(f"✅ TTS 생성 완료 (소요 시간: {elapsed_time:.2f}초)")
            print(f"   오디오 파일: {result.get('audio_path', 'N/A')}")
            if result.get('s3_info'):
                print(f"   S3 URL: {result['s3_info']['url']}")
        else:
            print(f"❌ 오류 발생: {await response.text()}")

async def check_system_status(session):
    """시스템 상태 확인"""
    print("\n=== 시스템 상태 확인 ===")
    
    # Zonos 상태
    async with session.get(f"{BASE_URL}/zonos/zonos_status") as response:
        if response.status == 200:
            status = await response.json()
            print("Zonos 모델 상태:")
            print(f"  - 모델 로드: {'✅' if status['model_loaded'] else '❌'}")
            print(f"  - 디바이스: {status['device']}")
            print(f"  - CUDA 사용 가능: {'✅' if status['cuda_available'] else '❌'}")
            print(f"  - 활성 작업: {status['active_tasks']}")
            print(f"  - 대기 작업: {status['pending_tasks']}")
            print(f"  - 전체 작업: {status['total_tasks']}")
    
    # S3 상태
    async with session.get(f"{BASE_URL}/zonos/s3_status") as response:
        if response.status == 200:
            status = await response.json()
            print("\nS3 상태:")
            if status['connected']:
                print(f"  - 연결 상태: ✅")
                print(f"  - 버킷: {status['bucket']}")
                print(f"  - 리전: {status['region']}")
            else:
                print(f"  - 연결 상태: ❌")
                print(f"  - 오류: {status.get('error', 'Unknown')}")

async def main():
    """메인 실행 함수"""
    print("Zonos TTS 비동기 API 테스트 시작\n")
    
    # aiohttp 세션 생성
    async with aiohttp.ClientSession() as session:
        # 시스템 상태 확인
        await check_system_status(session)
        
        # S3 설정 (옵션)
        if S3_BUCKET_NAME and S3_BUCKET_NAME != "your-bucket-name":
            await configure_s3(session)
        
        # 각 테스트 실행
        await test_sync_mode(session)
        await test_async_tts(session)
        await test_multiple_async_tts(session)
        await test_task_management(session)
        
        # 최종 상태 확인
        await check_system_status(session)
    
    print("\n테스트 완료!")

if __name__ == "__main__":
    # 이벤트 루프 실행
    asyncio.run(main())