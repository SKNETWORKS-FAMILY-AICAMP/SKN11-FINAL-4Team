#!/usr/bin/env python3
"""
Zonos TTS 디버깅 스크립트
"""

import torch
import sys
import os

# 모듈 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from zonos.model import Zonos
from zonos.conditioning import make_cond_dict

def test_zonos_model():
    """Zonos 모델 직접 테스트"""
    print("=== Zonos 모델 디버깅 ===")
    
    # 시스템 정보 출력
    print(f"Python 버전: {sys.version}")
    print(f"PyTorch 버전: {torch.__version__}")
    print(f"CUDA 사용 가능: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA 버전: {torch.version.cuda}")
        print(f"GPU 이름: {torch.cuda.get_device_name(0)}")
        print(f"GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n사용할 디바이스: {device}")
    
    try:
        # 모델 로드
        print("\n1. 모델 로드 중...")
        model = Zonos.from_pretrained("Zyphra/Zonos-v0.1-transformer", device=device)
        print("✅ 모델 로드 성공")
        
        # 간단한 텍스트로 테스트
        test_text = "안녕하세요"
        print(f"\n2. 테스트 텍스트: '{test_text}'")
        
        # 조건 딕셔너리 생성
        print("3. 조건 딕셔너리 생성 중...")
        cond_dict = make_cond_dict(
            text=test_text,
            speaker=None,
            language="ko",
            speaking_rate=22.0,
            pitch_std=40.0
        )
        print("✅ 조건 딕셔너리 생성 성공")
        
        # 조건 준비
        print("\n4. 조건 준비 중...")
        conditioning = model.prepare_conditioning(cond_dict)
        print(f"✅ 조건 준비 성공. Shape: {conditioning.shape}")
        
        # 코드 생성 (다양한 cfg_scale 테스트)
        for cfg_scale in [2.0, 3.0, 4.0]:
            print(f"\n5. 코드 생성 중 (cfg_scale={cfg_scale})...")
            try:
                codes = model.generate(
                    conditioning, 
                    cfg_scale=cfg_scale,
                    max_new_tokens=100,  # 짧은 테스트용
                    disable_torch_compile=True,
                    progress_bar=True
                )
                print(f"✅ 코드 생성 성공! Shape: {codes.shape}")
                
                # 오디오 디코드
                print("6. 오디오 디코드 중...")
                wavs = model.autoencoder.decode(codes)
                print(f"✅ 오디오 디코드 성공! Shape: {wavs.shape}")
                print(f"   샘플링 레이트: {model.autoencoder.sampling_rate}")
                
                break  # 성공하면 종료
                
            except Exception as e:
                print(f"❌ cfg_scale={cfg_scale}에서 실패: {e}")
                if cfg_scale == 4.0:  # 마지막 시도에서도 실패하면
                    raise
        
        print("\n✅ 모든 테스트 완료!")
        
    except Exception as e:
        import traceback
        print(f"\n❌ 오류 발생: {e}")
        print("\n상세 에러:")
        traceback.print_exc()
        
        # 추가 디버깅 정보
        if torch.cuda.is_available():
            print(f"\nGPU 메모리 사용량: {torch.cuda.memory_allocated() / 1024**3:.2f} GB")
            print(f"GPU 메모리 예약량: {torch.cuda.memory_reserved() / 1024**3:.2f} GB")

if __name__ == "__main__":
    test_zonos_model()