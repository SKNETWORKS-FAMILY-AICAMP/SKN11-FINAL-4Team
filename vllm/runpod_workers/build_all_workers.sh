#!/bin/bash

# RunPod 모든 Worker 빌드 및 배포 스크립트

set -e  # 에러 발생시 즉시 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 설정
DOCKER_REGISTRY="your-registry.com"  # 여기에 실제 레지스트리 주소 입력

# Worker 목록
WORKERS=("tts" "embedding" "finetuning" "vllm_generation")

echo -e "${GREEN}🚀 RunPod Workers 빌드 및 배포 시작${NC}"

# 도커 레지스트리 설정 확인
if [ "$DOCKER_REGISTRY" == "your-registry.com" ]; then
    echo -e "${RED}❌ Docker 레지스트리 주소를 설정하세요!${NC}"
    echo "build_all_workers.sh 파일을 편집해서 DOCKER_REGISTRY 값을 설정하세요."
    exit 1
fi

# 빌드할 워커 선택
echo -e "${YELLOW}빌드할 워커를 선택하세요:${NC}"
echo "1) 전체 빌드"
echo "2) TTS Worker"
echo "3) Embedding Worker"
echo "4) Fine-tuning Worker"
echo "5) vLLM Generation Worker"
read -p "선택 (1-5): " choice

case $choice in
    1)
        SELECTED_WORKERS=("${WORKERS[@]}")
        ;;
    2)
        SELECTED_WORKERS=("tts")
        ;;
    3)
        SELECTED_WORKERS=("embedding")
        ;;
    4)
        SELECTED_WORKERS=("finetuning")
        ;;
    5)
        SELECTED_WORKERS=("vllm_generation")
        ;;
    *)
        echo -e "${RED}잘못된 선택입니다.${NC}"
        exit 1
        ;;
esac

# 각 워커 빌드
for worker in "${SELECTED_WORKERS[@]}"; do
    echo -e "\n${BLUE}=== $worker Worker 빌드 시작 ===${NC}"
    
    # 워커 디렉토리로 이동
    cd "$worker"
    
    # 이미지 이름 설정
    IMAGE_NAME="runpod-$worker-worker"
    IMAGE_TAG="latest"
    FULL_IMAGE_NAME="${DOCKER_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
    
    # TTS Worker의 경우 zonos 모듈 복사
    if [ "$worker" == "tts" ]; then
        echo -e "${YELLOW}📦 zonos 모듈 준비 중...${NC}"
        if [ -d "../../zonos" ]; then
            cp -r ../../zonos ./zonos_temp
        else
            echo -e "${RED}❌ ../../zonos 디렉토리를 찾을 수 없습니다${NC}"
            cd ..
            continue
        fi
    fi
    
    # Docker 이미지 빌드
    echo -e "${YELLOW}🔨 Docker 이미지 빌드 중: $IMAGE_NAME${NC}"
    
    # Dockerfile 이름 확인
    if [ -f "Dockerfile" ]; then
        docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
    else
        echo -e "${RED}❌ Dockerfile을 찾을 수 없습니다${NC}"
        cd ..
        continue
    fi
    
    # 빌드 성공 확인
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $worker Worker 빌드 성공${NC}"
        
        # Docker 레지스트리에 푸시
        echo -e "${YELLOW}📤 Docker 이미지를 레지스트리에 푸시 중...${NC}"
        docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${FULL_IMAGE_NAME}
        docker push ${FULL_IMAGE_NAME}
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ $worker Worker 푸시 성공${NC}"
        else
            echo -e "${RED}❌ $worker Worker 푸시 실패${NC}"
        fi
    else
        echo -e "${RED}❌ $worker Worker 빌드 실패${NC}"
    fi
    
    # 임시 파일 정리
    if [ "$worker" == "tts" ] && [ -d "zonos_temp" ]; then
        rm -rf ./zonos_temp
    fi
    
    # 부모 디렉토리로 돌아가기
    cd ..
done

# RunPod 배포 설정 생성
echo -e "\n${YELLOW}📝 RunPod 배포 설정 파일 생성 중...${NC}"

cat > runpod_deployments.json << EOF
{
  "workers": {
    "tts": {
      "name": "zonos-tts-worker",
      "dockerImage": "${DOCKER_REGISTRY}/runpod-tts-worker:latest",
      "gpuType": "RTX 3090",
      "gpuCount": 1,
      "containerDiskInGb": 20,
      "volumeInGb": 50,
      "minWorkers": 0,
      "maxWorkers": 10,
      "idleTimeout": 60
    },
    "embedding": {
      "name": "embedding-rag-worker",
      "dockerImage": "${DOCKER_REGISTRY}/runpod-embedding-worker:latest",
      "gpuType": "RTX 3090",
      "gpuCount": 1,
      "containerDiskInGb": 20,
      "volumeInGb": 30,
      "minWorkers": 0,
      "maxWorkers": 5,
      "idleTimeout": 120
    },
    "finetuning": {
      "name": "lora-finetuning-worker",
      "dockerImage": "${DOCKER_REGISTRY}/runpod-finetuning-worker:latest",
      "gpuType": "A100",
      "gpuCount": 1,
      "containerDiskInGb": 50,
      "volumeInGb": 100,
      "minWorkers": 0,
      "maxWorkers": 2,
      "idleTimeout": 300
    },
    "vllm_generation": {
      "name": "vllm-generation-worker",
      "dockerImage": "${DOCKER_REGISTRY}/runpod-vllm_generation-worker:latest",
      "gpuType": "A100",
      "gpuCount": 1,
      "containerDiskInGb": 50,
      "volumeInGb": 100,
      "minWorkers": 0,
      "maxWorkers": 5,
      "idleTimeout": 300
    }
  }
}
EOF

echo -e "\n${GREEN}✅ 빌드 및 배포 준비 완료!${NC}"
echo
echo "다음 단계:"
echo "1. RunPod 대시보드에 로그인하세요"
echo "2. 'Serverless' > 'New Endpoint' 클릭"
echo "3. runpod_deployments.json 파일의 설정을 참조하여 각 워커를 생성하세요"
echo
echo "생성된 Endpoint ID들을 백엔드 환경 변수에 설정하세요:"
echo "  export RUNPOD_TTS_ENDPOINT_ID=<your-tts-endpoint-id>"
echo "  export RUNPOD_EMBEDDING_ENDPOINT_ID=<your-embedding-endpoint-id>"
echo "  export RUNPOD_FINETUNING_ENDPOINT_ID=<your-finetuning-endpoint-id>"
echo "  export RUNPOD_VLLM_ENDPOINT_ID=<your-vllm-endpoint-id>"