# Zonos TTS Async Integration Guide

이 문서는 vLLM 프로젝트에 통합된 비동기 Zonos TTS (Text-to-Speech) 기능에 대해 설명합니다.

## 개요

Zonos는 Zyphra에서 개발한 고품질 한국어 TTS 모델입니다. 이 통합을 통해 vLLM API에서 직접 TTS 기능을 사용할 수 있습니다.

## 주요 기능

- 한국어 텍스트를 자연스러운 음성으로 변환
- 음성 클로닝 지원 (참조 음성 파일 사용)
- 말하기 속도, 피치 등 세부 조정 가능
- **비동기 처리 지원** - 백그라운드 작업으로 대량 처리 가능
- **작업 상태 추적** - 실시간 진행률 모니터링
- **S3 자동 업로드** - 생성된 파일 자동 클라우드 저장
- RESTful API 엔드포인트 제공

## API 엔드포인트

### 1. 간단한 TTS 생성
```
POST /zonos/generate_tts_simple
```

**Parameters:**
- `text` (string, required): 변환할 텍스트

**Example:**
```bash
curl -X POST "http://localhost:8000/zonos/generate_tts_simple" \
  -F "text=안녕하세요. 테스트입니다."
```

### 2. 고급 TTS 생성 (비동기)
```
POST /zonos/generate_tts
```

**Request Body:**
```json
{
  "text": "변환할 텍스트",
  "language": "ko",
  "speaking_rate": 22.0,
  "pitch_std": 40.0,
  "cfg_scale": 4.0,
  "output_filename": "output.wav",
  "async_mode": true,
  "upload_to_s3": true,
  "s3_folder_prefix": "zonos-tts",
  "s3_public_read": false
}
```

**Parameters:**
- `text` (string, required): 변환할 텍스트
- `language` (string, default: "ko"): 언어 코드
- `speaking_rate` (float, default: 22.0): 말하기 속도
- `pitch_std` (float, default: 40.0): 피치 표준편차
- `cfg_scale` (float, default: 4.0): CFG 스케일
- `output_filename` (string, optional): 출력 파일명
- `async_mode` (bool, default: true): 비동기 처리 여부
- `upload_to_s3` (bool, default: false): S3 업로드 여부
- `s3_folder_prefix` (string, default: "zonos-tts"): S3 폴더 prefix
- `s3_public_read` (bool, default: false): Public URL 생성 여부

**비동기 응답:**
```json
{
  "task_id": "uuid-string",
  "status": "pending",
  "message": "TTS 생성 작업이 시작되었습니다..."
}
```

### 3. 음성 클로닝 TTS
```
POST /zonos/generate_tts (with voice file)
```

**Request:**
- Multipart form data with voice file
- JSON parameters as form fields

**Example:**
```bash
curl -X POST "http://localhost:8000/zonos/generate_tts" \
  -F "voice_file=@/path/to/voice.wav" \
  -F "text=변환할 텍스트" \
  -F "language=ko" \
  -F "speaking_rate=22.0"
```

### 4. TTS 파일 다운로드
```
GET /zonos/download_tts/{filename}
```

### 5. 작업 상태 확인
```
GET /zonos/task_status/{task_id}
```

**응답:**
```json
{
  "task_id": "uuid-string",
  "status": "processing",
  "progress": 70,
  "message": "오디오 생성 중...",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:30"
}
```

### 6. 작업 목록 조회
```
GET /zonos/tasks?status=completed&limit=10
```

### 7. 작업 삭제
```
DELETE /zonos/task/{task_id}
```

### 8. Zonos 상태 확인
```
GET /zonos/zonos_status
```

**응답:**
```json
{
  "model_loaded": true,
  "device": "cuda",
  "cuda_available": true,
  "active_tasks": 2,
  "pending_tasks": 5,
  "total_tasks": 15
}
```

## 설치 및 설정

### 필수 의존성

다음 패키지들이 추가로 필요합니다:
```bash
pip install inflect kanjize phonemizer sudachidict-full sudachipy torchaudio soundfile
```

### 선택적 의존성 (성능 향상)

Mamba 모델을 사용하려면:
```bash
pip install flash-attn mamba-ssm causal-conv1d
```

## 사용 예제

### Python 클라이언트 예제

```python
import requests

# 간단한 TTS 생성
response = requests.post(
    "http://localhost:8000/zonos/generate_tts_simple",
    data={"text": "안녕하세요. Zonos TTS입니다."}
)
result = response.json()
print(f"생성된 오디오: {result['audio_path']}")

# 고급 설정으로 TTS 생성
request_data = {
    "text": "더 자연스러운 음성을 생성합니다.",
    "language": "ko",
    "speaking_rate": 20.0,
    "pitch_std": 35.0,
    "cfg_scale": 4.5
}
response = requests.post(
    "http://localhost:8000/zonos/generate_tts",
    json=request_data
)
```

## 주의사항

1. **GPU 메모리**: Zonos 모델은 GPU에서 실행될 때 최적의 성능을 보입니다. 충분한 GPU 메모리가 필요합니다.

2. **첫 실행 시간**: 처음 모델을 로드할 때 시간이 걸릴 수 있습니다. 모델은 Hugging Face에서 자동으로 다운로드됩니다.

3. **음성 파일 형식**: 음성 클로닝을 위한 참조 음성은 WAV 형식이어야 합니다.

4. **임시 파일**: 생성된 오디오 파일은 `/tmp/zonos_tts/` 디렉토리에 저장됩니다. 주기적인 정리가 필요할 수 있습니다.

## 문제 해결

### 모델 로드 실패
- GPU 드라이버와 CUDA 버전을 확인하세요
- 충분한 메모리가 있는지 확인하세요
- 인터넷 연결을 확인하세요 (모델 다운로드)

### 음성 생성 실패
- 입력 텍스트가 비어있지 않은지 확인하세요
- 특수 문자나 이모지가 포함되어 있지 않은지 확인하세요
- 로그를 확인하여 상세한 오류 메시지를 확인하세요

## S3 통합

### S3 설정

S3 업로드 기능을 사용하려면 먼저 S3를 구성해야 합니다:

```bash
curl -X POST "http://localhost:8000/zonos/configure_s3" \
  -H "Content-Type: application/json" \
  -d '{
    "bucket_name": "your-bucket-name",
    "region_name": "ap-northeast-2",
    "aws_access_key_id": "your-access-key",
    "aws_secret_access_key": "your-secret-key"
  }'
```

또는 환경 변수로 설정:
```bash
export AWS_S3_BUCKET_NAME=your-bucket-name
export AWS_REGION=ap-northeast-2
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
```

### S3 업로드 포함 TTS 생성

```json
{
  "text": "S3에 업로드할 음성",
  "language": "ko",
  "upload_to_s3": true,
  "s3_folder_prefix": "zonos-tts/samples",
  "s3_public_read": true
}
```

응답 예시:
```json
{
  "audio_path": "/tmp/zonos_tts/output.wav",
  "message": "TTS 생성이 완료되었습니다.",
  "s3_info": {
    "success": true,
    "bucket": "your-bucket-name",
    "key": "zonos-tts/samples/output.wav",
    "url": "https://your-bucket-name.s3.ap-northeast-2.amazonaws.com/zonos-tts/samples/output.wav",
    "region": "ap-northeast-2"
  }
}
```

### S3 관련 엔드포인트

- `POST /zonos/configure_s3`: S3 설정
- `GET /zonos/s3_status`: S3 연결 상태 확인

## 비동기 처리 예제

### Python 비동기 클라이언트

```python
import asyncio
import aiohttp

async def generate_tts_async():
    async with aiohttp.ClientSession() as session:
        # TTS 생성 시작
        async with session.post(
            "http://localhost:8000/zonos/generate_tts",
            json={
                "text": "비동기로 처리되는 TTS입니다.",
                "async_mode": True,
                "upload_to_s3": True
            }
        ) as response:
            result = await response.json()
            task_id = result["task_id"]
        
        # 작업 상태 확인
        while True:
            async with session.get(
                f"http://localhost:8000/zonos/task_status/{task_id}"
            ) as response:
                status = await response.json()
                
                print(f"진행률: {status['progress']}%")
                
                if status["status"] == "completed":
                    print(f"완료! S3 URL: {status['result']['s3_info']['url']}")
                    break
                elif status["status"] == "failed":
                    print(f"실패: {status['error']}")
                    break
            
            await asyncio.sleep(1)

# 실행
asyncio.run(generate_tts_async())
```

### 다중 작업 동시 처리

```python
async def batch_tts_generation(texts):
    async with aiohttp.ClientSession() as session:
        # 모든 작업 동시 시작
        tasks = []
        for text in texts:
            task = session.post(
                "http://localhost:8000/zonos/generate_tts",
                json={"text": text, "async_mode": True}
            )
            tasks.append(task)
        
        # 모든 응답 수집
        responses = await asyncio.gather(*tasks)
        task_ids = [await r.json() for r in responses]
        
        # 결과 확인...
```

## 성능 최적화

1. **동시 작업 수**: ThreadPoolExecutor의 max_workers 조정
2. **GPU 메모리**: 여러 작업 동시 처리 시 GPU 메모리 관리
3. **작업 정리**: 24시간 이상 된 완료 작업 자동 삭제

## 추가 개발 아이디어

1. **WebSocket 지원**: 실시간 진행률 업데이트
2. **우선순위 큐**: 중요 작업 우선 처리
3. **작업 재시도**: 실패한 작업 자동 재시도
4. **배치 API**: 여러 텍스트 일괄 처리 엔드포인트
5. **스트리밍**: 실시간 음성 스트리밍 지원
6. **캐싱**: Redis 기반 결과 캐싱
7. **모니터링**: Prometheus 메트릭 추가