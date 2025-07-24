#!/usr/bin/env python3
"""
파인튜닝을 별도 프로세스로 실행하기 위한 래퍼 스크립트
"""
import os
import sys
import json
import argparse
import logging

# 현재 스크립트의 디렉토리를 기준으로 상위 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# 환경 변수 설정을 맨 처음에 수행
def setup_gpu_environment(gpu_id):
    """GPU 환경 변수를 설정합니다."""
    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    
    # PyTorch가 지정된 GPU만 볼 수 있도록 설정
    print(f"✅ CUDA_VISIBLE_DEVICES를 {gpu_id}로 설정 완료")

def main():
    parser = argparse.ArgumentParser(description="파인튜닝 서브프로세스")
    parser.add_argument("--gpu-id", type=int, required=True, help="사용할 GPU ID")
    parser.add_argument("--qa-data", type=str, required=True, help="QA 데이터 JSON 파일 경로")
    parser.add_argument("--system-message", type=str, required=True, help="시스템 메시지")
    parser.add_argument("--hf-token", type=str, required=True, help="HuggingFace 토큰")
    parser.add_argument("--hf-repo-id", type=str, required=True, help="HuggingFace 리포지토리 ID")
    parser.add_argument("--training-epochs", type=int, required=True, help="훈련 에포크 수")
    parser.add_argument("--output-file", type=str, required=True, help="결과를 저장할 파일 경로")
    
    args = parser.parse_args()
    
    # GPU 환경 설정 (import 전에 설정)
    setup_gpu_environment(args.gpu_id)
    
    # 이제 PyTorch와 fine_custom을 import
    try:
        import torch
        print(f"🔍 PyTorch가 볼 수 있는 GPU 수: {torch.cuda.device_count()}")
        if torch.cuda.is_available():
            print(f"✅ GPU 사용 가능: {torch.cuda.get_device_name(0)}")
            print(f"📊 GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
        
        from pipeline import fine_custom
    except ImportError as e:
        print(f"❌ Import 오류: {e}")
        sys.exit(1)
    
    # 결과 저장을 위한 딕셔너리
    result = {
        "success": False,
        "hf_model_url": None,
        "error": None
    }
    
    try:
        # QA 데이터 로드
        with open(args.qa_data, 'r', encoding='utf-8') as f:
            qa_data = json.load(f)
        
        print(f"📊 QA 데이터 로드 완료: {len(qa_data)} 개")
        
        # fine_custom.py의 CUDA_VISIBLE_DEVICES 설정을 제거했으므로
        # 이제 물리적 GPU ID를 사용할지 결정
        # CUDA_VISIBLE_DEVICES가 설정되어 있으므로 0을 사용
        hf_model_url = fine_custom.main(
            qa_data=qa_data,
            system_message=args.system_message,
            hf_token=args.hf_token,
            hf_repo_id=args.hf_repo_id,
            training_epochs=args.training_epochs,
            gpu_id=0  # CUDA_VISIBLE_DEVICES 설정 후에는 항상 0
        )
        
        result["success"] = True
        result["hf_model_url"] = hf_model_url
        
    except Exception as e:
        print(f"❌ 파인튜닝 실패: {e}")
        result["success"] = False
        result["error"] = str(e)
    
    finally:
        # 결과를 파일로 저장
        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"📄 결과를 {args.output_file}에 저장했습니다")
        
        # GPU 메모리 정리
        if 'torch' in sys.modules:
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                print("✅ GPU 메모리 정리 완료")

if __name__ == "__main__":
    main()