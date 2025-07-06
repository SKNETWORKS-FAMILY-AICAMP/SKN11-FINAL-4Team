import os
import asyncio
import json
import logging
import time
import tempfile
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, APIRouter
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from vllm.engine.arg_utils import AsyncEngineArgs
from vllm.engine.async_llm_engine import AsyncLLMEngine
from vllm import SamplingParams
from vllm.lora.request import LoRARequest
from huggingface_hub import hf_hub_download, login
import uvicorn
import uuid
from enum import Enum

# Speech Generator 관련 임포트
from pipeline.speech_generator import SpeechGenerator, CharacterProfile, Gender

# 환경 변수 설정
os.environ["VLLM_USE_V1"] = "0"

# OpenAI API 키 설정 (Speech Generator용)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="vLLM LoRA Influencer API", version="1.0.0")

# Speech Generator 초기화
speech_generator = None
if OPENAI_API_KEY:
    speech_generator = SpeechGenerator(api_key=OPENAI_API_KEY)
    logger.info("✅ Speech Generator 초기화 완료")
else:
    logger.warning("⚠️ OPENAI_API_KEY가 설정되지 않아 Speech Generator 기능이 비활성화됩니다")

# 파인튜닝 상태 Enum
class FineTuningStatus(Enum):
    PENDING = "pending"
    PREPARING_DATA = "preparing_data"
    TRAINING = "training"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"

# 요청 모델 정의
class LoRALoadRequest(BaseModel):
    model_id: str  # 어댑터를 식별할 ID
    hf_repo_name: str  # 허깅페이스 레포 이름
    hf_token: Optional[str] = None  # 허깅페이스 액세스 토큰
    base_model_override: Optional[str] = None  # 베이스 모델 오버라이드

class GenerateRequest(BaseModel):
    user_message: str
    system_message: str = "당신은 도움이 되는 AI 어시스턴트입니다."
    influencer_name: str = "어시스턴트"
    model_id: Optional[str] = None  # 사용할 LoRA 어댑터 ID
    max_new_tokens: int = 150
    temperature: float = 0.7
    do_sample: bool = True
    use_chat_template: bool = True

class GenerateResponse(BaseModel):
    response: str
    model_id: Optional[str]
    used_adapter: bool
    formatted_prompt: str
    raw_response: str

class FineTuningRequest(BaseModel):
    influencer_id: str
    influencer_name: str
    personality: str
    qa_data: List[Dict[str, Any]]
    hf_repo_id: str
    hf_token: str
    training_epochs: int = 5
    style_info: Optional[str] = ""

class FineTuningResponse(BaseModel):
    task_id: str
    status: str
    message: str
    hf_repo_id: Optional[str] = None

class FineTuningStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    hf_model_url: Optional[str] = None

# Speech Generator 관련 모델
class VLLMCharacterProfile(BaseModel):
    name: str
    description: str
    age_range: Optional[str] = None
    gender: Gender
    personality: str
    mbti: Optional[str] = None

    class Config:
        use_enum_values = True

class VLLMQAGenerationResponse(BaseModel):
    question: str
    responses: Dict[str, List[Dict[str, Any]]]

# 전역 변수
engine: AsyncLLMEngine = None
loaded_adapters: Dict[str, Dict[str, Any]] = {}
finetuning_tasks: Dict[str, Dict[str, Any]] = {}  # 파인튜닝 작업 저장

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 비동기 엔진 초기화"""
    global engine
    logger.info("🚀 vLLM LoRA 엔진 초기화 중...")
    
    try:
        # AsyncEngineArgs 설정 (LoRA 지원 활성화)
        engine_args = AsyncEngineArgs(
            model="LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct",
            max_model_len=2048,
            tensor_parallel_size=1,
            trust_remote_code=True,
            gpu_memory_utilization=0.8,
            # LoRA 설정
            enable_lora=True,
            max_loras=8,
            max_lora_rank=64,
            lora_extra_vocab_size=256,
            max_cpu_loras=16,
            # 성능 최적화
            max_num_seqs=256,
            max_num_batched_tokens=8192,
        )
        
        engine = AsyncLLMEngine.from_engine_args(engine_args)
        logger.info("✅ vLLM LoRA 엔진 초기화 완료!")
        
    except Exception as e:
        logger.error(f"❌ vLLM 엔진 초기화 실패: {e}")
        raise e

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

def create_chat_prompt(user_message: str, system_message: str, influencer_name: str) -> str:
    """채팅 프롬프트 생성 (EXAONE 스타일)"""
    # EXAONE 모델에 최적화된 프롬프트 템플릿
    prompt = f"""[|System|] {system_message}

[|Human|] {user_message}

[|Assistant|] {influencer_name}: """
    
    return prompt

async def execute_finetuning(task_id: str):
    """파인튜닝 실행 (백그라운드 작업)"""
    task = finetuning_tasks.get(task_id)
    if not task:
        return
    
    try:
        logger.info(f"🎯 파인튜닝 실행 시작: {task_id}")
        
        # 1. 데이터 준비 단계
        task["status"] = FineTuningStatus.PREPARING_DATA.value
        task["updated_at"] = time.time()
        
        # 시스템 메시지 생성
        system_message = create_system_message(
            task["influencer_name"], 
            task["personality"], 
            task["style_info"]
        )
        
        # QA 데이터를 파인튜닝용 형식으로 변환
        finetuning_data = convert_qa_data_for_finetuning(
            task["qa_data"], 
            task["influencer_name"],
            task["personality"],
            task["style_info"]
        )
        
        # 2. 파인튜닝 실행
        task["status"] = FineTuningStatus.TRAINING.value
        task["updated_at"] = time.time()
        
        # 파인튜닝 데이터를 임시 파일로 저장
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False)
        for item in finetuning_data:
            temp_file.write(json.dumps(item, ensure_ascii=False) + '\n')
        temp_file.close()
        
        # 파인튜닝 실행 (pipeline/fine_custom.py 호출)
        hf_model_url = await run_finetuning_pipeline(
            qa_data=finetuning_data,
            system_message=system_message,
            hf_token=task["hf_token"],
            hf_repo_id=task["hf_repo_id"],
            training_epochs=task["training_epochs"]
        )
        
        if hf_model_url:
            # 3. 완료
            task["status"] = FineTuningStatus.COMPLETED.value
            task["hf_model_url"] = hf_model_url
            task["updated_at"] = time.time()
            
            logger.info(f"✅ 파인튜닝 완료: {task_id} → {hf_model_url}")
            
            # 완료된 모델을 자동으로 로드
            try:
                load_request = LoRALoadRequest(
                    model_id=task["hf_repo_id"],
                    hf_repo_name=task["hf_repo_id"],
                    hf_token=task["hf_token"]
                )
                await load_lora_adapter(load_request)
                logger.info(f"🔄 파인튜닝 완료 후 어댑터 자동 로드: {task['hf_repo_id']}")
            except Exception as e:
                logger.warning(f"⚠️ 파인튜닝 완료 후 어댑터 자동 로드 실패: {e}")
        else:
            raise Exception("파인튜닝 실행 실패: 모델 URL을 반환하지 못했습니다.")
            
    except Exception as e:
        task["status"] = FineTuningStatus.FAILED.value
        task["error_message"] = str(e)
        task["updated_at"] = time.time()
        logger.error(f"❌ 파인튜닝 실패: {task_id}, {e}")

from pipeline import fine_custom

async def run_finetuning_pipeline(qa_data: List[Dict], system_message: str, 
                                hf_token: str, hf_repo_id: str, training_epochs: int) -> Optional[str]:
    """파인튜닝 파이프라인 실행"""
    try:
        logger.info(f"🔄 파인튜닝 파이프라인 실행: {hf_repo_id}")
        
        # fine_custom.py의 main 함수를 별도의 스레드에서 실행
        hf_model_url = await asyncio.to_thread(
            fine_custom.main,
            qa_data=qa_data,
            system_message=system_message,
            hf_token=hf_token,
            hf_repo_id=hf_repo_id,
            training_epochs=training_epochs
        )
        
        if hf_model_url:
            logger.info(f"✅ 파인튜닝 파이프라인 실행 완료: {hf_repo_id}")
            return hf_model_url
        else:
            raise Exception("파인튜닝 실행 실패: 모델 URL을 반환하지 못했습니다.")
            
    except Exception as e:
        logger.error(f"❌ 파인튜닝 파이프라인 실행 실패: {e}")
        return None

# 공통 유틸리티 함수들은 backend의 utils에서 임포트 필요
# 현재는 VLLM 서버이므로 로컬 구현 유지하지만, 
# 실제 배포시에는 공통 패키지로 분리 권장

def create_system_message(influencer_name: str, personality: str, style_info: str = "") -> str:
    """시스템 메시지 생성 (VLLM 서버용)"""
    system_msg = f"""당신은 {influencer_name}입니다.

성격과 특징:
{personality}

"""
    
    if style_info:
        system_msg += f"""스타일 정보:
{style_info}

"""
    
    system_msg += f"""이 캐릭터의 성격과 말투를 완벽하게 재현하여 답변해주세요.
- 항상 캐릭터의 개성이 드러나도록 답변하세요
- 일관된 말투와 어조를 유지하세요
- 캐릭터의 특징적인 표현이나 어미를 사용하세요
- 자연스럽고 매력적인 대화를 이끌어가세요"""
    
    return system_msg

def convert_qa_data_for_finetuning(qa_data: List[Dict], influencer_name: str, 
                                 personality: str, style_info: str = "") -> List[Dict]:
    """QA 데이터를 파인튜닝용 형식으로 변환 (VLLM 서버용)"""
    finetuning_data = []

    logger.info(f"convert_qa_data_for_finetuning: Received {len(qa_data)} QA pairs.")
    if not qa_data:
        logger.warning("convert_qa_data_for_finetuning: qa_data is empty.")
        return []

    # 시스템 메시지 생성
    system_message = create_system_message(influencer_name, personality, style_info)

    for i, qa_pair in enumerate(qa_data):
        question = qa_pair.get('question', '').strip()
        answer = qa_pair.get('answer', '').strip()

        if not question:
            logger.warning(f"convert_qa_data_for_finetuning: QA pair {i} has empty question: {qa_pair}")
        if not answer:
            logger.warning(f"convert_qa_data_for_finetuning: QA pair {i} has empty answer: {qa_pair}")

        if question and answer:
            # EXAONE 모델용 채팅 형식으로 변환
            formatted_data = {
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": answer}
                ]
            }
            finetuning_data.append(formatted_data)
        else:
            logger.warning(f"convert_qa_data_for_finetuning: Skipping invalid QA pair {i}: {qa_pair}")

    logger.info(f"QA 데이터 변환 완료: {len(qa_data)}개 → {len(finetuning_data)}개")
    return finetuning_data

def clean_response(response: str, influencer_name: str) -> str:
    """응답 후처리"""
    # 기본 정리
    response = response.strip()
    
    # 특수 토큰 제거
    special_tokens = [
        "<|im_end|>", "<|endoftext|>", "[/INST]", "</s>", 
        "<|eot_id|>", "[|Human|]", "[|Assistant|]", "[|System|]"
    ]
    
    for token in special_tokens:
        response = response.replace(token, "")
    
    # 인플루언서 이름 뒤의 콜론 제거
    if response.startswith(f"{influencer_name}:"):
        response = response[len(f"{influencer_name}:"):].strip()
    
    # 너무 길면 자르기
    if len(response) > 300:
        response = response[:300] + "..."
    
    # 빈 응답인 경우 기본 응답 제공
    if not response.strip():
        response = f"안녕하세요! {influencer_name}입니다! 😊 메시지 감사해요!"
    
    return response

@app.get("/")
async def root():
    return {"message": "vLLM LoRA Influencer API가 실행 중입니다!"}

@app.get("/health")
async def health_check():
    """서버 상태 확인 엔드포인트"""
    return {"status": "ok", "message": "vLLM LoRA Influencer API 서버가 정상적으로 실행 중입니다."}

@app.post("/load_adapter")
async def load_lora_adapter(request: LoRALoadRequest):
    """LoRA 어댑터 로드"""
    if engine is None:
        raise HTTPException(status_code=500, detail="엔진이 초기화되지 않았습니다.")
    
    try:
        # 이미 로드된 어댑터인지 확인
        if request.model_id in loaded_adapters:
            logger.info(f"♻️ 어댑터 {request.model_id}는 이미 로드되어 있습니다.")
            return {
                "message": f"어댑터 {request.model_id}는 이미 로드되어 있습니다.",
                "adapter_info": loaded_adapters[request.model_id]
            }
        
        logger.info(f"🔄 LoRA 어댑터 로딩 시작: {request.hf_repo_name}")
        
        # 허깅페이스 토큰 로그인
        if request.hf_token:
            try:
                login(token=request.hf_token)
                logger.info("🔑 허깅페이스 토큰 로그인 성공")
            except Exception as e:
                logger.warning(f"⚠️ 허깅페이스 로그인 실패: {e}")
        
        # 베이스 모델 확인
        base_model_name = (
            request.base_model_override or 
            get_base_model_from_adapter(request.hf_repo_name, request.hf_token)
        )
        
        # 어댑터 정보 저장
        adapter_info = {
            "model_id": request.model_id,
            "hf_repo_name": request.hf_repo_name,
            "base_model_name": base_model_name,
            "status": "loaded",
            "lora_int_id": hash(request.model_id) % 1000000
        }
        
        loaded_adapters[request.model_id] = adapter_info
        
        logger.info(f"✅ LoRA 어댑터 로드 완료: {request.model_id}")
        
        return {
            "message": f"LoRA 어댑터 {request.model_id} 로드 완료",
            "adapter_info": adapter_info
        }
        
    except Exception as e:
        logger.error(f"❌ LoRA 어댑터 로드 실패: {e}")
        raise HTTPException(status_code=500, detail=f"어댑터 로드 실패: {str(e)}")

@app.post("/generate", response_model=GenerateResponse)
async def generate_response(request: GenerateRequest):
    """인플루언서 응답 생성"""
    if engine is None:
        raise HTTPException(status_code=500, detail="엔진이 초기화되지 않았습니다.")
    
    try:
        # 프롬프트 생성
        if request.use_chat_template:
            formatted_prompt = create_chat_prompt(
                request.user_message, 
                request.system_message, 
                request.influencer_name
            )
        else:
            formatted_prompt = f"{request.system_message}\n\n사용자: {request.user_message}\n\n{request.influencer_name}:"
        
        logger.info(f"🔍 생성된 프롬프트 (처음 200자): {formatted_prompt[:200]}...")
        
        # 샘플링 파라미터 설정
        sampling_params = SamplingParams(
            temperature=request.temperature,
            max_tokens=request.max_new_tokens,
            top_p=0.9,
            top_k=50,
            stop=["[|Human|]", "[|System|]", "<|im_end|>", "</s>", "<|eot_id|>"],
            repetition_penalty=1.1
        )
        
        # LoRA 요청 설정
        lora_request = None
        used_adapter = False
        
        if request.model_id:
            if request.model_id not in loaded_adapters:
                raise HTTPException(
                    status_code=400,
                    detail=f"어댑터 {request.model_id}가 로드되지 않았습니다. 먼저 /load_adapter를 사용하세요."
                )
            
            adapter_info = loaded_adapters[request.model_id]
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
        async for output in engine.generate(
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
        logger.error(f"❌ 응답 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"응답 생성 실패: {str(e)}")

@app.get("/adapters")
async def list_adapters():
    """로드된 어댑터 목록 조회"""
    return {
        "loaded_adapters": loaded_adapters,
        "total_count": len(loaded_adapters)
    }

@app.delete("/adapter/{model_id}")
async def unload_adapter(model_id: str):
    """어댑터 언로드"""
    if model_id not in loaded_adapters:
        raise HTTPException(status_code=404, detail=f"어댑터 {model_id}를 찾을 수 없습니다.")
    
    try:
        del loaded_adapters[model_id]
        logger.info(f"🗑️ LoRA 어댑터 언로드 완료: {model_id}")
        
        return {"message": f"어댑터 {model_id} 언로드 완료"}
        
    except Exception as e:
        logger.error(f"❌ 어댑터 언로드 실패: {e}")
        raise HTTPException(status_code=500, detail=f"어댑터 언로드 실패: {str(e)}")

@app.websocket("/ws/chat/{lora_repo}")
async def websocket_chat(websocket: WebSocket, lora_repo: str):
    """WebSocket 채팅 엔드포인트 (기존 backend와 호환)"""
    await websocket.accept()
    
    try:
        # Base64 디코딩으로 실제 repo 이름 얻기
        import base64
        try:
            decoded_repo = base64.b64decode(lora_repo).decode('utf-8')
        except:
            decoded_repo = lora_repo
        
        logger.info(f"🔗 WebSocket 연결: {decoded_repo}")
        
        # 어댑터가 로드되어 있는지 확인하고 없으면 로드
        if decoded_repo not in loaded_adapters:
            await websocket.send_text(json.dumps({
                "type": "status",
                "message": f"어댑터 {decoded_repo} 로딩 중..."
            }))
            
            # 어댑터 로드 시도
            try:
                load_request = LoRALoadRequest(
                    model_id=decoded_repo,
                    hf_repo_name=decoded_repo
                )
                await load_lora_adapter(load_request)
                
                await websocket.send_text(json.dumps({
                    "type": "status", 
                    "message": f"어댑터 {decoded_repo} 로드 완료"
                }))
            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"어댑터 로드 실패: {str(e)}"
                }))
                return
        
        while True:
            # 메시지 수신
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            user_message = message_data.get("message", "")
            system_message = message_data.get("system_message", "당신은 도움이 되는 AI 어시스턴트입니다.")
            influencer_name = message_data.get("influencer_name", "어시스턴트")
            
            if not user_message:
                continue
            
            # 응답 생성
            try:
                generate_request = GenerateRequest(
                    user_message=user_message,
                    system_message=system_message,
                    influencer_name=influencer_name,
                    model_id=decoded_repo,
                    max_new_tokens=150,
                    temperature=0.7
                )
                
                response = await generate_response(generate_request)
                
                # WebSocket으로 응답 전송
                await websocket.send_text(json.dumps({
                    "type": "response",
                    "message": response.response,
                    "model_id": response.model_id,
                    "used_adapter": response.used_adapter
                }))
                
            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"응답 생성 실패: {str(e)}"
                }))
                
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket 연결 해제: {lora_repo}")
    except Exception as e:
        logger.error(f"❌ WebSocket 오류: {e}")
        await websocket.close()

@app.post("/finetuning/start", response_model=FineTuningResponse)
async def start_finetuning(request: FineTuningRequest):
    """파인튜닝 시작"""
    try:
        # 작업 ID 생성
        task_id = f"ft_{request.influencer_id}_{int(time.time())}"
        
        # 작업 정보 저장
        finetuning_tasks[task_id] = {
            "task_id": task_id,
            "influencer_id": request.influencer_id,
            "influencer_name": request.influencer_name,
            "personality": request.personality,
            "qa_data": request.qa_data,
            "hf_repo_id": request.hf_repo_id,
            "hf_token": request.hf_token,
            "training_epochs": request.training_epochs,
            "style_info": request.style_info,
            "status": FineTuningStatus.PENDING.value,
            "created_at": time.time(),
            "updated_at": time.time()
        }
        
        logger.info(f"🎯 파인튜닝 작업 생성: {task_id}")
        
        # 백그라운드에서 파인튜닝 실행
        asyncio.create_task(execute_finetuning(task_id))
        
        return FineTuningResponse(
            task_id=task_id,
            status=FineTuningStatus.PENDING.value,
            message=f"파인튜닝 작업 {task_id} 시작됨",
            hf_repo_id=request.hf_repo_id
        )
        
    except Exception as e:
        logger.error(f"❌ 파인튜닝 시작 실패: {e}")
        raise HTTPException(status_code=500, detail=f"파인튜닝 시작 실패: {str(e)}")

@app.get("/finetuning/status/{task_id}", response_model=FineTuningStatusResponse)
async def get_finetuning_status(task_id: str):
    """파인튜닝 상태 조회"""
    if task_id not in finetuning_tasks:
        raise HTTPException(status_code=404, detail=f"파인튜닝 작업 {task_id}를 찾을 수 없습니다.")
    
    task = finetuning_tasks[task_id]
    
    return FineTuningStatusResponse(
        task_id=task_id,
        status=task["status"],
        progress=task.get("progress"),
        error_message=task.get("error_message"),
        hf_model_url=task.get("hf_model_url")
    )

@app.get("/finetuning/tasks")
async def list_finetuning_tasks():
    """파인튜닝 작업 목록"""
    return {
        "tasks": finetuning_tasks,
        "total_count": len(finetuning_tasks)
    }

@app.get("/stats")
async def get_stats():
    """서버 상태 정보"""
    return {
        "status": "running",
        "base_model": "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct",
        "loaded_adapters_count": len(loaded_adapters),
        "loaded_adapters": list(loaded_adapters.keys()),
        "finetuning_tasks_count": len(finetuning_tasks),
        "max_loras": 8,
        "max_lora_rank": 64,
        "lora_enabled": True,
        "speech_generator_enabled": speech_generator is not None
    }

# Speech Generator 엔드포인트
@app.post("/generate_qa", response_model=VLLMQAGenerationResponse)
async def generate_qa_for_character_vllm(
    character_profile: VLLMCharacterProfile
):
    """
    캐릭터 프로필에 대한 질문과 3가지 톤 변형 응답을 생성합니다.
    """
    if not speech_generator:
        raise HTTPException(
            status_code=503, 
            detail="Speech Generator가 활성화되지 않았습니다. OPENAI_API_KEY를 설정해주세요."
        )
    
    try:
        # Pydantic 모델을 dataclass로 변환
        vllm_char_profile = CharacterProfile(
            name=character_profile.name,
            description=character_profile.description,
            age_range=character_profile.age_range,
            gender=character_profile.gender,
            personality=character_profile.personality,
            mbti=character_profile.mbti
        )

        question, responses_data = speech_generator.generate_character_random_tones_sync(vllm_char_profile)

        # 응답 구조 정리
        if question in responses_data:
            actual_responses = responses_data[question]
        else:
            if responses_data:
                actual_responses = list(responses_data.values())[0]
            else:
                actual_responses = {}

        return VLLMQAGenerationResponse(
            question=question,
            responses=actual_responses
        )

    except Exception as e:
        logger.error(f"❌ Speech Generator 오류: {e}")
        raise HTTPException(status_code=500, detail=f"Speech Generator 오류: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )