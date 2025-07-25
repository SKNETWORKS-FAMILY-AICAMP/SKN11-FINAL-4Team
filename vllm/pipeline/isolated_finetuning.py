"""
격리된 GPU 컨텍스트에서 실행되는 파인튜닝 워커
"""

import os
import sys
import torch
import logging
from typing import Dict, Any
import json
import traceback
from datetime import datetime

# 프로젝트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.fine_custom import train_lora_model, ExaoneDataPreprocessor
from transformers import AutoTokenizer
from datasets import Dataset

logger = logging.getLogger(__name__)

def setup_gpu_isolation(gpu_id: int):
    """GPU 격리 설정"""
    # 환경 변수 설정 (torch import 전에)
    os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu_id)
    
    # CUDA 설정
    if torch.cuda.is_available():
        torch.cuda.set_device(0)  # 격리된 환경에서는 항상 0
        logger.info(f"✅ GPU 격리 설정 완료: 물리적 GPU {gpu_id} → 논리적 GPU 0")
        logger.info(f"🔧 GPU 이름: {torch.cuda.get_device_name(0)}")
    else:
        logger.warning("⚠️ GPU를 사용할 수 없습니다.")

def run_isolated_finetuning(config: Dict[str, Any]):
    """격리된 환경에서 파인튜닝 실행"""
    
    # GPU 설정
    gpu_id = config.get('gpu_id', 2)
    setup_gpu_isolation(gpu_id)
    
    # 메모리 fraction 설정
    memory_fraction = config.get('memory_fraction', 0.8)
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(memory_fraction, device=0)
        logger.info(f"💾 GPU 메모리 사용률 제한: {memory_fraction * 100}%")
    
    try:
        # 설정 로드
        dataset_path = config['dataset_path']
        output_dir = config.get('output_dir', './lora_model')
        hf_token = config.get('hf_token')
        hf_repo_name = config.get('hf_repo_name')
        model_name = config.get('model_name', 'LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct')
        
        logger.info(f"🚀 파인튜닝 시작")
        logger.info(f"📁 데이터셋: {dataset_path}")
        logger.info(f"📦 출력 디렉토리: {output_dir}")
        logger.info(f"🤖 모델: {model_name}")
        
        # 데이터셋 로드
        with open(dataset_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 토크나이저 로드
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        preprocessor = ExaoneDataPreprocessor(tokenizer)
        
        # 데이터 전처리
        processed_data = []
        for item in data:
            text = preprocessor.create_chat_format(
                instruction=item['instruction'],
                output=item['output'],
                system_msg=item.get('system', "You are a helpful AI assistant.")
            )
            processed_data.append({"text": text})
        
        # Dataset 생성
        dataset = Dataset.from_list(processed_data)
        logger.info(f"✅ 데이터셋 준비 완료: {len(dataset)} 샘플")
        
        # 훈련 실행
        model, trainer = train_lora_model(
            model_name=model_name,
            dataset=dataset,
            output_dir=output_dir,
            num_epochs=config.get('num_epochs', 3),
            batch_size=config.get('batch_size', 1),
            learning_rate=config.get('learning_rate', 2e-5),
            lora_rank=config.get('lora_rank', 32),
            lora_alpha=config.get('lora_alpha', 16),
            lora_dropout=config.get('lora_dropout', 0.05),
            hub_token=hf_token,
            push_to_hub=bool(hf_repo_name),
            hub_model_id=hf_repo_name
        )
        
        logger.info("✅ 파인튜닝 완료!")
        
        # 결과 반환
        return {
            'status': 'completed',
            'output_dir': output_dir,
            'hf_repo_name': hf_repo_name,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ 파인튜닝 실패: {e}")
        logger.error(traceback.format_exc())
        
        return {
            'status': 'failed',
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat()
        }
    
    finally:
        # GPU 메모리 정리
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("🧹 GPU 메모리 정리 완료")

if __name__ == "__main__":
    # 독립 실행을 위한 코드
    import argparse
    
    parser = argparse.ArgumentParser(description='격리된 GPU 파인튜닝')
    parser.add_argument('--config', type=str, required=True, help='설정 파일 경로')
    args = parser.parse_args()
    
    # 설정 파일 로드
    with open(args.config, 'r') as f:
        config = json.load(f)
    
    # 파인튜닝 실행
    result = run_isolated_finetuning(config)
    
    # 결과 출력
    print(json.dumps(result, indent=2))