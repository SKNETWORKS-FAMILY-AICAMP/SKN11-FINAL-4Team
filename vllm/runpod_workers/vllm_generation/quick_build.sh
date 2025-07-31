#!/bin/bash

# Quick Docker Build and Push Script
# 간단한 버전 - 확인 과정 없이 바로 빌드/푸시

set -e

DOCKER_IMAGE="fallsnowing/exaone-vllm-worker"
VERSION_TAG=${1:-"latest"}
FULL_IMAGE_NAME="${DOCKER_IMAGE}:${VERSION_TAG}"

echo "🚀 빌드 시작: ${FULL_IMAGE_NAME}"

# Docker 빌드
export DOCKER_BUILDKIT=1
docker build --tag "${FULL_IMAGE_NAME}" .

echo "✅ 빌드 완료"

# 푸시
echo "📤 푸시 시작..."
docker push "${FULL_IMAGE_NAME}"

echo "🎉 완료! 이미지: ${FULL_IMAGE_NAME}"