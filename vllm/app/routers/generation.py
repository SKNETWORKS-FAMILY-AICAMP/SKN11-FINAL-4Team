from fastapi import APIRouter, HTTPException
from vllm import SamplingParams
from vllm.lora.request import LoRARequest
import uuid
import logging

from app.models import GenerateRequest, GenerateResponse
from app import core
from app.utils.prompt_utils import create_chat_prompt
from app.utils.response_utils import clean_response

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/generate", response_model=GenerateResponse)
async def generate_response_endpoint(request: GenerateRequest):
    """인플루언서 응답 생성"""
    logger.info(f"🔄 응답 생성 엔드포인트 호출됨")
    logger.info(f"📋 요청 데이터: {request.dict()}")
    
    logger.info(f"🔍 현재 엔진 상태 확인: {core.engine}")
    if core.engine is None:
        logger.error("❌ 엔진이 초기화되지 않았습니다.")
        raise HTTPException(status_code=500, detail="엔진이 초기화되지 않았습니다.")
    
    logger.info(f"✅ 엔진 상태 확인 완료: {type(core.engine)}")
    
    try:
        # 프롬프트 생성 (무조건 chat template 사용)
        formatted_prompt = create_chat_prompt(
            request.user_message, 
            request.system_message, 
            request.influencer_name
        )
        
        logger.info(f"🔍 생성된 프롬프트 (처음 200자): {formatted_prompt[:200]}...")
        
        # 샘플링 파라미터 설정
        sampling_params = SamplingParams(
            temperature=request.temperature,
            max_tokens=request.max_new_tokens,
            top_p=0.9,
            top_k=50,
            stop=["[|Human|", "[|System|", "<|im_end|", "</s>", "<|eot_id|>"],
            repetition_penalty=1.1
        )
        
        # LoRA 요청 설정
        lora_request = None
        used_adapter = False
        
        if request.model_id:
            if request.model_id not in core.loaded_adapters:
                raise HTTPException(
                    status_code=400,
                    detail=f"어댑터 {request.model_id}가 로드되지 않았습니다. 먼저 /load_adapter를 사용하세요."
                )
            
            adapter_info = core.loaded_adapters[request.model_id]
            lora_request = LoRARequest(
                lora_name=request.model_id,
                lora_int_id=adapter_info["lora_int_id"],
                lora_path=adapter_info["hf_repo_name"]
            )
            used_adapter = True
            logger.info(f"🔧 LoRA 어댑터 사용: {request.model_id}")
        
        # 고유 request_id 생성
        request_id = str(uuid.uuid4())
        
        # 비동기 생성
        results = []
        async for output in core.engine.generate(
            formatted_prompt,
            sampling_params,
            request_id=request_id,
            lora_request=lora_request
        ):
            results.append(output)
        
        if not results:
            raise HTTPException(status_code=500, detail="생성된 응답이 없습니다.")
        
        # 응답 처리
        final_output = results[-1]
        raw_response = final_output.outputs[0].text
        
        # 응답 정리
        cleaned_response = clean_response(raw_response, request.influencer_name)
        
        logger.info(f"✅ 응답 생성 완료: {request.influencer_name}")
        
        return GenerateResponse(
            response=cleaned_response,
            model_id=request.model_id,
            used_adapter=used_adapter,
            formatted_prompt=formatted_prompt,
            raw_response=raw_response
        )
        
    except Exception as e:
        logger.error(f"❌ 응답 생성 엔드포인트에서 예외 발생: {str(e)}")
        logger.error(f"❌ 예외 타입: {type(e).__name__}")
        import traceback
        logger.error(f"❌ 전체 스택 트레이스: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"응답 생성 실패: {str(e)}")