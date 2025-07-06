import json
import logging
from typing import Optional
from huggingface_hub import hf_hub_download

logger = logging.getLogger(__name__)

def get_base_model_from_adapter(hf_repo_name: str, hf_token: Optional[str] = None) -> str:
    """어댑터 레포에서 베이스 모델 정보 확인"""
    try:
        logger.info(f"📋 어댑터 config 확인: {hf_repo_name}")
        
        # adapter_config.json에서 베이스 모델 정보 확인
        config_file = hf_hub_download(
            repo_id=hf_repo_name,
            filename="adapter_config.json",
            token=hf_token
        )
        
        with open(config_file, 'r') as f:
            adapter_config = json.load(f)
        
        base_model_name = adapter_config.get("base_model_name_or_path")
        logger.info(f"📋 베이스 모델 확인: {base_model_name}")
        
        return base_model_name
        
    except Exception as e:
        logger.warning(f"⚠️ adapter_config.json 읽기 실패: {e}")
        # 기본값으로 EXAONE 모델 사용
        base_model_name = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
        logger.info(f"📋 기본 베이스 모델 사용: {base_model_name}")
        return base_model_name
