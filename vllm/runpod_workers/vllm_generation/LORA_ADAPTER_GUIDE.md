# vLLM Generation Worker - LoRA 어댑터 동적 로드 가이드

## 개요
vLLM Generation Worker는 백엔드 요청에 따라 LoRA 어댑터를 동적으로 로드할 수 있습니다. 어댑터는 고정된 경로(`/app/lora_adapters`)에 저장되며, 백엔드에서 어댑터 이름만 전달하면 자동으로 로드됩니다.

## 어댑터 경로 구조
```
/app/lora_adapters/
├── influencer_001/
│   ├── adapter_config.json
│   ├── adapter_model.safetensors
│   └── tokenizer_config.json
├── influencer_002/
│   ├── adapter_config.json
│   ├── adapter_model.safetensors
│   └── tokenizer_config.json
└── ...
```

## 사용 방법

### 1. 어댑터 이름만으로 로드
```json
{
  "prompt": "안녕하세요",
  "lora_adapter": "influencer_001"
}
```

### 2. 딕셔너리 형태로 로드
```json
{
  "prompt": "안녕하세요",
  "lora_adapter": {
    "name": "custom_influencer",
    "path": "influencer_001"
  }
}
```

### 3. Hugging Face Hub에서 로드
```json
{
  "prompt": "안녕하세요",
  "lora_adapter": "hf://username/repo-name"
}
```

### 4. 절대 경로로 로드
```json
{
  "prompt": "안녕하세요",
  "lora_adapter": "/custom/path/to/adapter"
}
```

## 환경 변수
- `LORA_ADAPTERS_BASE_PATH`: LoRA 어댑터가 저장된 기본 경로 (기본값: `/app/lora_adapters`)

## 어댑터 배포 방법

### 1. 빌드 시 포함
Dockerfile에 어댑터를 복사:
```dockerfile
COPY lora_adapters /app/lora_adapters
```

### 2. 볼륨 마운트
RunPod 배포 시 볼륨을 마운트:
```yaml
volumes:
  - name: lora-adapters
    path: /app/lora_adapters
```

### 3. 런타임 다운로드
백엔드에서 Hugging Face Hub URL을 전달하여 런타임에 다운로드

## 주의사항
1. 어댑터는 한 번 로드되면 메모리에 캐시됩니다.
2. 동일한 어댑터를 여러 번 요청해도 재로드되지 않습니다.
3. 어댑터 경로에 `adapter_config.json` 파일이 반드시 있어야 합니다.
4. GPU 메모리 제한으로 최대 5개의 어댑터까지 동시 로드 가능합니다.

## 에러 처리
- 어댑터를 찾을 수 없는 경우: `FileNotFoundError`
- `adapter_config.json`이 없는 경우: `FileNotFoundError`
- GPU 메모리 부족: `RuntimeError`