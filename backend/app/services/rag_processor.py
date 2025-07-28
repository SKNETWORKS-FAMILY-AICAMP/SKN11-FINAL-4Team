"""
RAG 분기처리 프로세서
1. 문서에서 임계값을 넘는 top_k 문서들을 검색
2. 가장 유사도가 높은 문서를 호출
3. 결과 후처리 openai로 자연스러운 자연어로 후처리
4. SLLM 모델로 말투 자연어로 후처리
5. 임계값을 넘는 문서들이 없으면 MCP로 넘어감
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from app.services.openai_service_simple import OpenAIService
from app.services.vllm_client import (
    vllm_generate_response,
    vllm_health_check,
    get_vllm_client,
)
from app.services.rag_service import get_rag_service, RAGService

logger = logging.getLogger(__name__)


@dataclass
class RAGProcessorConfig:
    """RAG 프로세서 설정"""

    top_k: int = 5
    similarity_threshold: float = 0.5
    max_context_length: int = 2000
    max_tokens: int = 1024
    temperature: float = 0.8


class RAGProcessor:
    """RAG 분기처리 프로세서"""

    def __init__(self, config: RAGProcessorConfig = None):
        self.config = config or RAGProcessorConfig()
        self.openai_service = OpenAIService()
        self.rag_service = get_rag_service()

    async def should_use_rag(self, message: str) -> bool:
        """메시지가 RAG 사용이 필요한지 확인"""
        try:
            logger.info("🔍 RAG 사용 여부 판단 시작:")
            logger.info(f"  - 사용자 메시지: {message}")

            # OpenAI를 사용한 지능적 판단
            prompt = f"""
다음 사용자 메시지가 문서 검색이나 지식베이스 조회가 필요한지 판단해주세요.

사용자 메시지: {message}

다음 중 하나라도 해당되면 'YES'를, 그렇지 않으면 'NO'를 답변해주세요:
- 문서 내용 검색 (특정 문서나 자료에서 정보 찾기)
- 지식베이스 조회 (저장된 정보나 데이터에서 답변 찾기)
- 업무 관련 정보 (회사 문서, 매뉴얼, 가이드라인 등)
- 기술 문서 검색 (API 문서, 사용법, 설정 등)
- FAQ나 도움말 검색
- 기타 저장된 정보 검색

다음은 RAG를 사용하지 않는 경우입니다:
- 수학 계산 (덧셈, 뺄셈, 곱셈, 나눗셈 등)
- 날씨 정보 (현재 날씨, 예보 등)
- 실시간 정보 (뉴스, 최신 정보 등)
- 일반적인 대화나 인사

답변 (YES/NO만):
"""
            logger.info("🧠 OpenAI를 사용한 RAG 사용 여부 분석 중...")
            response = await self.openai_service.openai_tool_selection(
                user_prompt=prompt,
                system_prompt="당신은 RAG 사용 여부를 판단하는 AI입니다. YES 또는 NO로만 답변하세요.",
            )
            response_text = response.strip().upper()
            should_use = "YES" in response_text
            logger.info(f"📊 RAG 사용 여부 판단 결과:")
            logger.info(f"  - OpenAI 응답: {response_text}")
            logger.info(f"  - RAG 사용 여부: {should_use}")
            logger.info("🔍 RAG 사용 여부 판단 완료")
            return should_use
        except Exception as e:
            logger.error(f"❌ RAG 사용 여부 판단 실패: {e}")
            return False

    async def process_with_rag(
        self,
        message: str,
        group_id: int = None,
        influencer_name: str = None,
        system_message: str = None,
    ) -> Tuple[Optional[str], List[Dict], bool]:
        """
        RAG 분기처리 메인 함수
        Returns: (response, sources, should_fallback_to_mcp)
        """
        try:
            logger.info("=" * 50)
            logger.info("🚀 RAG 프로세서 처리 시작")
            logger.info(f"📝 사용자 메시지: {message}")
            logger.info("=" * 50)

            # 1단계: RAG 사용 필요 여부 판단
            should_use_rag = await self.should_use_rag(message)
            logger.info(f"🔍 RAG 사용 필요 여부: {should_use_rag}")
            if not should_use_rag:
                logger.info("❌ RAG 사용 불필요. MCP로 전환.")
                return None, [], True  # MCP로 전환

            # 2단계: 문서에서 임계값을 넘는 top_k 문서들을 검색
            logger.info("🔍 1단계: 문서 검색 시작")
            search_results = await self.rag_service.vector_store.search_similar(
                query=message,
                top_k=self.config.top_k,
                score_threshold=self.config.similarity_threshold,
            )

            if not search_results:
                logger.info("❌ 임계값을 넘는 문서가 없음. MCP로 전환.")
                return None, [], True  # MCP로 전환

            logger.info(f"✅ 검색 완료: {len(search_results)}개 문서 발견")

            # 3단계: 가장 유사도가 높은 문서를 호출
            logger.info("📄 2단계: 최고 유사도 문서 호출")
            best_document = search_results[0]  # 가장 유사도가 높은 문서
            logger.info(
                f"📄 최고 유사도 문서: {best_document.get('text', '')[:100]}..."
            )
            logger.info(f"📊 유사도 점수: {best_document.get('score', 0)}")

            # 4단계: 결과 후처리 openai로 자연스러운 자연어로 후처리
            logger.info("🤖 3단계: OpenAI 후처리 시작")
            openai_prompt = f"""
아래 문서 내용을 바탕으로 사용자의 질문에 답변해주세요.

사용자 질문: {message}

문서 내용:
{best_document.get('text', '')}

답변 요구사항:
- 문서 내용을 바탕으로 정확하고 명확하게 답변
- 문서에 없는 정보는 추가하지 않음
- 자연스럽고 이해하기 쉽게 작성
- 불필요한 사설이나 감탄은 제외
"""

            openai_response = await self.openai_service.openai_tool_selection(
                user_prompt=openai_prompt,
                system_prompt="당신은 문서 내용을 바탕으로 정확하고 자연스럽게 답변하는 AI입니다.",
            )
            logger.info(f"✅ OpenAI 후처리 완료: {openai_response[:100]}...")

            # 5단계: SLLM 모델로 말투 자연어로 후처리
            logger.info("🎭 4단계: SLLM 말투 후처리 시작")

            # VLLM 서버 상태 확인
            if not await vllm_health_check():
                logger.warning(
                    "VLLM 서버에 연결할 수 없어 OpenAI 결과를 그대로 사용합니다."
                )
                final_response = openai_response
            else:
                try:
                    # SLLM을 사용한 말투 변환
                    sllm_prompt = f"""
다음 내용을 {influencer_name or '친근한'} 말투로 자연스럽게 변환해주세요.

원본 내용: {openai_response}

변환 요구사항:
- {influencer_name or '친근하고 도움이 되는'} 말투로 변환
- 정보의 정확성은 유지
- 자연스럽고 대화체로 작성
- 이모지나 과도한 감탄은 제외
"""

                    vllm_client = await get_vllm_client()
                    final_response = await vllm_generate_response(
                        user_message=sllm_prompt,
                        system_message=system_message
                        or f"당신은 {influencer_name or '친근한'} AI 어시스턴트입니다.",
                        influencer_name=influencer_name or "친근한 어시스턴트",
                        model_id="default",  # 기본 모델 사용
                        max_new_tokens=self.config.max_tokens,
                        temperature=self.config.temperature,
                    )
                    logger.info(f"✅ SLLM 말투 후처리 완료: {final_response[:100]}...")
                except Exception as e:
                    logger.error(f"❌ SLLM 후처리 실패: {e}")
                    final_response = openai_response  # OpenAI 결과 사용

            # 결과 구성
            sources = []
            for result in search_results:
                sources.append(
                    {
                        "text": result.get("text", ""),
                        "score": result.get("score", 0),
                        "metadata": result.get("metadata", {}),
                    }
                )

            logger.info(f"🎯 최종 RAG 응답: {final_response}")
            logger.info(f"📋 참조 문서: {len(sources)}개")
            logger.info("=" * 50)

            return final_response, sources, False  # RAG 성공, MCP로 전환하지 않음

        except Exception as e:
            logger.error(f"❌ RAG 프로세서 처리 중 오류: {e}")
            logger.info("🔄 RAG 처리 중 오류로 MCP로 전환")
            logger.info("=" * 50)
            return None, [], True  # MCP로 전환


# 전역 RAG 프로세서 인스턴스
rag_processor = RAGProcessor()


# RAG 프로세서 함수들 (외부에서 사용)
async def should_use_rag(message: str) -> bool:
    """메시지가 RAG 사용이 필요한지 확인"""
    return await rag_processor.should_use_rag(message)


async def process_with_rag(
    message: str,
    group_id: int = None,
    influencer_name: str = None,
    system_message: str = None,
) -> Tuple[Optional[str], List[Dict], bool]:
    """RAG를 사용하여 메시지 처리"""
    return await rag_processor.process_with_rag(
        message, group_id, influencer_name, system_message
    )
