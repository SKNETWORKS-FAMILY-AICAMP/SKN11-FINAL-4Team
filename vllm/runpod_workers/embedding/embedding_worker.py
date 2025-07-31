"""
RunPod Serverless Worker for Embeddings (RAG)
다국어 임베딩 생성을 위한 Worker
"""
import os
import sys
import logging
import json
import torch
import traceback
import numpy as np
from typing import Dict, Any, List, Optional, Union
import base64

import runpod
from sentence_transformers import SentenceTransformer

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 전역 모델 변수
embedding_model = None
device = None

# 지원 모델 목록
SUPPORTED_MODELS = {
    "bge-m3": "BAAI/bge-m3",
    "multilingual-e5-large-instruct": "intfloat/multilingual-e5-large-instruct",
    "gte-multilingual-base": "Alibaba-NLP/gte-multilingual-base",
    "distiluse-base-multilingual": "sentence-transformers/distiluse-base-multilingual-cased-v1",
    "xlm-roberta-large": "sentence-transformers/xlm-r-100langs-bert-base-nli-stsb-mean-tokens"
}

DEFAULT_MODEL = "BAAI/bge-m3"

def initialize_model(model_name: str = DEFAULT_MODEL):
    """모델 초기화"""
    global embedding_model, device
    
    if embedding_model is not None:
        # 이미 로드된 모델이 동일한 경우 재사용
        if hasattr(embedding_model, 'model_name') and embedding_model.model_name == model_name:
            return
        # 다른 모델인 경우 기존 모델 정리
        del embedding_model
        torch.cuda.empty_cache()
    
    logger.info(f"🔧 임베딩 모델 초기화 시작: {model_name}")
    
    # GPU 설정
    if torch.cuda.is_available():
        device = torch.device("cuda:0")
        logger.info(f"🖥️ GPU 사용: {torch.cuda.get_device_name(0)}")
        logger.info(f"📊 GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    else:
        device = torch.device("cpu")
        logger.warning("⚠️ CUDA를 사용할 수 없습니다. CPU를 사용합니다.")
    
    # 토크나이저 병렬화 비활성화
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    
    # 모델 로드
    try:
        embedding_model = SentenceTransformer(model_name, device=device)
        embedding_model.model_name = model_name  # 모델 이름 저장
        logger.info(f"✅ 임베딩 모델 초기화 완료: {model_name}")
        logger.info(f"📏 임베딩 차원: {embedding_model.get_sentence_embedding_dimension()}")
    except Exception as e:
        logger.error(f"❌ 모델 로드 실패: {str(e)}")
        raise

def validate_input(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """입력 데이터 검증"""
    # 필수 필드 확인
    if "texts" not in job_input:
        raise ValueError("texts 필드는 필수입니다.")
    
    texts = job_input["texts"]
    
    # 텍스트 타입 확인 및 변환
    if isinstance(texts, str):
        texts = [texts]
    elif not isinstance(texts, list):
        raise ValueError("texts는 문자열 또는 문자열 리스트여야 합니다.")
    
    # 빈 텍스트 확인
    if len(texts) == 0:
        raise ValueError("texts는 비어있을 수 없습니다.")
    
    # 모델 이름 처리
    model_name = job_input.get("model_name", DEFAULT_MODEL)
    if model_name in SUPPORTED_MODELS:
        model_name = SUPPORTED_MODELS[model_name]
    
    # 검증된 입력 반환
    validated = {
        "texts": texts,
        "model_name": model_name,
        "batch_size": int(job_input.get("batch_size", 32)),
        "normalize_embeddings": job_input.get("normalize_embeddings", True),
        "show_progress_bar": job_input.get("show_progress_bar", False),
        "convert_to_numpy": job_input.get("convert_to_numpy", True),
        "return_format": job_input.get("return_format", "list"),  # list, numpy, base64
    }
    
    return validated

def generate_embeddings(
    texts: List[str],
    batch_size: int = 32,
    normalize_embeddings: bool = True,
    show_progress_bar: bool = False,
    convert_to_numpy: bool = True
) -> Union[List[List[float]], np.ndarray]:
    """임베딩 생성"""
    logger.info(f"📝 임베딩 생성 시작: {len(texts)}개 텍스트")
    
    # 임베딩 생성
    with torch.no_grad():
        embeddings = embedding_model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=normalize_embeddings,
            show_progress_bar=show_progress_bar,
            convert_to_numpy=convert_to_numpy,
            device=device
        )
    
    return embeddings

def convert_embeddings_format(embeddings: np.ndarray, format: str) -> Union[List[List[float]], str]:
    """임베딩을 요청된 형식으로 변환"""
    if format == "numpy":
        # numpy 배열은 직렬화할 수 없으므로 base64로 인코딩
        return base64.b64encode(embeddings.tobytes()).decode()
    elif format == "base64":
        # base64로 인코딩
        return base64.b64encode(embeddings.tobytes()).decode()
    else:  # list
        # 기본값: 리스트로 변환
        return embeddings.tolist()

def handler(job):
    """RunPod 핸들러 함수"""
    try:
        logger.info("📥 새로운 임베딩 요청 수신")
        
        # 입력 검증
        job_input = validate_input(job["input"])
        
        # 모델 초기화 (필요한 경우)
        initialize_model(job_input["model_name"])
        
        logger.info(f"📝 텍스트 개수: {len(job_input['texts'])}")
        logger.info(f"🎯 모델: {job_input['model_name']}")
        logger.info(f"📦 배치 크기: {job_input['batch_size']}")
        
        # 임베딩 생성
        embeddings = generate_embeddings(
            texts=job_input["texts"],
            batch_size=job_input["batch_size"],
            normalize_embeddings=job_input["normalize_embeddings"],
            show_progress_bar=job_input["show_progress_bar"],
            convert_to_numpy=job_input["convert_to_numpy"]
        )
        
        # 형식 변환
        formatted_embeddings = convert_embeddings_format(
            embeddings, 
            job_input["return_format"]
        )
        
        # 통계 정보
        if isinstance(embeddings, np.ndarray):
            embedding_stats = {
                "min": float(embeddings.min()),
                "max": float(embeddings.max()),
                "mean": float(embeddings.mean()),
                "std": float(embeddings.std())
            }
        else:
            embedding_stats = None
        
        # 결과 생성
        result = {
            "embeddings": formatted_embeddings,
            "dimension": embedding_model.get_sentence_embedding_dimension(),
            "model_name": job_input["model_name"],
            "device": str(device),
            "batch_size": job_input["batch_size"],
            "num_texts": len(job_input["texts"]),
            "format": job_input["return_format"],
            "normalized": job_input["normalize_embeddings"],
            "status": "success"
        }
        
        if embedding_stats:
            result["stats"] = embedding_stats
        
        logger.info("✅ 임베딩 생성 완료")
        return result
        
    except Exception as e:
        error_msg = f"임베딩 처리 중 오류 발생: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(traceback.format_exc())
        
        return {
            "error": error_msg,
            "status": "failed",
            "traceback": traceback.format_exc()
        }

def cleanup():
    """GPU 메모리 정리"""
    global embedding_model
    if embedding_model is not None:
        del embedding_model
        embedding_model = None
    
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        logger.info("🧹 GPU 메모리 정리 완료")

# Batch processing을 위한 추가 핸들러
def batch_handler(jobs):
    """여러 작업을 배치로 처리하는 핸들러"""
    results = []
    
    # 모든 텍스트를 하나로 모음
    all_texts = []
    job_indices = []  # 각 텍스트가 어떤 job에 속하는지 추적
    
    for i, job in enumerate(jobs):
        try:
            job_input = validate_input(job["input"])
            texts = job_input["texts"]
            all_texts.extend(texts)
            job_indices.extend([i] * len(texts))
        except Exception as e:
            # 검증 실패한 job은 에러로 처리
            results.append({
                "error": str(e),
                "status": "failed"
            })
    
    if all_texts:
        try:
            # 첫 번째 유효한 job의 설정 사용
            first_valid_job = next(j for j in jobs if "error" not in validate_input(j["input"]))
            job_input = validate_input(first_valid_job["input"])
            
            # 모델 초기화
            initialize_model(job_input["model_name"])
            
            # 모든 텍스트에 대해 임베딩 생성
            all_embeddings = generate_embeddings(
                texts=all_texts,
                batch_size=job_input["batch_size"],
                normalize_embeddings=job_input["normalize_embeddings"],
                show_progress_bar=False,
                convert_to_numpy=True
            )
            
            # 결과를 각 job별로 분리
            current_idx = 0
            for i, job in enumerate(jobs):
                if i < len(results):  # 이미 에러 처리된 job
                    continue
                
                job_input = validate_input(job["input"])
                num_texts = len(job_input["texts"])
                
                # 해당 job의 임베딩 추출
                job_embeddings = all_embeddings[current_idx:current_idx + num_texts]
                current_idx += num_texts
                
                # 형식 변환
                formatted_embeddings = convert_embeddings_format(
                    job_embeddings,
                    job_input["return_format"]
                )
                
                results.append({
                    "embeddings": formatted_embeddings,
                    "dimension": embedding_model.get_sentence_embedding_dimension(),
                    "model_name": job_input["model_name"],
                    "num_texts": num_texts,
                    "status": "success"
                })
                
        except Exception as e:
            # 배치 처리 실패 시 모든 job을 실패로 처리
            error_result = {
                "error": str(e),
                "status": "failed",
                "traceback": traceback.format_exc()
            }
            results = [error_result] * len(jobs)
    
    return results

# RunPod 서버리스 실행
if __name__ == "__main__":
    logger.info("🚀 RunPod Embedding Worker 시작")
    logger.info(f"📋 지원 모델: {list(SUPPORTED_MODELS.keys())}")
    runpod.serverless.start({
        "handler": handler,
        "batch_handler": batch_handler  # 배치 처리 지원
    })