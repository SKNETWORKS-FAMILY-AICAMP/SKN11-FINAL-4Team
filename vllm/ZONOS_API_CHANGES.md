# Zonos TTS API 변경사항

## 변경 내용

### `/zonos/generate_tts_simple` 엔드포인트 변경

기존의 Form 데이터 방식에서 JSON 요청 방식으로 변경되었습니다.

#### 이전 (Form 데이터)
```bash
curl -X POST "http://localhost:8000/zonos/generate_tts_simple" \
  -F "text=안녕하세요"
```

#### 현재 (JSON 데이터)
```bash
curl -X POST "http://localhost:8000/zonos/generate_tts_simple" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "안녕하세요",
    "language": "ko",
    "speaking_rate": 22.0,
    "pitch_std": 40.0,
    "cfg_scale": 4.0
  }'
```

## 새로운 요청 형식

### SimpleTTSRequest 모델
```python
{
    "text": str,              # 필수: 변환할 텍스트
    "language": str = "ko",   # 선택: 언어 코드 (기본값: "ko")
    "speaking_rate": float = 22.0,  # 선택: 발화 속도 (기본값: 22.0)
    "pitch_std": float = 40.0,      # 선택: 피치 표준편차 (기본값: 40.0)
    "cfg_scale": float = 4.0        # 선택: CFG 스케일 (기본값: 4.0, 1.0은 사용 불가)
}
```

### 최소 요청 예제
```json
{
    "text": "안녕하세요"
}
```

### 전체 파라미터 요청 예제
```json
{
    "text": "안녕하세요. 저는 Zonos TTS 시스템입니다.",
    "language": "ko",
    "speaking_rate": 25.0,
    "pitch_std": 35.0,
    "cfg_scale": 3.5
}
```

## Python 클라이언트 예제

```python
import requests

# 기본 설정으로 요청
response = requests.post(
    "http://localhost:8000/zonos/generate_tts_simple",
    json={"text": "테스트 메시지입니다."}
)

# 모든 파라미터 지정
response = requests.post(
    "http://localhost:8000/zonos/generate_tts_simple",
    json={
        "text": "안녕하세요. 저는 Zonos TTS 시스템입니다.",
        "language": "ko",
        "speaking_rate": 20.0,
        "pitch_std": 45.0,
        "cfg_scale": 2.5
    }
)

if response.status_code == 200:
    result = response.json()
    print(f"오디오 파일: {result['audio_path']}")
    print(f"메시지: {result['message']}")
```

## 장점

1. **일관성**: 다른 API 엔드포인트와 동일한 JSON 형식 사용
2. **유연성**: 선택적 파라미터를 쉽게 추가 가능
3. **타입 안정성**: Pydantic 모델로 자동 검증
4. **문서화**: OpenAPI/Swagger에서 자동으로 문서화됨

## 주의사항

- `cfg_scale`은 1.0을 사용할 수 없습니다 (모델 제약사항)
- Content-Type 헤더를 `application/json`으로 설정해야 합니다
- 텍스트는 필수 파라미터입니다