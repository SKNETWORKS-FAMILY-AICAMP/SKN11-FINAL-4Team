#!/bin/bash

# RunPod 파인튜닝 워커 Docker 이미지 빌드 및 푸시 스크립트

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 기본 설정
DOCKER_USERNAME="${DOCKER_USERNAME:-fallsnowing}"
IMAGE_NAME="exaone-finetuning-worker"
TAG="${1:-latest}"
FULL_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}:${TAG}"

echo -e "${GREEN}🚀 RunPod 파인튜닝 워커 Docker 이미지 빌드 시작${NC}"
echo "이미지: ${FULL_IMAGE_NAME}"

# 현재 디렉토리 확인
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
VLLM_DIR="$(dirname "$SCRIPT_DIR")"
WORKER_DIR="${VLLM_DIR}/runpod_workers/finetuning"

echo "작업 디렉토리: ${WORKER_DIR}"

# 작업 디렉토리로 이동
cd "${VLLM_DIR}" || exit 1

# Docker 빌드
echo -e "${YELLOW}📦 Docker 이미지 빌드 중...${NC}"
docker build \
    -f "${WORKER_DIR}/Dockerfile" \
    -t "${FULL_IMAGE_NAME}" \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Docker 빌드 실패${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker 빌드 성공${NC}"

# Docker Hub 로그인 확인
echo -e "${YELLOW}🔐 Docker Hub 로그인 확인...${NC}"
docker info | grep -q "Username: ${DOCKER_USERNAME}"
if [ $? -ne 0 ]; then
    echo "Docker Hub에 로그인이 필요합니다."
    docker login
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Docker Hub 로그인 실패${NC}"
        exit 1
    fi
fi

# Docker 이미지 푸시
echo -e "${YELLOW}📤 Docker Hub에 이미지 푸시 중...${NC}"
docker push "${FULL_IMAGE_NAME}"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Docker 푸시 실패${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker 이미지 푸시 성공!${NC}"
echo -e "${GREEN}🎉 완료! 이미지: ${FULL_IMAGE_NAME}${NC}"

# 이미지 크기 확인
echo -e "\n${YELLOW}📊 이미지 정보:${NC}"
docker images "${DOCKER_USERNAME}/${IMAGE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

# RunPod 배포 안내
echo -e "\n${GREEN}🚀 RunPod 배포 방법:${NC}"
echo "1. RunPod 콘솔에서 새 Serverless Endpoint 생성"
echo "2. Docker 이미지: ${FULL_IMAGE_NAME}"
echo "3. 컨테이너 디스크: 50GB 이상 권장"
echo "4. 환경 변수 설정:"
echo "   - BACKEND_POST_URL: 백엔드 파인튜닝 결과 수신 URL"
echo "   - HF_HOME: /workspace/huggingface"
echo "   - PYTORCH_CUDA_ALLOC_CONF: max_split_size_mb:512"