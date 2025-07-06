# RunPod + ComfyUI 이미지 생성 워크플로우 API 키 설정 가이드

## 현재 상태
- **OpenAI**: Mock 모드 (실제 API 키 없음)
- **ComfyUI**: Mock 모드 (실제 서버 연결 없음)  
- **RunPod**: Mock 모드 (실제 API 키 없음)

## 완전한 이미지 생성 워크플로우

### 전체 흐름:
1. **사용자 요청**: 한글/영문 프롬프트 입력 → DB 저장
2. **RunPod 서버 시작**: ComfyUI가 설치된 GPU 인스턴스 생성
3. **서버 준비 대기**: ComfyUI API 응답 확인
4. **프롬프트 최적화**: OpenAI로 ComfyUI 최적화된 영문 프롬프트 생성
5. **이미지 생성**: 최적화된 프롬프트로 ComfyUI 워크플로우 실행
6. **결과 반환**: 생성된 이미지를 Base64 또는 URL로 반환
7. **자동 정리**: 작업 완료 후 RunPod 서버 자동 종료

## 실제 API 키 설정 방법

### 1. 환경 변수 설정

백엔드 폴더에 `.env` 파일을 생성하고 다음을 추가하세요:

```bash
# OpenAI API 설정 (필수 - 프롬프트 최적화용)
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4
OPENAI_MAX_TOKENS=2000

# RunPod 설정 (권장 - 클라우드 GPU 사용)
RUNPOD_API_KEY=your-runpod-api-key-here
RUNPOD_TEMPLATE_ID=your-comfyui-template-id
RUNPOD_GPU_TYPE=NVIDIA RTX A6000
RUNPOD_MAX_WORKERS=1
RUNPOD_IDLE_TIMEOUT=300

# ComfyUI 설정 (로컬 GPU 사용 시)
COMFYUI_SERVER_URL=http://127.0.0.1:8188
COMFYUI_API_KEY=your-comfyui-api-key-if-needed
COMFYUI_TIMEOUT=300
```

### 2. OpenAI API 키 발급

1. [OpenAI 플랫폼](https://platform.openai.com/)에 로그인
2. API Keys 메뉴에서 새 키 생성
3. 생성된 키를 `.env` 파일의 `OPENAI_API_KEY`에 입력

### 3. RunPod API 키 발급 (권장)

1. [RunPod](https://runpod.io/)에 계정 생성
2. API Keys 메뉴에서 새 키 생성
3. ComfyUI 템플릿 생성 또는 기존 템플릿 ID 확인
4. 생성된 키와 템플릿 ID를 `.env`에 입력

#### RunPod 템플릿 설정:
- **Container Image**: `runpod/comfyui:latest`
- **Container Disk**: 50GB 이상
- **Ports**: `8188/http`
- **GPU**: RTX A6000 또는 RTX 4090 권장

### 4. ComfyUI 로컬 설정 (대안)

#### 로컬 ComfyUI 설치 (고성능 GPU 필요)
```bash
# ComfyUI 설치
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip install -r requirements.txt

# 실행
python main.py --listen
```

#### 필요 모델 다운로드:
- **Base Model**: SD 1.5, SDXL, 또는 커스텀 모델
- **VAE**: vae-ft-mse-840000-ema-pruned.ckpt
- **Upscaler**: RealESRGAN_x4plus.pth (선택사항)

### 5. 의존성 패키지 설치

```bash
cd backend
pip install openai aiohttp requests
```

### 5. 서버 재시작

환경 변수 변경 후 백엔드 서버를 재시작해야 합니다:

```bash
cd backend
python run.py
```

## 동작 확인

### Mock 모드에서 실제 API 모드로 전환 확인

백엔드 서버 시작 시 로그를 확인하세요:

```
# Mock 모드 (API 키 없음)
OpenAI Service initialized (Mock mode: True)
ComfyUI Service initialized (Mock mode: True)

# 실제 API 모드 (API 키 있음)
OpenAI client initialized with API key
OpenAI Service initialized (Mock mode: False)
ComfyUI Service initialized (Mock mode: False)
```

### API 테스트

### 새로운 통합 워크플로우 테스트:

```bash
# 완전한 이미지 생성 워크플로우 테스트
curl -X POST "http://localhost:8000/api/v1/boards/generate-image-full" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "original_prompt": "아름다운 고양이 사진",
    "style": "realistic",
    "quality_level": "high",
    "width": 1024,
    "height": 1024,
    "steps": 20
  }'

# 생성 상태 확인
curl -X GET "http://localhost:8000/api/v1/boards/generate-image-status/{request_id}" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 개별 서비스 테스트:

- OpenAI 테스트: `POST /api/v1/boards/test-openai`
- ComfyUI 테스트: `POST /api/v1/boards/test-comfyui`

## 주의사항

1. **API 키 보안**: `.env` 파일을 절대 git에 커밋하지 마세요
2. **비용 관리**: OpenAI API는 사용량에 따라 요금이 부과됩니다
3. **Rate Limit**: API 호출 한도를 초과하지 않도록 주의하세요
4. **ComfyUI 모델**: ComfyUI 사용 시 필요한 모델 파일들이 다운로드되어야 합니다

## 문제 해결

### OpenAI API 오류
- API 키가 유효한지 확인
- 계정에 충분한 크레딧이 있는지 확인
- 모델 접근 권한이 있는지 확인

### ComfyUI 연결 오류
- ComfyUI 서버가 실행 중인지 확인
- 포트 번호가 올바른지 확인 (기본 8188)
- 방화벽 설정 확인

## Mock 모드 유지

실제 API 키 없이 개발하려면 `.env` 파일에서 해당 키들을 제거하거나 빈 값으로 두면 됩니다. 이 경우 Mock 데이터가 반환됩니다.