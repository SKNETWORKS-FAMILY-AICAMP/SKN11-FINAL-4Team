#!/bin/bash

# RunPod TTS Worker 빌드 및 배포 스크립트

set -e  # 에러 발생시 즉시 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 설정
DOCKER_REGISTRY="your-registry.com"  # 여기에 실제 레지스트리 주소 입력
IMAGE_NAME="zonos-tts-worker"
IMAGE_TAG="latest"
FULL_IMAGE_NAME="${DOCKER_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"

echo -e "${GREEN}🚀 RunPod TTS Worker 빌드 및 배포 시작${NC}"

# 1. zonos 모듈 복사 준비
echo -e "${YELLOW}📦 zonos 모듈 준비 중...${NC}"
if [ ! -d "../zonos" ]; then
    echo -e "${RED}❌ ../zonos 디렉토리를 찾을 수 없습니다${NC}"
    exit 1
fi

# zonos 모듈을 빌드 컨텍스트로 복사
cp -r ../zonos ./zonos_temp

# 2. Docker 이미지 빌드
echo -e "${YELLOW}🔨 Docker 이미지 빌드 중...${NC}"
docker build -f Dockerfile.tts -t ${IMAGE_NAME}:${IMAGE_TAG} .

# 3. 로컬 테스트 (선택사항)
read -p "로컬에서 테스트를 실행하시겠습니까? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}🧪 로컬 테스트 실행 중...${NC}"
    docker run --rm --gpus all ${IMAGE_NAME}:${IMAGE_TAG} python3 -c "
import torch
print('PyTorch version:', torch.__version__)
print('CUDA available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('CUDA device:', torch.cuda.get_device_name(0))
"
fi

# 4. Docker 레지스트리에 푸시
echo -e "${YELLOW}📤 Docker 이미지를 레지스트리에 푸시 중...${NC}"
docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${FULL_IMAGE_NAME}
docker push ${FULL_IMAGE_NAME}

# 5. 임시 파일 정리
echo -e "${YELLOW}🧹 임시 파일 정리 중...${NC}"
rm -rf ./zonos_temp

# 6. RunPod 배포 설정 생성
echo -e "${YELLOW}📝 RunPod 배포 설정 파일 생성 중...${NC}"
cat > runpod_deployment.json << EOF
{
  "name": "zonos-tts-worker",
  "dockerImage": "${FULL_IMAGE_NAME}",
  "gpuType": "RTX 3090",
  "gpuCount": 1,
  "containerDiskInGb": 20,
  "volumeInGb": 50,
  "minWorkers": 0,
  "maxWorkers": 10,
  "idleTimeout": 60,
  "env": {
    "CUDA_VISIBLE_DEVICES": "0",
    "HF_HOME": "/runpod-volume/models",
    "TRANSFORMERS_CACHE": "/runpod-volume/models"
  },
  "volumeMounts": [
    {
      "name": "models",
      "mountPath": "/runpod-volume/models"
    }
  ]
}
EOF

echo -e "${GREEN}✅ 빌드 및 배포 준비 완료!${NC}"
echo
echo "다음 단계:"
echo "1. RunPod 대시보드에 로그인하세요"
echo "2. 'Serverless' > 'New Endpoint' 클릭"
echo "3. 다음 정보로 엔드포인트 생성:"
echo "   - Docker Image: ${FULL_IMAGE_NAME}"
echo "   - GPU Type: RTX 3090 (또는 사용 가능한 GPU)"
echo "   - Container Disk: 20 GB"
echo "   - Volume: 50 GB (모델 캐싱용)"
echo "4. 생성된 Endpoint ID를 백엔드 환경 변수에 설정:"
echo "   export RUNPOD_TTS_ENDPOINT_ID=<your-endpoint-id>"
echo
echo -e "${YELLOW}📄 상세 설정은 runpod_deployment.json 파일을 참조하세요${NC}"