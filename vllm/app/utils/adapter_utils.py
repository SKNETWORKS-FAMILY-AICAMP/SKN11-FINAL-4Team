import json
import logging
from typing import Optional
from huggingface_hub import hf_hub_download

logger = logging.getLogger(__name__)

def get_base_model_from_adapter(hf_repo_name: str, hf_token: Optional[str] = None) -> str:
    """어댑터 레포에서 베이스 모델 정보 확인"""
    try:
        logger.info(f"📋 어댑터 config 확인 시작: {hf_repo_name}")
        logger.info(f"🔑 사용할 토큰: {'있음' if hf_token else '없음'}")
        
        # adapter_config.json에서 베이스 모델 정보 확인
        logger.info(f"📥 HuggingFace Hub에서 adapter_config.json 다운로드 중...")
        config_file = hf_hub_download(
            repo_id=hf_repo_name,
            filename="adapter_config.json",
            token=hf_token
        )
        logger.info(f"📁 다운로드된 config 파일 경로: {config_file}")
        
        logger.info(f"📖 config 파일 읽기 중...")
        with open(config_file, 'r') as f:
            adapter_config = json.load(f)
        
        logger.info(f"📋 adapter_config 내용: {adapter_config}")
        
        base_model_name = adapter_config.get("base_model_name_or_path")
        if not base_model_name:
            logger.warning(f"⚠️ adapter_config.json에 base_model_name_or_path가 없습니다.")
            logger.info(f"📋 사용 가능한 키들: {list(adapter_config.keys())}")
        
        logger.info(f"📋 베이스 모델 확인 완료: {base_model_name}")
        
        return base_model_name
        
    except Exception as e:
        logger.error(f"❌ adapter_config.json 읽기 실패 (상세): {e}")
        logger.error(f"❌ 에러 타입: {type(e).__name__}")
        import traceback
        logger.error(f"❌ 전체 스택 트레이스: {traceback.format_exc()}")
        
        # 기본값으로 EXAONE 모델 사용
        base_model_name = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
        logger.info(f"📋 기본 베이스 모델 사용: {base_model_name}")
        return base_model_name
