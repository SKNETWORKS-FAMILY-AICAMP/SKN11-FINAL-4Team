"""
모든 RunPod Worker 로컬 테스트 스크립트
"""
import os
import sys
import json
import base64
import importlib.util

# 색상 정의
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
NC = '\033[0m'  # No Color

def print_colored(text, color):
    print(f"{color}{text}{NC}")

def test_tts_worker():
    """TTS Worker 테스트"""
    print_colored("\n=== TTS Worker 테스트 ===", BLUE)
    
    # TTS Worker 임포트
    spec = importlib.util.spec_from_file_location("tts_worker", "tts/tts_worker.py")
    tts_worker = importlib.util.module_from_spec(spec)
    sys.modules["tts_worker"] = tts_worker
    spec.loader.exec_module(tts_worker)
    
    # 테스트 job
    job = {
        "input": {
            "text": "RunPod Worker 테스트입니다.",
            "emotion_name": "neutral"
        }
    }
    
    try:
        # 모델 초기화
        print("모델 초기화 중...")
        tts_worker.initialize_model()
        
        # 핸들러 실행
        result = tts_worker.handler(job)
        
        if result["status"] == "success":
            print_colored("✅ TTS Worker 테스트 성공", GREEN)
            print(f"   - 오디오 크기: {len(result['audio_base64'])} bytes")
        else:
            print_colored(f"❌ TTS Worker 테스트 실패: {result.get('error')}", RED)
    except Exception as e:
        print_colored(f"❌ TTS Worker 테스트 중 오류: {str(e)}", RED)

def test_embedding_worker():
    """Embedding Worker 테스트"""
    print_colored("\n=== Embedding Worker 테스트 ===", BLUE)
    
    # Embedding Worker 임포트
    spec = importlib.util.spec_from_file_location("embedding_worker", "embedding/embedding_worker.py")
    embedding_worker = importlib.util.module_from_spec(spec)
    sys.modules["embedding_worker"] = embedding_worker
    spec.loader.exec_module(embedding_worker)
    
    # 테스트 job
    job = {
        "input": {
            "texts": ["안녕하세요", "반갑습니다", "좋은 하루 되세요"],
            "model_name": "bge-m3"
        }
    }
    
    try:
        # 핸들러 실행
        result = embedding_worker.handler(job)
        
        if result["status"] == "success":
            print_colored("✅ Embedding Worker 테스트 성공", GREEN)
            print(f"   - 임베딩 차원: {result['dimension']}")
            print(f"   - 처리된 텍스트 수: {result['num_texts']}")
        else:
            print_colored(f"❌ Embedding Worker 테스트 실패: {result.get('error')}", RED)
    except Exception as e:
        print_colored(f"❌ Embedding Worker 테스트 중 오류: {str(e)}", RED)

def test_finetuning_worker():
    """Fine-tuning Worker 테스트"""
    print_colored("\n=== Fine-tuning Worker 테스트 ===", BLUE)
    
    # Fine-tuning Worker 임포트
    spec = importlib.util.spec_from_file_location("finetuning_worker", "finetuning/finetuning_worker.py")
    finetuning_worker = importlib.util.module_from_spec(spec)
    sys.modules["finetuning_worker"] = finetuning_worker
    spec.loader.exec_module(finetuning_worker)
    
    # 테스트 job (실제로 실행하지 않음)
    job = {
        "input": {
            "qa_data": [
                {"question": "테스트 질문 1", "answer": "테스트 답변 1"},
                {"question": "테스트 질문 2", "answer": "테스트 답변 2"}
            ],
            "system_message": "테스트 시스템 메시지",
            "hf_token": "test_token",
            "hf_repo_id": "test/repo",
            "training_epochs": 1
        }
    }
    
    try:
        # 입력 검증만 테스트
        validated = finetuning_worker.validate_input(job["input"])
        print_colored("✅ Fine-tuning Worker 입력 검증 성공", GREEN)
        print(f"   - QA 데이터 개수: {len(validated['qa_data'])}")
        print(f"   - 학습 에폭: {validated['training_epochs']}")
    except Exception as e:
        print_colored(f"❌ Fine-tuning Worker 테스트 중 오류: {str(e)}", RED)

def test_generation_worker():
    """vLLM Generation Worker 테스트"""
    print_colored("\n=== vLLM Generation Worker 테스트 ===", BLUE)
    
    # Generation Worker 임포트
    spec = importlib.util.spec_from_file_location("generation_worker", "vllm_generation/generation_worker.py")
    generation_worker = importlib.util.module_from_spec(spec)
    sys.modules["generation_worker"] = generation_worker
    spec.loader.exec_module(generation_worker)
    
    # 테스트 job
    job = {
        "input": {
            "prompt": "인공지능의 미래는",
            "temperature": 0.7,
            "max_tokens": 50
        }
    }
    
    try:
        # 입력 검증 테스트
        validated = generation_worker.validate_input(job["input"])
        print_colored("✅ vLLM Generation Worker 입력 검증 성공", GREEN)
        print(f"   - 온도: {validated['temperature']}")
        print(f"   - 최대 토큰: {validated['max_tokens']}")
        
        # 실제 생성은 GPU와 모델이 필요하므로 스킵
        print_colored("   (실제 생성은 GPU 환경에서 테스트하세요)", YELLOW)
    except Exception as e:
        print_colored(f"❌ vLLM Generation Worker 테스트 중 오류: {str(e)}", RED)

def main():
    """메인 함수"""
    print_colored("🚀 RunPod Workers 로컬 테스트", GREEN)
    print("=" * 50)
    
    # 테스트 선택
    print("\n테스트할 워커를 선택하세요:")
    print("1) 전체 테스트")
    print("2) TTS Worker")
    print("3) Embedding Worker")
    print("4) Fine-tuning Worker")
    print("5) vLLM Generation Worker")
    
    choice = input("\n선택 (1-5): ")
    
    tests = {
        "1": [test_tts_worker, test_embedding_worker, test_finetuning_worker, test_generation_worker],
        "2": [test_tts_worker],
        "3": [test_embedding_worker],
        "4": [test_finetuning_worker],
        "5": [test_generation_worker]
    }
    
    if choice in tests:
        for test_func in tests[choice]:
            try:
                test_func()
            except Exception as e:
                print_colored(f"테스트 실행 중 오류: {str(e)}", RED)
    else:
        print_colored("잘못된 선택입니다.", RED)
    
    print("\n" + "=" * 50)
    print_colored("테스트 완료!", GREEN)

if __name__ == "__main__":
    main()