# Zonos TTS Emotion API 가이드

Zonos TTS API에서 감정(emotion)을 제어하는 방법을 설명합니다.

## 감정 벡터 개요

감정은 8차원 벡터로 표현되며, 각 차원은 다음 감정을 나타냅니다:
- [neutral, happy, sad, angry, fearful, disgusted, surprised, contempt]

## 사용 방법

### 1. 미리 정의된 감정 사용 (emotion_name)

가장 간단한 방법은 `emotion_name` 파라미터를 사용하는 것입니다:

```json
{
  "text": "안녕하세요, 반갑습니다.",
  "language": "ko",
  "emotion_name": "happy"
}
```

사용 가능한 감정 이름:
- `neutral`: 중립적인 감정
- `happy`: 행복한 감정
- `sad`: 슬픈 감정
- `angry`: 화난 감정
- `fearful`: 두려운 감정
- `disgusted`: 역겨운 감정
- `surprised`: 놀란 감정
- `contempt`: 경멸하는 감정

### 2. 커스텀 감정 벡터 사용

더 세밀한 제어를 원한다면 직접 8차원 벡터를 지정할 수 있습니다:

```json
{
  "text": "안녕하세요, 반갑습니다.",
  "language": "ko",
  "emotion": [0.1, 0.6, 0.05, 0.05, 0.05, 0.05, 0.1, 0.05]
}
```

**주의사항:**
- 모든 값은 0과 1 사이여야 합니다
- 정확히 8개의 값이 필요합니다
- 벡터의 합이 1일 필요는 없습니다

### 3. 혼합 감정 표현

여러 감정을 혼합하여 복잡한 감정을 표현할 수 있습니다:

```json
{
  "text": "정말 놀라운 소식이네요!",
  "language": "ko",
  "emotion": [0.1, 0.4, 0.0, 0.0, 0.0, 0.0, 0.4, 0.1]
}
```
위 예시는 happy(0.4)와 surprised(0.4)가 혼합된 감정입니다.

## API 엔드포인트

### 사용 가능한 감정 목록 조회

```bash
GET /zonos/emotions
```

응답 예시:
```json
{
  "emotions": {
    "neutral": [0.3077, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.2564, 0.3077],
    "happy": [0.0256, 0.5897, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.3077],
    ...
  },
  "description": {
    "neutral": "중립적인 감정",
    "happy": "행복한 감정",
    ...
  }
}
```

### TTS 생성 예시

1. **기본 TTS (감정 이름 사용)**
```bash
curl -X POST http://localhost:8000/zonos/generate_tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "오늘은 정말 행복한 날이에요!",
    "language": "ko",
    "emotion_name": "happy"
  }'
```

2. **커스텀 감정 벡터 사용**
```bash
curl -X POST http://localhost:8000/zonos/generate_tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "이 소식을 들으니 복잡한 감정이 드네요.",
    "language": "ko",
    "emotion": [0.2, 0.1, 0.3, 0.1, 0.1, 0.0, 0.1, 0.1]
  }'
```

3. **음성 클로닝과 함께 사용**
```bash
curl -X POST http://localhost:8000/zonos/generate_tts_with_voice \
  -H "Content-Type: application/json" \
  -d '{
    "text": "음성 클로닝과 감정을 함께 사용합니다.",
    "language": "ko",
    "emotion_name": "happy",
    "voice_data_base64": "..."
  }'
```

## 팁과 권장사항

1. **감정 강도 조절**: 극단적인 값(0.9 이상)보다는 적당한 값(0.3-0.7)을 사용하는 것이 자연스럽습니다.

2. **감정 전환**: 긴 텍스트에서 감정을 변경하려면 여러 번 API를 호출하여 오디오를 결합하세요.

3. **테스트**: 먼저 미리 정의된 감정으로 테스트한 후, 필요에 따라 커스텀 벡터를 조정하세요.

## 오류 처리

감정 벡터가 잘못된 경우 다음과 같은 오류가 발생합니다:

```json
{
  "detail": [
    {
      "loc": ["body", "emotion"],
      "msg": "emotion은 8개의 float 값으로 구성되어야 합니다.",
      "type": "value_error"
    }
  ]
}
```