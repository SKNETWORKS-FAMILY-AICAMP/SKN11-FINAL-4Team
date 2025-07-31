#!/bin/bash

# Docker Build and Push Script for EXAONE vLLM Worker
# 사용법: ./build_and_push.sh [version_tag]

set -e  # 에러 발생 시 스크립트 중단

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수들
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 기본 설정
DOCKER_IMAGE="fallsnowing/exaone-vllm-worker"
VERSION_TAG=${1:-"latest"}
FULL_IMAGE_NAME="${DOCKER_IMAGE}:${VERSION_TAG}"

# 현재 디렉토리 확인
if [ ! -f "Dockerfile" ] || [ ! -f "generation_worker.py" ]; then
    log_error "Dockerfile 또는 generation_worker.py가 현재 디렉토리에 없습니다."
    log_error "vllm_generation 디렉토리에서 실행해주세요."
    exit 1
fi

log_info "🚀 Docker 이미지 빌드 및 푸시를 시작합니다"
log_info "📦 이미지명: ${FULL_IMAGE_NAME}"

# Docker가 실행 중인지 확인
if ! docker info > /dev/null 2>&1; then
    log_error "Docker가 실행되고 있지 않습니다. Docker를 시작해주세요."
    exit 1
fi

# Docker 로그인 확인
log_info "🔐 Docker Hub 로그인 상태 확인 중..."
if ! docker system info | grep -q "Username:"; then
    log_warning "Docker Hub에 로그인되어 있지 않습니다."
    log_info "Docker Hub에 로그인해주세요:"
    docker login
fi

# GPU 지원 확인
if command -v nvidia-smi > /dev/null 2>&1; then
    log_info "🎮 NVIDIA GPU 감지됨"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits | head -1
else
    log_warning "⚠️ NVIDIA GPU가 감지되지 않았습니다. CPU 빌드로 진행합니다."
fi

# 빌드 시작 시간 기록
BUILD_START_TIME=$(date +%s)

log_info "🔨 Docker 이미지를 빌드합니다..."
log_info "   이 과정은 10-30분 정도 소요될 수 있습니다."

# Docker 빌드 (BuildKit 활성화)
export DOCKER_BUILDKIT=1
if docker build \
    --tag "${FULL_IMAGE_NAME}" \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    --progress=plain \
    .; then
    
    # 빌드 완료 시간 계산
    BUILD_END_TIME=$(date +%s)
    BUILD_DURATION=$((BUILD_END_TIME - BUILD_START_TIME))
    BUILD_MINUTES=$((BUILD_DURATION / 60))
    BUILD_SECONDS=$((BUILD_DURATION % 60))
    
    log_success "✅ Docker 이미지 빌드 완료! (소요시간: ${BUILD_MINUTES}분 ${BUILD_SECONDS}초)"
else
    log_error "❌ Docker 이미지 빌드 실패"
    exit 1
fi

# 이미지 크기 확인
IMAGE_SIZE=$(docker images "${FULL_IMAGE_NAME}" --format "table {{.Size}}" | tail -n 1)
log_info "📊 이미지 크기: ${IMAGE_SIZE}"

# 이미지 테스트 (간단한 import 테스트)
log_info "🧪 이미지 테스트 중..."
if docker run --rm --gpus all "${FULL_IMAGE_NAME}" python3 -c "
import vllm
import torch
import transformers
print('✅ 모든 라이브러리 import 성공')
print(f'🔧 vLLM 버전: {vllm.__version__}')
print(f'🔧 PyTorch 버전: {torch.__version__}')
print(f'🔧 Transformers 버전: {transformers.__version__}')
if torch.cuda.is_available():
    print(f'🎮 CUDA 사용 가능: {torch.cuda.get_device_name(0)}')
else:
    print('⚠️ CUDA 사용 불가 (CPU 모드)')
"; then
    log_success "✅ 이미지 테스트 통과"
else
    log_error "❌ 이미지 테스트 실패"
    exit 1
fi

# 푸시 여부 확인
read -p "$(echo -e ${YELLOW}[CONFIRM]${NC} Docker Hub에 이미지를 푸시하시겠습니까? [y/N]: )" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "📤 Docker Hub에 이미지를 푸시합니다..."
    
    PUSH_START_TIME=$(date +%s)
    
    if docker push "${FULL_IMAGE_NAME}"; then
        PUSH_END_TIME=$(date +%s)
        PUSH_DURATION=$((PUSH_END_TIME - PUSH_START_TIME))
        PUSH_MINUTES=$((PUSH_DURATION / 60))
        PUSH_SECONDS=$((PUSH_DURATION % 60))
        
        log_success "✅ Docker 이미지 푸시 완료! (소요시간: ${PUSH_MINUTES}분 ${PUSH_SECONDS}초)"
        log_success "🌐 이미지 URL: https://hub.docker.com/r/${DOCKER_IMAGE}"
        
        # latest 태그도 푸시 (버전 태그가 latest가 아닌 경우)
        if [ "${VERSION_TAG}" != "latest" ]; then
            read -p "$(echo -e ${YELLOW}[CONFIRM]${NC} latest 태그도 함께 푸시하시겠습니까? [y/N]: )" -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                log_info "📤 latest 태그로도 푸시합니다..."
                docker tag "${FULL_IMAGE_NAME}" "${DOCKER_IMAGE}:latest"
                docker push "${DOCKER_IMAGE}:latest"
                log_success "✅ latest 태그 푸시 완료"
            fi
        fi
    else
        log_error "❌ Docker 이미지 푸시 실패"
        exit 1
    fi
else
    log_info "ℹ️ 푸시를 건너뜁니다. 로컬에서만 사용 가능합니다."
fi

# 총 소요 시간 계산
TOTAL_END_TIME=$(date +%s)
TOTAL_DURATION=$((TOTAL_END_TIME - BUILD_START_TIME))
TOTAL_MINUTES=$((TOTAL_DURATION / 60))
TOTAL_SECONDS=$((TOTAL_DURATION % 60))

log_success "🎉 작업 완료!"
log_info "📊 총 소요시간: ${TOTAL_MINUTES}분 ${TOTAL_SECONDS}초"
log_info "🐳 사용 방법:"
echo "   docker run --gpus all -p 8000:8000 ${FULL_IMAGE_NAME}"
echo ""
log_info "🚀 RunPod에서 사용:"
echo "   Image: ${FULL_IMAGE_NAME}"
echo "   Container Disk: 50GB+"
echo "   GPU: RTX 4090 또는 A100 권장"
echo ""

# 정리 옵션
read -p "$(echo -e ${YELLOW}[CONFIRM]${NC} 빌드 캐시를 정리하시겠습니까? [y/N]: )" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "🧹 빌드 캐시 정리 중..."
    docker builder prune -f
    log_success "✅ 빌드 캐시 정리 완료"
fi

log_success "🏁 모든 작업이 완료되었습니다!"