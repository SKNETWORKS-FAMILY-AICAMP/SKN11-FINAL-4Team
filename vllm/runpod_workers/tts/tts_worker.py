"""
RunPod Serverless Worker for Zonos TTS
vLLM 프로젝트의 Zonos TTS 엔진을 RunPod Worker로 완전 마이그레이션
"""
import os
import sys
import logging
import json
import torch
import torchaudio
import base64
import io
import traceback
import requests
import aiohttp
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# vLLM 프로젝트의 zonos 모듈 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import runpod

# Zonos 관련 임포트
from zonos.model import Zonos
from zonos.conditioning import make_cond_dict

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 전역 모델 변수
zonos_model = None
device = None

# 미리 정의된 감정 벡터 (기존 코드에서 가져옴)
PREDEFINED_EMOTIONS = {
    "neutral": [0.3077, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.2564, 0.3077],
    "happy": [0.0256, 0.5897, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.3077],
    "sad": [0.0256, 0.0256, 0.5897, 0.0256, 0.0256, 0.0256, 0.0256, 0.3077],
    "angry": [0.0256, 0.0256, 0.0256, 0.5897, 0.0256, 0.0256, 0.0256, 0.3077],
    "fearful": [0.0256, 0.0256, 0.0256, 0.0256, 0.5897, 0.0256, 0.0256, 0.3077],
    "disgusted": [0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.5897, 0.0256, 0.3077],
    "surprised": [0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.5897, 0.3077],
    "contempt": [0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.8718]
}

def initialize_model():
    """모델 초기화 (한 번만 실행)"""
    global zonos_model, device
    
    if zonos_model is None:
        logger.info("🔧 Zonos 모델 초기화 시작...")
        
        # GPU 설정
        if torch.cuda.is_available():
            device = torch.device("cuda:0")
            logger.info(f"🖥️ GPU 사용: {torch.cuda.get_device_name(0)}")
            logger.info(f"📊 GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        else:
            device = torch.device("cpu")
            logger.warning("⚠️ CUDA를 사용할 수 없습니다. CPU를 사용합니다.")
        
        # 모델 로드
        try:
            zonos_model = Zonos.from_pretrained("Zyphra/Zonos-v0.1-transformer", device=device)
            logger.info("✅ Zonos 모델 초기화 완료")
        except Exception as e:
            logger.error(f"❌ 모델 로드 실패: {str(e)}")
            raise

def validate_input(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """입력 데이터 검증 및 기본값 설정"""
    # 필수 필드 확인
    if "text" not in job_input:
        raise ValueError("text 필드는 필수입니다.")
    
    # 기본값 설정
    validated = {
        "text": job_input["text"],
        "language": job_input.get("language", "ko"),
        "speaking_rate": float(job_input.get("speaking_rate", 22.0)),
        "pitch_std": float(job_input.get("pitch_std", 40.0)),
        "cfg_scale": float(job_input.get("cfg_scale", 4.0)),
        "emotion": job_input.get("emotion", PREDEFINED_EMOTIONS["neutral"]),
        "emotion_name": job_input.get("emotion_name", None),
        "voice_data_base64": job_input.get("voice_data_base64", None),
        "output_format": job_input.get("output_format", "wav"),
        "influencer_id": job_input.get("influencer_id", None),  # 인플루언서 ID 추가
        "base_voice_id": job_input.get("base_voice_id", None),  # 베이스 음성 ID 추가
        "voice_id": job_input.get("voice_id", None),  # 백엔드에서 전달한 DB ID
        "use_async": job_input.get("use_async", False),  # 비동기 처리 옵션
    }
    
    # 감정 이름으로 벡터 설정
    if validated["emotion_name"] and validated["emotion_name"] in PREDEFINED_EMOTIONS:
        validated["emotion"] = PREDEFINED_EMOTIONS[validated["emotion_name"]]
    
    # 감정 벡터 검증
    if len(validated["emotion"]) != 8:
        raise ValueError("emotion은 8개의 float 값으로 구성되어야 합니다.")
    
    if not all(0 <= x <= 1 for x in validated["emotion"]):
        raise ValueError("emotion 값은 0과 1 사이여야 합니다.")
    
    # 언어 코드 검증 (한국어로 고정)
    validated["language"] = "ko"
    
    return validated

def generate_tts(
    text: str,
    speaker_embedding: Optional[torch.Tensor],
    language: str,
    speaking_rate: float,
    pitch_std: float,
    cfg_scale: float,
    emotion: List[float]
) -> torch.Tensor:
    """TTS 생성 핵심 로직"""
    # 조건 딕셔너리 생성
    cond_dict = make_cond_dict(
        text=text,
        speaker=speaker_embedding,
        language=language,
        speaking_rate=speaking_rate,
        emotion=emotion,
        pitch_std=pitch_std,
        device=device
    )
    
    # 조건 준비
    conditioning = zonos_model.prepare_conditioning(cond_dict)
    
    # 코드 생성
    with torch.no_grad():
        codes = zonos_model.generate(
            conditioning,
            cfg_scale=cfg_scale,
            disable_torch_compile=True,
            progress_bar=False
        )
    
    # 오디오 디코드
    wavs = zonos_model.autoencoder.decode(codes)
    
    return wavs[0]

def process_voice_cloning(voice_data_base64: str) -> torch.Tensor:
    """음성 클로닝을 위한 스피커 임베딩 생성"""
    try:
        # Base64 디코딩
        voice_data = base64.b64decode(voice_data_base64)
        
        # 오디오 로드
        voice_wav, sr = torchaudio.load(io.BytesIO(voice_data))
        voice_wav = voice_wav.to(device)
        
        # 스피커 임베딩 생성
        speaker_embedding = zonos_model.make_speaker_embedding(voice_wav, sr)
        
        return speaker_embedding
        
    except Exception as e:
        logger.error(f"음성 클로닝 처리 중 오류: {str(e)}")
        raise

def encode_audio(wav_tensor: torch.Tensor, sample_rate: int, format: str = "wav") -> str:
    """오디오 텐서를 base64로 인코딩"""
    audio_buffer = io.BytesIO()
    
    # CPU로 이동 후 저장
    wav_cpu = wav_tensor.cpu()
    
    if format == "wav":
        torchaudio.save(audio_buffer, wav_cpu, sample_rate, format="wav")
    elif format == "mp3":
        # MP3는 torchaudio에서 직접 지원하지 않을 수 있음
        torchaudio.save(audio_buffer, wav_cpu, sample_rate, format="wav")
    else:
        raise ValueError(f"지원하지 않는 포맷: {format}")
    
    audio_buffer.seek(0)
    audio_base64 = base64.b64encode(audio_buffer.getvalue()).decode()
    
    return audio_base64


def send_to_backend_sync(audio_base64: str, metadata: Dict[str, Any]):
    """생성된 음성을 Backend로 전송 (동기 방식)"""
    backend_url = os.getenv('BACKEND_POST_URL')
    if not backend_url:
        logger.warning("BACKEND_POST_URL이 설정되지 않았습니다")
        return None
    
    try:
        # POST 페이로드 구성
        payload = {
            "audio_base64": audio_base64,
            "metadata": metadata
        }
        
        logger.info(f"📤 Backend로 음성 데이터 전송: {backend_url}")
        logger.info(f"📦 페이로드 크기: {len(json.dumps(payload))} bytes")
        
        response = requests.post(
            backend_url,
            json=payload,
            timeout=60  # 큰 음성 파일을 위해 타임아웃 증가
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Backend 전송 성공: {response.status_code}")
            return response.json()
        else:
            logger.error(f"❌ Backend 전송 실패: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Backend 전송 중 오류: {str(e)}")
        return None

async def send_to_backend(audio_base64: str, metadata: Dict[str, Any]):
    """생성된 음성을 Backend로 전송 (비동기 방식)"""
    backend_url = os.getenv('BACKEND_POST_URL')
    if not backend_url:
        logger.warning("BACKEND_POST_URL이 설정되지 않았습니다")
        return None
    
    try:
        # POST 페이로드 구성
        payload = {
            "audio_base64": audio_base64,
            "metadata": metadata
        }
        
        logger.info(f"📤 Backend로 음성 데이터 비동기 전송: {backend_url}")
        logger.info(f"📦 페이로드 크기: {len(json.dumps(payload))} bytes")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                backend_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)  # 큰 음성 파일을 위해 타임아웃 증가
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"✅ Backend 비동기 전송 성공: {response.status}")
                    return result
                else:
                    text = await response.text()
                    logger.error(f"❌ Backend 비동기 전송 실패: {response.status} - {text}")
                    return None
            
    except Exception as e:
        logger.error(f"❌ Backend 비동기 전송 중 오류: {str(e)}")
        return None



async def handler(job):
    """RunPod 비동기 핸들러 함수"""
    try:
        # 로깅
        logger.info("📥 새로운 TTS 요청 수신")
        start_time = datetime.now().timestamp()
        
        # RunPod job ID와 메타데이터 추출
        job_id = job.get("id", "unknown")
        webhook_metadata = job.get("webhook_metadata", {})
        
        # 모델 초기화 확인
        initialize_model()
        
        # 입력 검증
        job_input = validate_input(job["input"])
        logger.info(f"📝 텍스트 길이: {len(job_input['text'])} 문자")
        
        # 음성 클로닝 처리
        speaker_embedding = None
        if job_input["voice_data_base64"]:
            logger.info("🎤 음성 클로닝 처리 중...")
            speaker_embedding = process_voice_cloning(job_input["voice_data_base64"])
        
        # TTS 생성
        logger.info("🔊 TTS 생성 중...")
        wav_output = generate_tts(
            text=job_input["text"],
            speaker_embedding=speaker_embedding,
            language=job_input["language"],
            speaking_rate=job_input["speaking_rate"],
            pitch_std=job_input["pitch_std"],
            cfg_scale=job_input["cfg_scale"],
            emotion=job_input["emotion"]
        )
        
        # 오디오 인코딩
        logger.info("📦 오디오 인코딩 중...")
        
        # WAV 파일로 저장
        audio_buffer = io.BytesIO()
        wav_cpu = wav_output.cpu()
        torchaudio.save(audio_buffer, wav_cpu, zonos_model.autoencoder.sampling_rate, format="wav")
        audio_buffer.seek(0)
        audio_data = audio_buffer.getvalue()
        
        # 오디오 길이 계산 (초)
        duration = float(wav_cpu.shape[1]) / zonos_model.autoencoder.sampling_rate
        
        # Base64 인코딩
        audio_base64 = base64.b64encode(audio_data).decode()
        
        # 결과 생성
        result = {
            "audio_base64": audio_base64,
            "duration": duration,
            "file_size": len(audio_data),
            "sample_rate": zonos_model.autoencoder.sampling_rate,
            "text_length": len(job_input["text"]),
            "language": job_input["language"],
            "emotion": job_input.get("emotion_name", "custom"),
            "status": "success"
        }
        
        # Backend로 전송 (환경 변수가 설정된 경우)
        if os.getenv('BACKEND_POST_URL'):
            logger.info("🔔 Backend로 음성 데이터 전송 중...")
            
            # 메타데이터 구성
            metadata = {
                "job_id": job_id,  # RunPod job_id (로깅용)
                "voice_id": job_input.get("voice_id"),  # DB voice ID
                "text": job_input["text"],
                "text_length": len(job_input["text"]),
                "language": job_input["language"],
                "emotion": job_input.get("emotion_name", "custom"),
                "duration": duration,
                "file_size": len(audio_data),
                "sample_rate": zonos_model.autoencoder.sampling_rate,
                "created_at": datetime.now().isoformat(),
                "influencer_id": job_input.get("influencer_id"),  # 인플루언서 ID 추가
                "base_voice_id": job_input.get("base_voice_id"),   # 베이스 음성 ID 추가
                "status": "success"  # 성공 상태 명시
            }
            
            # 동기 또는 비동기 방식으로 Backend 전송
            use_async = job.get("input", {}).get("use_async", False)
            
            if use_async:
                logger.info("🔔 Backend로 음성 데이터 비동기 전송 중...")
                backend_response = await send_to_backend(audio_base64, metadata)
            else:
                logger.info("🔔 Backend로 음성 데이터 동기 전송 중...")
                backend_response = send_to_backend_sync(audio_base64, metadata)
                
            if backend_response:
                logger.info(f"✅ Backend 응답: {backend_response}")
        
        logger.info("✅ TTS 생성 완료")
        return result
        
    except Exception as e:
        error_msg = f"TTS 처리 중 오류 발생: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(traceback.format_exc())
        
        # 실패 시에도 Backend로 전송
        if os.getenv('BACKEND_POST_URL'):
            logger.info("🔔 Backend로 실패 상태 전송 중...")
            
            # 실패 메타데이터 구성
            error_metadata = {
                "job_id": job.get("id", "unknown"),
                "voice_id": job.get("input", {}).get("voice_id"),
                "text": job.get("input", {}).get("text", ""),
                "text_length": len(job.get("input", {}).get("text", "")),
                "language": job.get("input", {}).get("language", "ko"),
                "emotion": job.get("input", {}).get("emotion_name", "neutral"),
                "duration": 0,
                "file_size": 0,
                "sample_rate": 0,
                "created_at": datetime.now().isoformat(),
                "influencer_id": job.get("input", {}).get("influencer_id"),
                "base_voice_id": job.get("input", {}).get("base_voice_id"),
                "status": "failed",
                "error": error_msg,
                "error_type": type(e).__name__
            }
            
            # 실패 응답 전송 (audio_base64는 빈 문자열로)
            use_async = job.get("input", {}).get("use_async", False)
            
            if use_async:
                backend_response = await send_to_backend("", error_metadata)
            else:
                backend_response = send_to_backend_sync("", error_metadata)
                
            if backend_response:
                logger.info(f"✅ Backend 실패 응답 전송 완료: {backend_response}")
        
        return {
            "error": error_msg,
            "status": "failed",
            "traceback": traceback.format_exc()
        }

# GPU 메모리 정리 함수
def cleanup():
    """GPU 메모리 정리"""
    global zonos_model
    if zonos_model is not None:
        del zonos_model
        zonos_model = None
    
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        logger.info("🧹 GPU 메모리 정리 완료")

# RunPod 서버리스 실행
if __name__ == "__main__":
    logger.info("🚀 RunPod Zonos TTS Worker 시작")
    
    # Zonos 엔진 미리 초기화 (첫 요청 대기 시간 단축)
    logger.info("⏳ Zonos 엔진 사전 초기화 중...")
    try:
        initialize_model()
        logger.info("✅ Zonos 엔진 사전 초기화 완료 - 첫 요청 응답 시간이 개선됩니다")
    except Exception as e:
        logger.error(f"❌ Zonos 엔진 사전 초기화 실패: {str(e)}")
        logger.warning("⚠️ 첫 요청 시 초기화가 진행됩니다")
    
    runpod.serverless.start({"handler": handler})