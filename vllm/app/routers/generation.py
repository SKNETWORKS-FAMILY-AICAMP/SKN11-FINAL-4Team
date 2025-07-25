from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from vllm import SamplingParams
from vllm.lora.request import LoRARequest
from vllm.engine.async_llm_engine import AsyncEngineDeadError
import uuid
import logging
import json
import asyncio
import torch
import os

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
        
        logger.info(f"🔍 생성된 프롬프트 (처음 200자): {formatted_prompt}...")
        
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
        try:
            async for output in core.engine.generate(
                formatted_prompt,
                sampling_params,
                request_id=request_id,
                lora_request=lora_request
            ):
                results.append(output)
        except AsyncEngineDeadError as e:
            logger.error(f"❌ AsyncEngineDeadError 발생: {str(e)}")
            logger.info("🔄 엔진 재시작 시도 중...")
            
            # 엔진 재시작 시도
            try:
                await core.restart_engine()
                logger.info("✅ 엔진 재시작 성공")
                # 재시도
                async for output in core.engine.generate(
                    formatted_prompt,
                    sampling_params,
                    request_id=request_id,
                    lora_request=lora_request
                ):
                    results.append(output)
            except Exception as restart_error:
                logger.error(f"❌ 엔진 재시작 실패: {str(restart_error)}")
                raise HTTPException(
                    status_code=503,
                    detail="AI 엔진에 문제가 발생했습니다. 관리자에게 문의해주세요."
                )
        except RuntimeError as e:
            if "Expected all tensors to be on the same device" in str(e):
                logger.error(f"❌ CUDA 디바이스 불일치 오류: {str(e)}")
                # 디바이스 정보 로깅
                if torch.cuda.is_available():
                    logger.error(f"현재 CUDA 디바이스: {torch.cuda.current_device()}")
                    logger.error(f"사용 가능한 디바이스 수: {torch.cuda.device_count()}")
                    logger.error(f"CUDA_VISIBLE_DEVICES: {os.environ.get('CUDA_VISIBLE_DEVICES', 'Not set')}")
                
                # 디바이스 동기화 시도
                try:
                    # 엔진 재시작으로 디바이스 문제 해결
                    await core.restart_engine()
                    # 재시도
                    async for output in core.engine.generate(
                        formatted_prompt,
                        sampling_params,
                        request_id=request_id,
                        lora_request=lora_request
                    ):
                        results.append(output)
                except Exception as device_error:
                    logger.error(f"❌ 디바이스 동기화 실패: {str(device_error)}")
                    raise HTTPException(
                        status_code=503,
                        detail="GPU 디바이스 오류가 발생했습니다. 관리자에게 문의해주세요."
                    )
            else:
                raise
        
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
        
    except HTTPException:
        # HTTPException은 그대로 전달
        raise
    except Exception as e:
        logger.error(f"❌ 응답 생성 엔드포인트에서 예외 발생: {str(e)}")
        logger.error(f"❌ 예외 타입: {type(e).__name__}")
        import traceback
        logger.error(f"❌ 전체 스택 트레이스: {traceback.format_exc()}")
        
        # 사용자 친화적인 에러 메시지
        if "CUDA" in str(e) or "device" in str(e):
            detail = "GPU 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        elif "memory" in str(e).lower():
            detail = "메모리 부족으로 요청을 처리할 수 없습니다. 더 짧은 메시지로 시도해주세요."
        else:
            detail = "응답 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        
        raise HTTPException(status_code=500, detail=detail)

@router.post("/generate/stream")
async def generate_response_stream_endpoint(request: GenerateRequest):
    """인플루언서 스트리밍 응답 생성"""
    logger.info(f"🔄 스트리밍 응답 생성 엔드포인트 호출됨")
    logger.info(f"📋 요청 데이터: {request.dict()}")
    
    # 입력 검증
    if not request.user_message or not request.user_message.strip():
        raise HTTPException(status_code=400, detail="사용자 메시지가 비어있습니다.")
    
    if not request.influencer_name or not request.influencer_name.strip():
        raise HTTPException(status_code=400, detail="인플루언서 이름이 비어있습니다.")
    
    # 엔진 상태 확인
    if core.engine is None:
        logger.error("❌ 엔진이 초기화되지 않았습니다.")
        raise HTTPException(status_code=503, detail="AI 엔진이 초기화되지 않았습니다. 잠시 후 다시 시도해주세요.")
    
    async def generate_stream():
        try:
            # 프롬프트 생성
            try:
                formatted_prompt = create_chat_prompt(
                    request.user_message, 
                    request.system_message, 
                    request.influencer_name
                )
            except Exception as e:
                logger.error(f"❌ 프롬프트 생성 실패: {str(e)}")
                yield f"data: {json.dumps({'error': '프롬프트 생성에 실패했습니다.'}, ensure_ascii=False, separators=(',', ':'))}\n\n"
                return
            
            # 샘플링 파라미터 검증 및 설정
            try:
                if request.temperature < 0 or request.temperature > 2:
                    yield f"data: {json.dumps({'error': 'temperature는 0과 2 사이의 값이어야 합니다.'}, ensure_ascii=False, separators=(',', ':'))}\n\n"
                    return
                
                if request.max_new_tokens <= 0 or request.max_new_tokens > 4096:
                    yield f"data: {json.dumps({'error': 'max_new_tokens는 1과 4096 사이의 값이어야 합니다.'}, ensure_ascii=False, separators=(',', ':'))}\n\n"
                    return
                
                sampling_params = SamplingParams(
                    temperature=request.temperature,
                    max_tokens=request.max_new_tokens,
                    top_p=0.9,
                    top_k=50,
                    stop=["[|Human|", "[|System|", "<|im_end|>", "</s>", "<|eot_id|>"],
                    repetition_penalty=1.1
                )
            except Exception as e:
                logger.error(f"❌ 샘플링 파라미터 설정 실패: {str(e)}")
                yield f"data: {json.dumps({'error': f'잘못된 파라미터: {str(e)}'}, ensure_ascii=False, separators=(',', ':'))}\n\n"
                return
            
            # LoRA 요청 설정
            lora_request = None
            
            if request.model_id:
                try:
                    if request.model_id not in core.loaded_adapters:
                        error_msg = f"어댑터 '{request.model_id}'가 로드되지 않았습니다."
                        yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False, separators=(',', ':'))}\n\n"
                        return
                    
                    adapter_info = core.loaded_adapters[request.model_id]
                    if not adapter_info or "lora_int_id" not in adapter_info or "hf_repo_name" not in adapter_info:
                        error_msg = f"어댑터 '{request.model_id}'의 정보가 불완전합니다."
                        yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False, separators=(',', ':'))}\n\n"
                        return
                    
                    lora_request = LoRARequest(
                        lora_name=request.model_id,
                        lora_int_id=adapter_info["lora_int_id"],
                        lora_path=adapter_info["hf_repo_name"]
                    )
                except Exception as e:
                    logger.error(f"❌ LoRA 어댑터 설정 실패: {str(e)}")
                    yield f"data: {json.dumps({'error': 'LoRA 어댑터 설정에 실패했습니다.'}, ensure_ascii=False, separators=(',', ':'))}\n\n"
                    return
            
            # 고유 request_id 생성
            request_id = str(uuid.uuid4())
            
            # 스트리밍 생성
            try:
                previous_text = ""
                token_count = 0
                has_output = False
                
                try:
                    async for output in core.engine.generate(
                        formatted_prompt,
                        sampling_params,
                        request_id=request_id,
                        lora_request=lora_request
                    ):
                        has_output = True
                        if output.outputs and len(output.outputs) > 0:
                            current_text = output.outputs[0].text

                            if len(current_text) > len(previous_text):
                                new_tokens = current_text[len(previous_text):]
                                
                                if new_tokens:
                                    new_tokens = new_tokens.replace('[|endofturn|]', '').replace('[|endoftext|]', '').replace('<|im_end|>', '')
                                    if new_tokens.strip():
                                        yield f"data: {json.dumps({'text': new_tokens}, ensure_ascii=False, separators=(',', ':'))}\n\n"
                                        previous_text = current_text
                                        token_count += len(new_tokens)
                except AsyncEngineDeadError as e:
                    logger.error(f"❌ 스트리밍 중 AsyncEngineDeadError 발생: {str(e)}")
                    yield f"data: {json.dumps({'error': 'AI 엔진에 문제가 발생했습니다. 잠시 후 다시 시도해주세요.'})}\n\n"
                    
                    # 비동기로 엔진 재시작 예약
                    asyncio.create_task(core.restart_engine())
                    return
                except RuntimeError as e:
                    if "Expected all tensors to be on the same device" in str(e):
                        logger.error(f"❌ 스트리밍 중 CUDA 디바이스 오류: {str(e)}")
                        # 디바이스 정보 로그
                        if torch.cuda.is_available():
                            logger.error(f"현재 CUDA 디바이스: {torch.cuda.current_device()}")
                            logger.error(f"사용 가능한 디바이스 수: {torch.cuda.device_count()}")
                        yield f"data: {json.dumps({'error': 'GPU 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'})}\n\n"
                        
                        # 비동기로 엔진 재시작 예약
                        asyncio.create_task(core.restart_engine())
                        return
                    else:
                        raise
                
                if not has_output:
                    yield f"data: {json.dumps({'error': '생성된 응답이 없습니다.'}, ensure_ascii=False, separators=(',', ':'))}\n\n"
                    return
                
                # 스트리밍 완료 신호
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False, separators=(',', ':'))}\n\n"
                
            except Exception as e:
                logger.error(f"❌ AI 스트리밍 생성 중 오류: {str(e)}")
                yield f"data: {json.dumps({'error': 'AI 응답 생성 중 오류가 발생했습니다.'}, ensure_ascii=False, separators=(',', ':'))}\n\n"
            
        except Exception as e:
            logger.error(f"❌ 스트리밍 생성 중 오류: {str(e)}")
            yield f"data: {json.dumps({'error': '스트리밍 생성 중 예상치 못한 오류가 발생했습니다.'}, ensure_ascii=False, separators=(',', ':'))}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )