from fastapi import FastAPI, Request, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel
import requests
import json
import os
from typing import Dict, Any, Optional, List
import uvicorn
from dotenv import load_dotenv
from datetime import datetime, timedelta
import asyncio
import random
from pathlib import Path
import base64
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

load_dotenv()

app = FastAPI(title="Instagram DM Bot - Production Ready", version="1.0.0")

class InstagramConfig:
    def __init__(self):
        # Instagram Login 방식 설정
        self.INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        self.VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "AIMEX_INSTAGRAM_WEBHOOK_TOKEN")
        self.INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID")  # Instagram 사용자 ID (Facebook 페이지 ID 아님)
        self.API_VERSION = "v23.0"
        self.BASE_URL = f"https://graph.instagram.com/{self.API_VERSION}"  # Instagram Graph API 직접 사용
        
        # 개발 모드 확인
        self.DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"
        
        # 테스트 모드 (앱 검토 전)
        self.TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"

config = InstagramConfig()

# EXAONE 챗봇 클래스
class ExaoneChatBot:
    def __init__(self, base_model_name="LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct", 
                 lora_repo_id=None):
        """EXAONE 채팅봇 초기화"""
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"🤖 AI 모델 Device: {self.device}")
        
        # 캐릭터 설정
        self.character_name = "센아"
        self.character_personality = "친근하고 도움이 되는 Instagram DM 어시스턴트입니다."
        
        # 사용자별 대화 히스토리 (메모리 절약을 위해 제한)
        self.user_conversations = {}
        
        # 모델과 토크나이저 로드
        self.load_model(base_model_name, lora_repo_id)
        
    def load_model(self, base_model_name, lora_path):
        """모델과 토크나이저 로드"""
        print("🔄 AI 모델 로딩 중...")
        
        try:
            # 토크나이저 로드
            self.tokenizer = AutoTokenizer.from_pretrained(base_model_name)
            
            # 패딩 토큰 설정
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
                self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
            
            # 베이스 모델 로드
            base_model = AutoModelForCausalLM.from_pretrained(
                base_model_name,
                torch_dtype=torch.bfloat16,
                trust_remote_code=True,
                device_map="auto",
                use_cache=True
            )
            
            # LoRA 어댑터 로드 및 병합
            if os.path.exists(lora_path):
                print(f"📥 LoRA 어댑터 로딩: {lora_path}")
                self.model = PeftModel.from_pretrained(base_model, lora_path)
                print("🔧 LoRA 가중치를 베이스 모델에 병합 중...")
                self.model = self.model.merge_and_unload()
            else:
                print(f"⚠️  LoRA 어댑터를 찾을 수 없습니다: {lora_path}")
                print("📦 베이스 모델만 사용합니다.")
                self.model = base_model
                
            # 모델을 평가 모드로 설정
            self.model.eval()
            print("✅ AI 모델 로딩 완료!")
            
        except Exception as e:
            print(f"❌ AI 모델 로딩 실패: {e}")
            self.model = None
            self.tokenizer = None
    
    def create_system_message(self):
        """시스템 메시지 생성"""
        return f"""당신은 {self.character_name}이라는 Instagram DM 어시스턴트입니다. 
{self.character_personality}

다음 규칙을 따라 응답해주세요:
1. 친근하고 자연스러운 톤으로 대화하세요
2. 답변은 2-3문장으로 간결하게 해주세요  
3. 도움이 되는 정보를 제공하되 너무 길지 않게 해주세요
4. 이모지를 적절히 사용해서 친근감을 표현하세요"""
    
    def get_user_history(self, user_id: str, max_turns: int = 3):
        """사용자별 대화 히스토리 가져오기"""
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = []
        
        # 최근 대화만 유지 (메모리 절약)
        return self.user_conversations[user_id][-max_turns:]
    
    def add_to_history(self, user_id: str, user_message: str, ai_response: str):
        """대화 히스토리에 추가"""
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = []
        
        self.user_conversations[user_id].append({
            "user": user_message,
            "assistant": ai_response,
            "timestamp": datetime.now().isoformat()
        })
        
        # 메모리 절약을 위해 최근 5턴만 유지
        if len(self.user_conversations[user_id]) > 5:
            self.user_conversations[user_id] = self.user_conversations[user_id][-5:]
    
    def generate_response(self, user_message: str, user_id: str = "default"):
        """AI 응답 생성"""
        if not self.model or not self.tokenizer:
            return "죄송해요, AI 모델이 로드되지 않았습니다. 잠시 후 다시 시도해주세요! 😅"
        
        try:
            # 대화 히스토리 가져오기
            history = self.get_user_history(user_id)
            
            # 메시지 구성
            messages = [{"role": "system", "content": self.create_system_message()}]
            
            # 대화 히스토리 추가
            for turn in history:
                messages.append({"role": "user", "content": turn["user"]})
                messages.append({"role": "assistant", "content": turn["assistant"]})
            
            # 현재 사용자 메시지 추가
            messages.append({"role": "user", "content": user_message})
            
            # 채팅 템플릿 적용
            input_text = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            # 토크나이즈
            input_ids = self.tokenizer.encode(
                input_text, 
                return_tensors="pt"
            ).to(self.device)
            
            # 입력 길이 제한
            if input_ids.shape[1] > 1500:
                # 히스토리 없이 재시도
                messages = [
                    {"role": "system", "content": self.create_system_message()},
                    {"role": "user", "content": user_message}
                ]
                input_text = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True
                )
                input_ids = self.tokenizer.encode(
                    input_text, 
                    return_tensors="pt"
                ).to(self.device)
            
            # 응답 생성
            with torch.no_grad():
                outputs = self.model.generate(
                    input_ids,
                    max_new_tokens=200,  # DM용으로 짧게 제한
                    temperature=0.7,
                    top_p=0.9,
                    do_sample=True,
                    eos_token_id=self.tokenizer.eos_token_id,
                    pad_token_id=self.tokenizer.pad_token_id,
                    repetition_penalty=1.1,
                    no_repeat_ngram_size=3,
                )
            
            # 응답 디코딩
            response = self.tokenizer.decode(
                outputs[0][input_ids.shape[1]:], 
                skip_special_tokens=True
            ).strip()
            
            # 히스토리에 추가
            self.add_to_history(user_id, user_message, response)
            
            return response
            
        except Exception as e:
            print(f"❌ AI 응답 생성 오류: {e}")
            return "죄송해요, 응답을 생성하는 중에 문제가 발생했습니다. 다시 한 번 말씀해주시겠어요? 😊"

# AI 챗봇 인스턴스 (전역)
ai_chatbot = None

# 메시지 로그 저장 (실제 운영시 데이터베이스 사용)
message_logs = []

# 게시글 스케줄링을 위한 저장소
scheduled_posts = []
post_queue = []

# 게시글 업로드 관련 Pydantic 모델
class PostContent(BaseModel):
    caption: str
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    media_type: str = "IMAGE"  # IMAGE, VIDEO, REELS, STORIES
    scheduled_time: Optional[str] = None
    hashtags: Optional[List[str]] = []

class BulkPostData(BaseModel):
    posts: List[PostContent]
    interval_minutes: int = 60  # 게시글 간 간격 (분)

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 설정 확인"""
    global ai_chatbot
    
    print("🚀 Instagram DM Bot 시작")
    print(f"📊 개발 모드: {'ON' if config.DEV_MODE else 'OFF'}")
    print(f"🧪 테스트 모드: {'ON' if config.TEST_MODE else 'OFF'}")
    
    # AI 챗봇 초기화
    try:
        ai_chatbot = ExaoneChatBot()
        print("🤖 AI 챗봇 준비 완료!")
    except Exception as e:
        print(f"⚠️  AI 챗봇 초기화 실패: {e}")
        print("📝 기본 응답 시스템을 사용합니다.")
        ai_chatbot = None
    
    if config.INSTAGRAM_ACCESS_TOKEN:
        print("✅ Instagram 액세스 토큰 설정됨")
        await test_api_connection()
        
        # 게시글 스케줄러 시작
        asyncio.create_task(post_scheduler())
    else:
        print("❌ Instagram 액세스 토큰이 설정되지 않았습니다")

async def test_api_connection():
    """Instagram API 연결 및 권한 테스트"""
    try:
        print(f"🔍 토큰 검증 중...")
        print(f"   토큰 시작: {config.INSTAGRAM_ACCESS_TOKEN[:20] if config.INSTAGRAM_ACCESS_TOKEN else 'None'}...")
        print(f"   사용자 ID: {config.INSTAGRAM_USER_ID}")
        
        # 먼저 기본 연결 테스트
        url = f"{config.BASE_URL}/me"
        params = {
            "fields": "id,username,account_type",
            "access_token": config.INSTAGRAM_ACCESS_TOKEN
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            user_id = data.get('id')
            username = data.get('username', 'Unknown')
            account_type = data.get('account_type', 'Unknown')
            
            print(f"✅ Instagram 연결 성공: @{username}")
            print(f"✅ 실제 사용자 ID: {user_id}")
            print(f"✅ 계정 타입: {account_type}")
            
            # 설정된 USER_ID와 실제 ID 비교
            if config.INSTAGRAM_USER_ID != user_id:
                print(f"⚠️  USER_ID 불일치!")
                print(f"   설정값: {config.INSTAGRAM_USER_ID}")
                print(f"   실제값: {user_id}")
                print(f"   .env 파일의 INSTAGRAM_USER_ID를 {user_id}로 변경하세요")
            
            if account_type not in ['BUSINESS', 'CREATOR']:
                print("⚠️  비즈니스 또는 크리에이터 계정이 필요합니다.")
                print("   개인 계정은 Instagram API 기능이 제한됩니다.")
            
            # 추가 권한 테스트
            await test_instagram_permissions()
                
        else:
            error_info = handle_api_error(response)
            print(f"❌ Instagram API 연결 실패: {error_info['detailed_message']}")
            
            # 특정 에러 코드에 대한 상세 안내
            if response.status_code == 401:
                print("🔑 토큰이 만료되었거나 유효하지 않습니다. 새 토큰을 발급받으세요.")
            elif response.status_code == 403:
                print("🚫 권한이 부족합니다. 필요한 스코프를 확인하세요.")
            
    except Exception as e:
        print(f"❌ 연결 테스트 실패: {e}")

async def test_instagram_permissions():
    """Instagram API 권한 테스트"""
    try:
        # 미디어 업로드 권한 테스트 (실제 업로드 없이)
        print("🔍 API 권한 테스트 중...")
        
        # 1. 미디어 목록 조회 권한 테스트
        url = f"{config.BASE_URL}/{config.INSTAGRAM_USER_ID}/media"
        params = {
            "fields": "id,media_type,timestamp",
            "limit": 1,
            "access_token": config.INSTAGRAM_ACCESS_TOKEN
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            print("✅ 미디어 조회 권한 확인")
        else:
            print(f"⚠️  미디어 조회 권한 제한: {response.status_code}")
        
        # 2. 인사이트 권한 테스트 (가능한 경우)
        insights_url = f"{config.BASE_URL}/{config.INSTAGRAM_USER_ID}/insights"
        insights_params = {
            "metric": "impressions,reach",
            "period": "day",
            "access_token": config.INSTAGRAM_ACCESS_TOKEN
        }
        
        insights_response = requests.get(insights_url, params=insights_params, timeout=10)
        
        if insights_response.status_code == 200:
            print("✅ 인사이트 조회 권한 확인")
        else:
            print(f"ℹ️  인사이트 권한: 제한됨 또는 데이터 없음")
            
    except Exception as e:
        print(f"❌ 권한 테스트 오류: {e}")

def handle_api_error(response) -> Dict[str, Any]:
    """API 에러 처리 및 상세 메시지 반환"""
    try:
        error_data = response.json() if response.headers.get('content-type') == 'application/json' else {}
        error_code = error_data.get('error', {}).get('code', response.status_code)
        error_message = error_data.get('error', {}).get('message', response.text)
        
        # 일반적인 Instagram API 에러 코드 처리
        error_descriptions = {
            1: "API 서비스 일시 중단",
            2: "API 서비스 이용 불가",
            4: "API 호출 한도 초과",
            10: "권한 부족",
            17: "사용자가 요청을 거부함",
            100: "잘못된 매개변수",
            190: "액세스 토큰 관련 오류",
            200: "권한 부족",
            368: "애플리케이션이 제한됨",
            803: "일부 첨부 파일을 업로드할 수 없음"
        }
        
        detailed_message = error_descriptions.get(error_code, error_message)
        
        return {
            "error_code": error_code,
            "error_message": error_message,
            "detailed_message": detailed_message,
            "status_code": response.status_code
        }
        
    except Exception:
        return {
            "error_code": response.status_code,
            "error_message": response.text,
            "detailed_message": "알 수 없는 오류가 발생했습니다.",
            "status_code": response.status_code
        }

@app.get("/")
async def root():
    return {
        "service": "Instagram DM Bot",
        "status": "running",
        "version": "1.0.0",
        "dev_mode": config.DEV_MODE,
        "test_mode": config.TEST_MODE,
        "endpoints": {
            "webhook": "/webhook",
            "auth_callback": "/auth/callback",
            "test": "/test-message",
            "logs": "/message-logs",
            "status": "/status",
            "post": "/upload-post",
            "story": "/upload-story", 
            "reels": "/upload-reels",
            "schedule": "/schedule-post",
            "bulk": "/bulk-upload",
            "queue": "/post-queue",
            "media_types": "/media-types",
            "debug_ai": "/debug/ai",
            "test_ai": "/debug/test-ai"
        }
    }

@app.get("/status")
async def get_status():
    """현재 상태 확인"""
    return {
        "server_status": "running",
        "api_configured": bool(config.INSTAGRAM_ACCESS_TOKEN),
        "webhook_configured": bool(config.VERIFY_TOKEN),
        "instagram_user_id": config.INSTAGRAM_USER_ID,
        "api_version": config.API_VERSION,
        "api_host": "graph.instagram.com",
        "login_method": "Instagram Login",
        "dev_mode": config.DEV_MODE,
        "test_mode": config.TEST_MODE,
        "total_messages": len(message_logs),
        "last_message_time": message_logs[-1]["timestamp"] if message_logs else None,
        "scheduled_posts": len(scheduled_posts),
        "queued_posts": len(post_queue)
    }

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge")
):
    """웹훅 검증"""
    print(f"🔍 웹훅 검증 요청: mode={hub_mode}, token={hub_verify_token}")
    
    if hub_mode == "subscribe" and hub_verify_token == config.VERIFY_TOKEN:
        print("✅ 웹훅 검증 성공!")
        return int(hub_challenge)
    else:
        print("❌ 웹훅 검증 실패!")
        raise HTTPException(status_code=403, detail="Forbidden")

@app.get("/auth/callback")
async def auth_callback(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"), 
    hub_challenge: str = Query(alias="hub.challenge")
):
    """Instagram 웹훅 인증 콜백"""
    print(f"🔍 Instagram 웹훅 검증: mode={hub_mode}, token={hub_verify_token}")
    
    # VERIFY_TOKEN과 비교 (환경변수에서 설정한 값)
    if hub_mode == "subscribe" and hub_verify_token == config.VERIFY_TOKEN:
        print("✅ Instagram 웹훅 검증 성공!")
        return int(hub_challenge)
    else:
        print("❌ Instagram 웹훅 검증 실패!")
        print(f"   예상 토큰: {config.VERIFY_TOKEN}")
        print(f"   받은 토큰: {hub_verify_token}")
        raise HTTPException(status_code=403, detail="Forbidden")

@app.post("/auth/callback")
async def auth_callback_post(request: Request):
    """Instagram 웹훅 메시지 처리 (POST)"""
    try:
        body = await request.json()
        
        print(f"📨 Instagram 웹훅 수신: {datetime.now()}")
        print(json.dumps(body, indent=2, ensure_ascii=False))
        
        # 웹훅 처리
        await process_instagram_message(body)
        
        return {"status": "EVENT_RECEIVED"}
        
    except Exception as e:
        print(f"❌ 웹훅 처리 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook")
async def handle_webhook(request: Request):
    """Instagram 메시지 처리 (기존 엔드포인트)"""
    try:
        body = await request.json()
        
        # 로그 저장
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "webhook_received",
            "data": body
        }
        message_logs.append(log_entry)
        
        print(f"📨 웹훅 수신: {datetime.now()}")
        print(json.dumps(body, indent=2, ensure_ascii=False))
        
        # 메시지 처리
        await process_instagram_message(body)
        
        return {"status": "EVENT_RECEIVED"}
        
    except Exception as e:
        error_log = {
            "timestamp": datetime.now().isoformat(),
            "type": "webhook_error",
            "error": str(e)
        }
        message_logs.append(error_log)
        
        print(f"❌ 웹훅 처리 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_instagram_message(data: Dict[str, Any]):
    """메시지 처리 로직"""
    try:
        for entry in data.get("entry", []):
            if "messaging" in entry:
                for messaging_event in entry["messaging"]:
                    await handle_messaging_event(messaging_event)
                    
    except Exception as e:
        print(f"❌ 메시지 처리 오류: {e}")

async def handle_messaging_event(messaging_event: Dict[str, Any]):
    """개별 메시지 이벤트 처리"""
    sender_id = messaging_event.get("sender", {}).get("id")
    
    if "message" in messaging_event:
        message = messaging_event["message"]
        message_text = message.get("text", "")
        
        # 메시지 로그 저장
        message_log = {
            "timestamp": datetime.now().isoformat(),
            "type": "message_received",
            "sender_id": sender_id,
            "message": message_text
        }
        message_logs.append(message_log)
        
        print(f"👤 발신자: {sender_id}")
        print(f"💬 메시지: {message_text}")
        
        # 자동응답 생성 (AI 사용)
        response_text = generate_smart_response(message_text, sender_id)
        
        # 테스트 모드에서는 응답 전송 시뮬레이션
        if config.TEST_MODE:
            print(f"🧪 테스트 모드 - 응답 시뮬레이션: {response_text}")
            
            # 응답 로그 저장
            response_log = {
                "timestamp": datetime.now().isoformat(),
                "type": "response_simulated",
                "recipient_id": sender_id,
                "response": response_text
            }
            message_logs.append(response_log)
            
        else:
            # 실제 응답 전송
            success = await send_instagram_message(sender_id, response_text)
            
            # 응답 로그 저장
            response_log = {
                "timestamp": datetime.now().isoformat(),
                "type": "response_sent" if success else "response_failed",
                "recipient_id": sender_id,
                "response": response_text,
                "success": success
            }
            message_logs.append(response_log)

def generate_smart_response(message_text: str, sender_id: str = "default") -> str:
    """AI 기반 스마트 자동응답 생성"""
    global ai_chatbot
    
    # AI 챗봇이 사용 가능한 경우
    if ai_chatbot and ai_chatbot.model:
        try:
            print(f"🤖 AI 응답 생성 중: {message_text[:50]}...")
            ai_response = ai_chatbot.generate_response(message_text, sender_id)
            print(f"✅ AI 응답 완료: {ai_response[:50]}...")
            return ai_response
        except Exception as e:
            print(f"❌ AI 응답 생성 실패: {e}")
            # AI 실패 시에도 모델 기반 답변 재시도
            try:
                print("🔄 AI 모델 재시도 중...")
                # 간단한 프롬프트로 재시도
                simple_prompt = f"사용자 메시지: {message_text}\n\n친절하고 도움이 되는 답변을 해주세요."
                ai_response = ai_chatbot.generate_response(simple_prompt, sender_id)
                print(f"✅ AI 재시도 성공: {ai_response[:50]}...")
                return ai_response
            except Exception as e2:
                print(f"❌ AI 재시도도 실패: {e2}")
    
    # AI 사용 불가능한 경우에만 기본 응답
    print("📝 AI 모델 사용 불가능 - 기본 응답 사용")
    return "🙏 소중한 메시지 감사합니다!\n\n확인 후 빠른 시일 내에 답변드리겠습니다.\n\n급하신 경우 프로필의 연락처로\n직접 연락 부탁드립니다!"

async def send_instagram_message(recipient_id: str, message_text: str) -> bool:
    """Instagram 메시지 전송 - Instagram Login 방식"""
    url = f"{config.BASE_URL}/{config.INSTAGRAM_USER_ID}/messages"
    
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "messaging_type": "RESPONSE",
        "recipient": {"id": recipient_id},
        "message": {"text": message_text},
        "access_token": config.INSTAGRAM_ACCESS_TOKEN
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ 메시지 전송 성공")
            return True
        else:
            print(f"❌ 메시지 전송 실패: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 메시지 전송 오류: {e}")
        return False

# ===================== 게시글 업로드 기능 =====================

async def upload_instagram_media(media_url: str, caption: str, media_type: str = "IMAGE", hashtags: List[str] = []) -> bool:
    """Instagram 미디어 업로드 (이미지/비디오/릴스)"""
    try:
        # 해시태그 추가
        full_caption = caption
        if hashtags:
            hashtag_string = " ".join([f"#{tag}" for tag in hashtags])
            full_caption = f"{caption}\n\n{hashtag_string}"
        
        # 1단계: 미디어 컨테이너 생성
        container_id = await create_media_container(media_url, full_caption, media_type)
        if not container_id:
            return False
        
        # 2단계: 컨테이너 상태 확인 (선택사항, 하지만 권장)
        await asyncio.sleep(3 if media_type in ["VIDEO", "REELS"] else 2)  # 비디오는 더 오래 대기
        status = await check_container_status(container_id)
        
        if status.get("status_code") == "ERROR":
            print(f"❌ 컨테이너 오류: {status}")
            return False
        
        # 3단계: 게시글 발행
        success = await publish_media(container_id)
        return success
        
    except Exception as e:
        print(f"❌ 미디어 업로드 오류: {e}")
        return False

async def upload_instagram_story(image_url: str, caption: str = "") -> bool:
    """Instagram 스토리 업로드"""
    try:
        # 스토리는 별도 엔드포인트 사용
        url = f"{config.BASE_URL}/{config.INSTAGRAM_USER_ID}/media"
        
        payload = {
            "image_url": image_url,
            "media_type": "STORIES",
            "access_token": config.INSTAGRAM_ACCESS_TOKEN
        }
        
        if caption:
            payload["caption"] = caption
            
        response = requests.post(url, data=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            container_id = data.get("id")
            print(f"✅ 스토리 컨테이너 생성: {container_id}")
            
            # 스토리 발행
            await asyncio.sleep(2)
            success = await publish_media(container_id)
            return success
        else:
            error_info = handle_api_error(response)
            print(f"❌ 스토리 업로드 실패: {error_info['detailed_message']}")
            return False
            
    except Exception as e:
        print(f"❌ 스토리 업로드 오류: {e}")
        return False

async def create_media_container(media_url: str, caption: str, media_type: str = "IMAGE") -> Optional[str]:
    """미디어 컨테이너 생성 (1단계) - Instagram Login 방식"""
    url = f"{config.BASE_URL}/{config.INSTAGRAM_USER_ID}/media"
    
    # 미디어 타입에 따른 URL 키 결정
    url_key = "video_url" if media_type in ["VIDEO", "REELS"] else "image_url"
    
    payload = {
        url_key: media_url,
        "caption": caption,
        "media_type": media_type,
        "access_token": config.INSTAGRAM_ACCESS_TOKEN
    }
    
    try:
        response = requests.post(url, data=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            container_id = data.get("id")
            print(f"✅ 미디어 컨테이너 생성 성공: {container_id}")
            return container_id
        else:
            error_info = handle_api_error(response)
            print(f"❌ 미디어 컨테이너 생성 실패: {error_info['detailed_message']} (코드: {error_info['error_code']})")
            return None
            
    except Exception as e:
        print(f"❌ 미디어 컨테이너 생성 오류: {e}")
        return None

async def check_container_status(container_id: str) -> Dict[str, Any]:
    """컨테이너 상태 확인"""
    url = f"{config.BASE_URL}/{container_id}"
    
    params = {
        "fields": "status_code,status",
        "access_token": config.INSTAGRAM_ACCESS_TOKEN
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ 컨테이너 상태 확인 실패: {response.text}")
            return {}
            
    except Exception as e:
        print(f"❌ 컨테이너 상태 확인 오류: {e}")
        return {}

async def publish_media(media_id: str) -> bool:
    """게시글 발행 (2단계)"""
    url = f"{config.BASE_URL}/{config.INSTAGRAM_USER_ID}/media_publish"
    
    payload = {
        "creation_id": media_id,
        "access_token": config.INSTAGRAM_ACCESS_TOKEN
    }
    
    try:
        response = requests.post(url, data=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            post_id = data.get("id")
            print(f"✅ 게시글 발행 성공: {post_id}")
            return True
        else:
            print(f"❌ 게시글 발행 실패: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 게시글 발행 오류: {e}")
        return False

async def post_scheduler():
    """게시글 스케줄러 - 백그라운드에서 실행"""
    print("📅 게시글 스케줄러 시작...")
    
    while True:
        try:
            current_time = datetime.now()
            
            # 스케줄된 게시글 확인
            posts_to_publish = []
            for post in scheduled_posts:
                scheduled_datetime = datetime.fromisoformat(post["scheduled_time"])
                if scheduled_datetime <= current_time:
                    posts_to_publish.append(post)
            
            # 스케줄된 게시글 발행
            for post in posts_to_publish:
                print(f"📤 스케줄된 게시글 발행: {post['caption'][:30]}...")
                
                # 미디어 타입에 따라 적절한 함수 호출
                media_type = post.get("media_type", "IMAGE")
                media_url = post.get("video_url") if media_type in ["VIDEO", "REELS"] else post.get("image_url")
                
                if media_type == "STORIES":
                    success = await upload_instagram_story(media_url, post["caption"])
                else:
                    success = await upload_instagram_media(
                        media_url, 
                        post["caption"],
                        media_type,
                        post.get("hashtags", [])
                    )
                
                if success:
                    print(f"✅ 스케줄된 게시글 발행 성공")
                    # 로그 저장
                    message_logs.append({
                        "timestamp": datetime.now().isoformat(),
                        "type": "scheduled_post_published",
                        "caption": post["caption"],
                        "success": True
                    })
                else:
                    print(f"❌ 스케줄된 게시글 발행 실패")
                    message_logs.append({
                        "timestamp": datetime.now().isoformat(),
                        "type": "scheduled_post_failed",
                        "caption": post["caption"],
                        "success": False
                    })
                
                # 발행한 게시글은 스케줄에서 제거
                scheduled_posts.remove(post)
                
                # API 호출 간 딜레이
                await asyncio.sleep(5)
            
            # 큐에 있는 게시글 처리
            if post_queue:
                post = post_queue.pop(0)
                print(f"📤 큐에서 게시글 발행: {post['caption'][:30]}...")
                
                # 미디어 타입에 따라 적절한 함수 호출
                media_type = post.get("media_type", "IMAGE")
                media_url = post.get("video_url") if media_type in ["VIDEO", "REELS"] else post.get("image_url")
                
                if media_type == "STORIES":
                    success = await upload_instagram_story(media_url, post["caption"])
                else:
                    success = await upload_instagram_media(
                        media_url, 
                        post["caption"],
                        media_type,
                        post.get("hashtags", [])
                    )
                
                if success:
                    print(f"✅ 큐 게시글 발행 성공")
                else:
                    print(f"❌ 큐 게시글 발행 실패")
            
            # 30초마다 확인
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"❌ 스케줄러 오류: {e}")
            await asyncio.sleep(60)

@app.get("/message-logs")
async def get_message_logs(limit: int = 50):
    """메시지 로그 조회"""
    return {
        "total_logs": len(message_logs),
        "logs": message_logs[-limit:] if message_logs else []
    }

@app.get("/test-message")
async def test_message_endpoint(
    recipient_id: str = "test_user_123",
    message: str = "안녕하세요! 테스트 메시지입니다."
):
    """메시지 테스트"""
    if config.TEST_MODE:
        response = generate_smart_response(message)
        return {
            "status": "test_mode",
            "input_message": message,
            "generated_response": response,
            "timestamp": datetime.now().isoformat()
        }
    else:
        success = await send_instagram_message(recipient_id, message)
        return {
            "status": "sent" if success else "failed",
            "message": message,
            "recipient": recipient_id,
            "timestamp": datetime.now().isoformat()
        }

@app.get("/next-steps")
async def get_next_steps():
    """다음 단계 가이드"""
    return {
        "current_status": "웹훅 설정 완료",
        "next_steps": [
            {
                "step": 1,
                "title": "Instagram 계정에서 테스트 메시지 전송",
                "description": "본인 Instagram 계정에서 연결된 비즈니스 계정으로 DM 전송"
            },
            {
                "step": 2,
                "title": "서버 로그 확인",
                "description": "터미널에서 웹훅 수신 및 응답 로그 확인"
            },
            {
                "step": 3,
                "title": "메시지 로그 확인",
                "description": "GET /message-logs 엔드포인트로 저장된 로그 확인"
            },
            {
                "step": 4,
                "title": "Meta 앱 검토 요청",
                "description": "개발자 콘솔에서 필요한 권한들에 대한 고급 액세스 요청"
            },
            {
                "step": 5,
                "title": "프로덕션 배포",
                "description": "클라우드 서비스에 배포 후 도메인 설정"
            }
        ],
        "required_scopes": [
            "instagram_business_basic",
            "instagram_business_content_publish", 
            "instagram_business_manage_messages",
            "instagram_business_manage_comments"
        ],
        "legacy_scopes": [
            "instagram_basic",
            "instagram_content_publish",
            "instagram_manage_messages",
            "instagram_manage_comments"
        ]
    }

# ===================== 게시글 업로드 API 엔드포인트 =====================

@app.post("/upload-post")
async def upload_post_endpoint(
    caption: str = Form(...),
    image_url: str = Form(None),
    video_url: str = Form(None),
    media_type: str = Form("IMAGE"),
    hashtags: str = Form(""),
    immediate: bool = Form(True)
):
    """즉시 또는 큐에 미디어 업로드 (이미지/비디오/릴스)"""
    try:
        # 미디어 URL 검증
        media_url = video_url if media_type in ["VIDEO", "REELS"] else image_url
        if not media_url:
            raise HTTPException(status_code=400, detail="미디어 URL이 필요합니다")
        
        # 해시태그 파싱
        hashtag_list = [tag.strip() for tag in hashtags.split(",") if tag.strip()] if hashtags else []
        
        post_data = {
            "caption": caption,
            "image_url": image_url,
            "video_url": video_url,
            "media_type": media_type,
            "hashtags": hashtag_list
        }
        
        if immediate:
            # 즉시 업로드
            if media_type == "STORIES":
                success = await upload_instagram_story(media_url, caption)
            else:
                success = await upload_instagram_media(media_url, caption, media_type, hashtag_list)
            
            return {
                "status": "uploaded" if success else "failed",
                "caption": caption,
                "hashtags": hashtag_list,
                "timestamp": datetime.now().isoformat()
            }
        else:
            # 큐에 추가
            post_queue.append(post_data)
            
            return {
                "status": "queued",
                "caption": caption,
                "hashtags": hashtag_list,
                "queue_position": len(post_queue),
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/schedule-post")
async def schedule_post_endpoint(
    caption: str = Form(...),
    image_url: str = Form(...),
    scheduled_time: str = Form(...),  # ISO format: "2024-01-01T12:00:00"
    hashtags: str = Form("")
):
    """게시글 스케줄링"""
    try:
        # 시간 형식 검증
        scheduled_datetime = datetime.fromisoformat(scheduled_time)
        
        if scheduled_datetime <= datetime.now():
            raise HTTPException(status_code=400, detail="스케줄 시간은 현재 시간보다 이후여야 합니다")
        
        # 해시태그 파싱
        hashtag_list = [tag.strip() for tag in hashtags.split(",") if tag.strip()] if hashtags else []
        
        # 스케줄에 추가
        scheduled_posts.append({
            "caption": caption,
            "image_url": image_url,
            "hashtags": hashtag_list,
            "scheduled_time": scheduled_time,
            "created_at": datetime.now().isoformat()
        })
        
        return {
            "status": "scheduled",
            "caption": caption,
            "scheduled_time": scheduled_time,
            "hashtags": hashtag_list,
            "total_scheduled": len(scheduled_posts)
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 시간 형식입니다. ISO 형식을 사용하세요: 2024-01-01T12:00:00")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bulk-upload")
async def bulk_upload_endpoint(data: BulkPostData):
    """대량 게시글 업로드 (스케줄링)"""
    try:
        if not data.posts:
            raise HTTPException(status_code=400, detail="업로드할 게시글이 없습니다")
        
        current_time = datetime.now()
        scheduled_count = 0
        
        for i, post in enumerate(data.posts):
            # 간격에 따라 스케줄 시간 계산
            schedule_time = current_time + timedelta(minutes=data.interval_minutes * i)
            
            scheduled_posts.append({
                "caption": post.caption,
                "image_url": post.image_url,
                "hashtags": post.hashtags or [],
                "scheduled_time": schedule_time.isoformat(),
                "created_at": current_time.isoformat()
            })
            
            scheduled_count += 1
        
        return {
            "status": "bulk_scheduled",
            "total_posts": len(data.posts),
            "scheduled_count": scheduled_count,
            "interval_minutes": data.interval_minutes,
            "first_post_time": current_time.isoformat(),
            "last_post_time": (current_time + timedelta(minutes=data.interval_minutes * (len(data.posts) - 1))).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/post-queue")
async def get_post_queue():
    """큐 및 스케줄 상태 조회"""
    return {
        "queue": {
            "total": len(post_queue),
            "posts": post_queue[:5] if post_queue else []  # 최근 5개만 표시
        },
        "scheduled": {
            "total": len(scheduled_posts),
            "posts": sorted(scheduled_posts, key=lambda x: x["scheduled_time"])[:5] if scheduled_posts else []
        },
        "next_scheduled": scheduled_posts[0]["scheduled_time"] if scheduled_posts else None
    }

@app.delete("/clear-queue")
async def clear_queue():
    """큐 및 스케줄 초기화"""
    global post_queue, scheduled_posts
    
    queue_count = len(post_queue)
    scheduled_count = len(scheduled_posts)
    
    post_queue.clear()
    scheduled_posts.clear()
    
    return {
        "status": "cleared",
        "cleared_queue": queue_count,
        "cleared_scheduled": scheduled_count,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/post-templates")
async def get_post_templates():
    """게시글 템플릿 예시"""
    return {
        "templates": [
            {
                "name": "일상 공유",
                "caption": "오늘의 소중한 순간 ✨\n\n#{username}의 일상을 공유합니다!",
                "hashtags": ["일상", "소통", "팔로우", "좋아요"]
            },
            {
                "name": "제품 홍보",
                "caption": "새로운 제품을 소개합니다! 🎉\n\n특별 할인 이벤트 진행 중입니다.\n자세한 내용은 DM으로 문의하세요!",
                "hashtags": ["신제품", "할인", "이벤트", "쇼핑"]
            },
            {
                "name": "감사 인사",
                "caption": "항상 응원해주시는 팔로워분들께 감사드립니다 🙏\n\n더 좋은 콘텐츠로 보답하겠습니다!",
                "hashtags": ["감사", "팔로워", "소통", "사랑"]
            }
        ]
    }

@app.get("/debug/ai")
async def debug_ai():
    """AI 챗봇 상태 확인"""
    global ai_chatbot
    
    if not ai_chatbot:
        return {"status": "not_initialized", "message": "AI 챗봇이 초기화되지 않았습니다"}
    
    return {
        "status": "initialized" if ai_chatbot.model else "failed",
        "character_name": ai_chatbot.character_name,
        "personality": ai_chatbot.character_personality,
        "device": str(ai_chatbot.device),
        "active_conversations": len(ai_chatbot.user_conversations),
        "model_loaded": ai_chatbot.model is not None,
        "tokenizer_loaded": ai_chatbot.tokenizer is not None
    }

@app.post("/debug/test-ai")
async def test_ai_response(
    message: str = Form(...),
    user_id: str = Form("test_user")
):
    """AI 응답 테스트"""
    global ai_chatbot
    
    if not ai_chatbot:
        return {"error": "AI 챗봇이 초기화되지 않았습니다"}
    
    try:
        response = ai_chatbot.generate_response(message, user_id)
        return {
            "status": "success",
            "user_message": message,
            "ai_response": response,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/debug/webhooks")
async def debug_webhooks():
    """웹훅 설정 및 수신 상태 확인"""
    return {
        "webhook_config": {
            "verify_token": config.VERIFY_TOKEN,
            "endpoints": ["/webhook", "/auth/callback"],
            "test_mode": config.TEST_MODE
        },
        "recent_webhooks": message_logs[-10:] if message_logs else [],
        "total_messages": len(message_logs),
        "webhook_urls": [
            "GET /webhook - 웹훅 검증",
            "POST /webhook - 메시지 처리", 
            "GET /auth/callback - 인증 콜백 검증",
            "POST /auth/callback - 인증 콜백 메시지"
        ]
    }

@app.get("/debug/token")
async def debug_token():
    """토큰 디버깅 정보"""
    if not config.INSTAGRAM_ACCESS_TOKEN:
        return {"error": "토큰이 설정되지 않았습니다"}
    
    try:
        # 토큰 기본 정보
        token_info = {
            "token_length": len(config.INSTAGRAM_ACCESS_TOKEN),
            "token_prefix": config.INSTAGRAM_ACCESS_TOKEN[:10] + "..." if config.INSTAGRAM_ACCESS_TOKEN else None,
            "user_id": config.INSTAGRAM_USER_ID,
            "api_version": config.API_VERSION,
            "base_url": config.BASE_URL
        }
        
        # API 테스트
        url = f"{config.BASE_URL}/me"
        params = {
            "fields": "id,username,account_type",
            "access_token": config.INSTAGRAM_ACCESS_TOKEN
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        return {
            "token_info": token_info,
            "api_test": {
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else response.text,
                "url": url
            }
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.post("/debug/test-webhook")
async def test_webhook(request: Request):
    """웹훅 테스트 (수동 메시지 시뮬레이션)"""
    try:
        # 테스트 메시지 데이터
        test_message = {
            "object": "instagram",
            "entry": [{
                "id": "test_entry",
                "time": 1234567890,
                "messaging": [{
                    "sender": {"id": "test_user_123"},
                    "recipient": {"id": config.INSTAGRAM_USER_ID},
                    "timestamp": 1234567890,
                    "message": {
                        "mid": "test_mid_123",
                        "text": "안녕하세요! 테스트 메시지입니다."
                    }
                }]
            }]
        }
        
        print("🧪 웹훅 테스트 메시지 처리 중...")
        await process_instagram_message(test_message)
        
        return {
            "status": "success",
            "message": "테스트 웹훅 처리 완료",
            "test_data": test_message
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.post("/upload-story")
async def upload_story_endpoint(
    image_url: str = Form(...),
    caption: str = Form(""),
    immediate: bool = Form(True)
):
    """Instagram 스토리 업로드"""
    try:
        if immediate:
            success = await upload_instagram_story(image_url, caption)
            
            return {
                "status": "uploaded" if success else "failed",
                "caption": caption,
                "media_type": "STORIES",
                "timestamp": datetime.now().isoformat()
            }
        else:
            # 스토리 큐에 추가
            story_data = {
                "caption": caption,
                "image_url": image_url,
                "media_type": "STORIES"
            }
            post_queue.append(story_data)
            
            return {
                "status": "queued",
                "caption": caption,
                "media_type": "STORIES",
                "queue_position": len(post_queue),
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-reels")
async def upload_reels_endpoint(
    video_url: str = Form(...),
    caption: str = Form(...),
    hashtags: str = Form(""),
    immediate: bool = Form(True)
):
    """Instagram 릴스 업로드"""
    try:
        hashtag_list = [tag.strip() for tag in hashtags.split(",") if tag.strip()] if hashtags else []
        
        if immediate:
            success = await upload_instagram_media(video_url, caption, "REELS", hashtag_list)
            
            return {
                "status": "uploaded" if success else "failed",
                "caption": caption,
                "media_type": "REELS",
                "hashtags": hashtag_list,
                "timestamp": datetime.now().isoformat()
            }
        else:
            # 릴스 큐에 추가
            reels_data = {
                "caption": caption,
                "video_url": video_url,
                "media_type": "REELS",
                "hashtags": hashtag_list
            }
            post_queue.append(reels_data)
            
            return {
                "status": "queued",
                "caption": caption,
                "media_type": "REELS",
                "hashtags": hashtag_list,
                "queue_position": len(post_queue),
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/media-types")
async def get_media_types():
    """지원하는 미디어 타입 정보"""
    return {
        "supported_types": {
            "IMAGE": {
                "description": "일반 이미지 게시글",
                "formats": ["JPG", "PNG"],
                "max_size": "8MB",
                "url_field": "image_url"
            },
            "VIDEO": {
                "description": "일반 비디오 게시글",
                "formats": ["MP4", "MOV"],
                "max_size": "100MB",
                "max_duration": "60초",
                "url_field": "video_url"
            },
            "REELS": {
                "description": "Instagram 릴스",
                "formats": ["MP4"],
                "max_size": "100MB",
                "duration": "15초-90초",
                "url_field": "video_url"
            },
            "STORIES": {
                "description": "Instagram 스토리",
                "formats": ["JPG", "PNG", "MP4"],
                "max_size": "30MB",
                "duration": "최대 15초 (비디오)",
                "url_field": "image_url 또는 video_url"
            }
        },
        "usage_tips": [
            "모든 미디어는 공개적으로 접근 가능한 URL이어야 합니다",
            "비디오는 업로드 시 처리 시간이 더 걸립니다",
            "스토리는 24시간 후 자동 삭제됩니다",
            "릴스는 해시태그와 캡션이 중요합니다"
        ]
    }

if __name__ == "__main__":
    print("🚀 Instagram DM Bot (Instagram Login v23.0) 시작...")
    print("📋 API 호스트: graph.instagram.com/v23.0")
    print("📊 상태 확인: http://localhost:8000/status")
    print("📝 로그 확인: http://localhost:8000/message-logs")
    print("🔧 미디어 타입: http://localhost:8000/media-types")
    print()
    print("📋 필요한 .env 설정:")
    print("INSTAGRAM_ACCESS_TOKEN=your_instagram_access_token")
    print("INSTAGRAM_USER_ID=your_instagram_user_id")
    print("WEBHOOK_VERIFY_TOKEN=your_webhook_verify_token")
    print()
    
    uvicorn.run(
        "instaDM:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
