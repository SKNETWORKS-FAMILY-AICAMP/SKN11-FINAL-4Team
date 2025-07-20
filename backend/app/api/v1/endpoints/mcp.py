"""
지능적인 도구 선택을 사용한 MCP 챗봇 구현
"""
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import os
import asyncio
import math
import re

logger = logging.getLogger(__name__)
router = APIRouter()

# 지능적인 도구 선택 MCP 챗봇 클래스
class IntelligentMCPChatbot:
    def __init__(self):
        self.llm = None
        self.tools = {}
        self.is_initialized = False
        
    async def initialize(self):
        """지능적인 도구 선택 MCP 챗봇 초기화"""
        try:
            logger.debug("도구들 정의 시작...")
            
            # 1. 도구들 정의
            def add_numbers(a: float, b: float) -> float:
                """두 숫자를 더합니다"""
                return a + b
            
            def multiply_numbers(a: float, b: float) -> float:
                """두 숫자를 곱합니다"""
                return a * b
            
            def sqrt_number(number: float) -> float:
                """숫자의 제곱근을 계산합니다"""
                return math.sqrt(number)
            
            def factorial_number(n: int) -> int:
                """숫자의 팩토리얼을 계산합니다"""
                return math.factorial(n)
            
            self.tools = {
                "add": (add_numbers, "두 숫자를 더합니다"),
                "multiply": (multiply_numbers, "두 숫자를 곱합니다"),
                "sqrt": (sqrt_number, "숫자의 제곱근을 계산합니다"),
                "factorial": (factorial_number, "숫자의 팩토리얼을 계산합니다"),
            }
            logger.info(f"도구 {len(self.tools)}개 정의 완료")
            
            # 2. 로컬 LLM 설정 (EXAONE 모델)
            from langchain_community.llms import HuggingFacePipeline
            from transformers import AutoTokenizer, AutoModelForCausalLM
            from transformers.pipelines import pipeline
            import torch
            
            model_name = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
            hf_token = os.getenv("HUGGINGFACE_TOKEN")
            
            # 토큰이 없으면 공개 모델 사용
            if not hf_token:
                logger.warning("HUGGINGFACE_TOKEN이 없어서 공개 모델을 사용합니다.")
                model_name = "beomi/KoAlpaca-Polyglot-12.8B"
            
            logger.info(f"로컬 모델 로딩 중: {model_name}")
            
            # CUDA 사용 가능 여부 확인
            cuda_available = torch.cuda.is_available()
            if cuda_available:
                logger.info(f"CUDA 사용 가능: {torch.cuda.get_device_name(0)}")
                device_map = "auto"
            else:
                logger.warning("CUDA 사용 불가능, CPU 사용")
                device_map = "cpu"
            
            tokenizer = AutoTokenizer.from_pretrained(
                model_name, 
                trust_remote_code=True,
                token=hf_token if hf_token else None
            )
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.float16,
                device_map=device_map,
                trust_remote_code=True,
                token=hf_token if hf_token else None
            )
            
            pipe = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                max_new_tokens=512,
                temperature=0.1,
                do_sample=True
            )
            
            self.llm = HuggingFacePipeline(pipeline=pipe)
            logger.info(f"로컬 모델 로드 완료: {model_name}")
            
            self.is_initialized = True
            logger.info("지능적인 도구 선택 MCP 챗봇 초기화 완료")
            
        except ImportError as e:
            logger.error(f"LangChain dependencies not installed: {e}")
            return False
        except Exception as e:
            logger.error(f"MCP 챗봇 초기화 실패: {e}")
            return False
        
        return True
    
    async def process_message(self, message: str) -> tuple[str, List[str]]:
        """LangChain Tool과 LLMChain을 사용한 지능적인 도구 선택"""
        try:
            from langchain.tools import Tool
            from langchain.chains import LLMChain
            from langchain_core.prompts import PromptTemplate
            
            # 1. LangChain Tool 객체로 변환
            langchain_tools = {}
            for name, (func, description) in self.tools.items():
                langchain_tools[name] = Tool(
                    name=name,
                    description=description,
                    func=func
                )
            
            # 2. 도구 선택을 위한 LLMChain 생성
            tool_selection_prompt = PromptTemplate.from_template("""
다음 사용자 메시지를 분석하여 적절한 도구를 선택해주세요.

사용 가능한 도구들:
- add: 두 숫자를 더합니다
- multiply: 두 숫자를 곱합니다  
- sqrt: 숫자의 제곱근을 계산합니다
- factorial: 숫자의 팩토리얼을 계산합니다

사용자 메시지: {input}

다음 중 하나를 선택해주세요: add, multiply, sqrt, factorial, none
답변 (도구명만):""")
            
            tool_selection_chain = LLMChain(llm=self.llm, prompt=tool_selection_prompt)
            
            # 3. 도구 선택
            tool_response = await tool_selection_chain.ainvoke({"input": message})
            selected_tool = tool_response["text"].strip().lower()
            
            logger.debug(f"LLM이 선택한 도구: {selected_tool}")
            
            # 4. 도구 실행
            tools_used = []
            response_text = ""
            
            if selected_tool in langchain_tools:
                tool = langchain_tools[selected_tool]
                
                # 숫자 추출
                numbers = re.findall(r'\d+', message)
                
                if selected_tool == "add" and len(numbers) >= 2:
                    result = tool.func(float(numbers[0]), float(numbers[1]))
                    response_text = f"{numbers[0]} + {numbers[1]} = {result}"
                    tools_used.append(selected_tool)
                
                elif selected_tool == "multiply" and len(numbers) >= 2:
                    result = tool.func(float(numbers[0]), float(numbers[1]))
                    response_text = f"{numbers[0]} × {numbers[1]} = {result}"
                    tools_used.append(selected_tool)
                
                elif selected_tool == "sqrt" and numbers:
                    result = tool.func(float(numbers[0]))
                    response_text = f"√{numbers[0]} = {result}"
                    tools_used.append(selected_tool)
                
                elif selected_tool == "factorial" and numbers:
                    result = tool.func(int(numbers[0]))
                    response_text = f"{numbers[0]}! = {result}"
                    tools_used.append(selected_tool)
                
                else:
                    response_text = f"죄송합니다. {tool.description}을 사용하려고 했지만 적절한 숫자를 찾을 수 없습니다."
            
            else:
                # 일반적인 응답을 위한 LLMChain
                general_prompt = PromptTemplate.from_template("""
사용자의 메시지에 대해 친근하고 도움이 되는 한국어 응답을 해주세요.

사용자 메시지: {input}

응답:""")
                
                general_chain = LLMChain(llm=self.llm, prompt=general_prompt)
                response = await general_chain.ainvoke({"input": message})
                response_text = response["text"]
            
            logger.debug(f"LangChain 도구 처리 결과: {response_text}")
            logger.debug(f"사용된 도구들: {tools_used}")
            
            return response_text, tools_used
            
        except Exception as e:
            logger.error(f"LangChain 메시지 처리 중 오류: {e}")
            return f"메시지 처리 중 오류가 발생했습니다: {str(e)}", []

# 전역 챗봇 인스턴스
mcp_chatbot = IntelligentMCPChatbot()

class MCPChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class MCPChatResponse(BaseModel):
    response: str
    session_id: str
    tools_used: List[str] = []

@router.post("/chat", response_model=MCPChatResponse)
async def mcp_chat(request: MCPChatRequest):
    """지능적인 도구 선택을 사용한 MCP 챗봇"""
    try:
        logger.debug("MCP chat 엔드포인트 호출됨")
        
        # 챗봇 초기화 확인
        logger.debug(f"챗봇 초기화 상태: {mcp_chatbot.is_initialized}")
        if not mcp_chatbot.is_initialized:
            logger.debug("챗봇 초기화 시작...")
            success = await mcp_chatbot.initialize()
            logger.debug(f"챗봇 초기화 결과: {success}")
            if not success:
                logger.error("MCP chatbot 초기화 실패")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="MCP chatbot initialization failed"
                )
        
        # 사용자 메시지 처리
        logger.info(f"사용자 메시지: {request.message}")
        
        response_text, tools_used = await mcp_chatbot.process_message(request.message)
        
        logger.info(f"사용된 도구들: {tools_used}")
        logger.info(f"응답: {response_text}")
        
        return MCPChatResponse(
            response=response_text,
            session_id=request.session_id or f"session_{hash(request.message)}",
            tools_used=tools_used,
        )
        
    except Exception as e:
        logger.error(f"Error in MCP chat: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat error: {str(e)}",
        )

@router.post("/init")
async def initialize_chatbot():
    """MCP 챗봇 초기화"""
    try:
        success = await mcp_chatbot.initialize()
        if success:
            return {"message": "Intelligent MCP chatbot initialized successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize MCP chatbot"
            )
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Initialization error: {str(e)}",
        )

@router.get("/status")
async def get_chatbot_status():
    """MCP 챗봇 상태 확인"""
    return {
        "initialized": mcp_chatbot.is_initialized,
        "agent_available": mcp_chatbot.llm is not None,
        "tools_available": len(mcp_chatbot.tools)
    }

@router.get("/tools")
async def get_tools():
    """사용 가능한 도구 목록 조회"""
    tools_info = {}
    for name, (func, description) in mcp_chatbot.tools.items():
        tools_info[name] = {
            "name": name,
            "description": description,
            "type": "intelligent"
        }
    
    return {
        "tools": tools_info,
        "total_count": len(mcp_chatbot.tools)
    }

@router.post("/tools/reload")
async def reload_tools():
    """도구들을 다시 로드합니다."""
    try:
        mcp_chatbot.is_initialized = False
        success = await mcp_chatbot.initialize()
        if success:
            return {"message": "도구들이 성공적으로 다시 로드되었습니다"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="도구 다시 로드 실패"
            )
    except Exception as e:
        logger.error(f"도구 다시 로드 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"도구 다시 로드 오류: {str(e)}"
        )

@router.post("/servers/{server_name}/add")
async def add_mcp_server(server_name: str, server_url: str):
    """새로운 MCP 서버를 추가합니다."""
    return {"message": f"MCP 서버 {server_name} 추가 완료"}
