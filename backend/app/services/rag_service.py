"""
RAG (Retrieval-Augmented Generation) 서비스
프로젝트 구조에 맞게 재구성된 RAG 기능
"""

import os
import logging
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import asyncio
from datetime import datetime

# Backend imports
from app.database import get_db
from app.models.user import HFTokenManage
from app.core.encryption import decrypt_sensitive_data
from app.core.config import settings
from app.services.embedding_client import VLLMEmbeddingClient, generate_embeddings
from app.services.vllm_client import vllm_health_check, get_vllm_client

logger = logging.getLogger(__name__)


@dataclass
class RAGConfig:
    """RAG 설정"""

    # 문서 처리
    min_paragraph_length: int = 30
    max_qa_pairs: int = 100

    # 검색 설정
    search_top_k: int = 3
    score_threshold: float = 0.3
    max_context_length: int = 2000

    # 생성 설정
    max_tokens: int = 512
    temperature: float = 0.8

    # 시스템 메시지
    system_message: str = (
        "당신은 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하는 AI 어시스턴트입니다. "
        "**중요**: 문서에 포함된 모든 내용은 절대 요약하거나 생략하지 말고, 원문 그대로 완전히 포함해야 합니다. "
        "사실, 수치, 날짜, 정책 내용, 세부 사항 등 모든 정보를 정확히 그대로 유지해주세요. "
        "문서 내용의 완전성과 정확성이 최우선이며, 말투와 표현 방식만 캐릭터 스타일로 조정해주세요. "
        "문서 내용을 임의로 변경, 요약, 추가하지 말고, 오직 제공된 정보를 완전히 그대로 사용해 답변해주세요."
    )
    influencer_name: str = "AI"


class RAGDocumentProcessor:
    """RAG 문서 처리기"""

    def __init__(self, config: RAGConfig):
        self.config = config

    async def process_pdf(self, pdf_path: str) -> List[Dict]:
        """PDF 문서 처리"""
        try:
            from PyPDF2 import PdfReader
            import re

            logger.info(f"📄 PDF 처리 시작: {pdf_path}")

            # PDF 읽기
            with open(pdf_path, "rb") as file:
                reader = PdfReader(file)
                text_content = ""

                for page_num, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    text_content += f"\n--- 페이지 {page_num + 1} ---\n{page_text}\n"

            # 텍스트 청킹
            chunks = self._create_chunks(text_content)

            # QA 쌍 생성
            qa_pairs = await self._generate_qa_pairs(chunks)

            logger.info(f"✅ PDF 처리 완료: {len(qa_pairs)}개 QA 쌍 생성")
            return qa_pairs

        except Exception as e:
            logger.error(f"❌ PDF 처리 실패: {e}")
            raise

    def _create_chunks(self, text: str) -> List[str]:
        """텍스트를 청크로 분할"""
        # 문단 단위로 분할
        paragraphs = re.split(r"\n\s*\n", text)

        chunks = []
        current_chunk = ""

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if len(paragraph) < self.config.min_paragraph_length:
                continue

            if len(current_chunk + paragraph) > 1000:  # 청크 크기 제한
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                current_chunk += "\n" + paragraph

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    async def _generate_qa_pairs(self, chunks: List[str]) -> List[Dict]:
        """청크에서 QA 쌍 생성"""
        qa_pairs = []

        for i, chunk in enumerate(chunks[: self.config.max_qa_pairs]):
            # 간단한 QA 생성 (실제로는 더 정교한 방법 사용 가능)
            question = f"이 문서의 {i+1}번째 섹션에 대해 설명해주세요."
            answer = chunk

            qa_pairs.append(
                {
                    "question": question,
                    "answer": answer,
                    "chunk_id": i,
                    "source": "document",
                    "page": i // 5 + 1,  # 대략적인 페이지 번호
                }
            )

        return qa_pairs


class RAGVectorStore:
    """RAG 벡터 스토어 (VLLM GPU 메모리 기반)"""

    def __init__(self, config: RAGConfig):
        self.config = config
        self.embedding_client = VLLMEmbeddingClient()
        self.chunks: List[Dict] = []

    async def store_qa_data(
        self, qa_data: List[Dict], source_file: str = "document.pdf"
    ) -> bool:
        """QA 데이터를 vLLM 서버의 Milvus 벡터DB에 저장"""
        try:
            logger.info(f"💾 vLLM 서버 벡터DB 저장 시작: {len(qa_data)}개")

            import httpx

            # QA 쌍을 DocumentChunk 형식으로 변환
            documents = []
            for i, qa in enumerate(qa_data):
                # 질문과 답변을 별도 문서로 저장
                question_doc = {
                    "id": f"{source_file}_q_{qa['chunk_id']}",
                    "text": qa["question"],
                    "metadata": {
                        "type": "question",
                        "source": source_file,
                        "chunk_id": qa["chunk_id"],
                        "page": qa.get("page", 1),
                    },
                }

                answer_doc = {
                    "id": f"{source_file}_a_{qa['chunk_id']}",
                    "text": qa["answer"],
                    "metadata": {
                        "type": "answer",
                        "source": source_file,
                        "chunk_id": qa["chunk_id"],
                        "page": qa.get("page", 1),
                    },
                }

                documents.extend([question_doc, answer_doc])

            # vLLM 서버의 벡터DB API 호출
            vllm_url = settings.VLLM_BASE_URL or "http://localhost:8001"
            logger.info(f"🔗 vLLM 서버 URL: {vllm_url}")
            logger.info(f"📊 저장할 문서 수: {len(documents)}개")

            async with httpx.AsyncClient(timeout=60.0) as client:
                logger.info(
                    f"📤 vLLM 서버로 요청 전송: {vllm_url}/vector-db/embed-and-store"
                )
                response = await client.post(
                    f"{vllm_url}/vector-db/embed-and-store",
                    json={"documents": documents},
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ vLLM 서버 벡터DB 저장 완료: {result}")
                    return True
                else:
                    logger.error(
                        f"❌ vLLM 서버 벡터DB 저장 실패: {response.status_code}"
                    )
                    logger.error(f"❌ 응답 내용: {response.text}")
                    return False

        except Exception as e:
            logger.error(f"❌ vLLM 서버 벡터DB 저장 실패: {e}")
            return False

    async def search_similar(
        self, query: str, top_k: int = 5, score_threshold: float = None
    ) -> List[Dict]:
        """vLLM 서버의 Milvus 벡터DB에서 유사한 문서 검색"""
        try:
            import httpx

            # vLLM 서버의 벡터 검색 API 호출
            vllm_url = settings.VLLM_BASE_URL or "http://localhost:8001"

            async with httpx.AsyncClient(timeout=30.0) as client:
                # score_threshold 설정 (파라미터 우선, 기본값 사용)
                if score_threshold is None:
                    score_threshold = getattr(self.config, "score_threshold", 0.3)
                logger.info(
                    f"🔍 검색 파라미터: query='{query}', top_k={top_k}, score_threshold={score_threshold}"
                )

                response = await client.post(
                    f"{vllm_url}/vector-db/embed-and-search",
                    params={
                        "query": query,
                        "top_k": top_k,
                        "score_threshold": score_threshold,
                    },
                )

                if response.status_code == 200:
                    search_results = response.json()
                    logger.info(
                        f"🔍 vLLM 벡터DB 검색 완료: {len(search_results)}개 결과"
                    )
                    logger.info(f"📊 검색 결과 상세: {search_results}")
                    return search_results
                else:
                    logger.error(f"❌ vLLM 벡터DB 검색 실패: {response.status_code}")
                    logger.error(f"❌ 응답 내용: {response.text}")
                    return []

        except Exception as e:
            logger.error(f"❌ vLLM 벡터DB 검색 실패: {e}")
            return []

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """코사인 유사도 계산"""
        import numpy as np

        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


class RAGChatGenerator:
    """RAG 채팅 생성기"""

    def __init__(self, config: RAGConfig):
        self.config = config

    async def generate_response(
        self,
        query: str,
        context: str,
        system_message: str = None,
        influencer_name: str = None,
    ) -> str:
        """컨텍스트 기반 응답 생성"""
        try:
            # VLLM 서버 상태 확인
            if not await vllm_health_check():
                logger.warning("⚠️ VLLM 서버 연결 불안정, 기본 응답 사용")
                return f"죄송합니다. 현재 서버 상태가 불안정합니다. 질문: {query}"

            # 시스템 메시지 구성
            system_msg = system_message or self.config.system_message
            influencer = influencer_name or self.config.influencer_name

            # 컨텍스트가 포함된 프롬프트 구성
            prompt = f"""시스템: {system_msg}

참고 문서:
{context}

사용자: {query}

{influencer}: """

            # VLLM 클라이언트로 응답 생성
            vllm_client = await get_vllm_client()

            response = await vllm_client.generate_response(
                user_message=query,
                system_message=system_msg,
                influencer_name=influencer,
                context=context,
                max_new_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )

            return response

        except Exception as e:
            logger.error(f"❌ 응답 생성 실패: {e}")
            return f"죄송합니다. 응답 생성 중 오류가 발생했습니다: {str(e)}"


class RAGService:
    """RAG 서비스 메인 클래스"""

    def __init__(self, config: RAGConfig = None):
        self.config = config or RAGConfig()
        self.document_processor = RAGDocumentProcessor(self.config)
        self.vector_store = RAGVectorStore(self.config)
        self.chat_generator = RAGChatGenerator(self.config)
        self._pipelines: Dict[int, Dict] = {}  # group_id별 파이프라인

    async def create_pipeline(
        self,
        group_id: int,
        pdf_path: str,
        system_message: str = None,
        influencer_name: str = None,
    ) -> bool:
        """VLLM GPU RAG 파이프라인 생성"""
        try:
            logger.info(f"🚀 VLLM GPU RAG 파이프라인 생성 시작: group_id={group_id}")

            # 1. 문서 처리
            qa_data = await self.document_processor.process_pdf(pdf_path)

            # 2. VLLM GPU 메모리에 저장
            success = await self.vector_store.store_qa_data(qa_data, pdf_path)

            if success:
                # 3. 파이프라인 정보 저장
                self._pipelines[group_id] = {
                    "pdf_path": pdf_path,
                    "qa_count": len(qa_data),
                    "system_message": system_message or self.config.system_message,
                    "influencer_name": influencer_name or self.config.influencer_name,
                    "created_at": datetime.now().isoformat(),
                }

                logger.info(
                    f"✅ VLLM GPU RAG 파이프라인 생성 완료: group_id={group_id}"
                )
                return True
            else:
                logger.error(
                    f"❌ VLLM GPU RAG 파이프라인 생성 실패: group_id={group_id}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ VLLM GPU RAG 파이프라인 생성 중 오류: {e}")
            return False

    async def chat(
        self, group_id: int, query: str, include_sources: bool = True
    ) -> Dict:
        """VLLM GPU RAG 채팅"""
        try:
            # 파이프라인 확인
            if group_id not in self._pipelines:
                return {
                    "error": "파이프라인이 없습니다. 먼저 문서를 업로드해주세요.",
                    "query": query,
                    "response": "",
                    "sources": [],
                    "timestamp": datetime.now().isoformat(),
                }

            pipeline_info = self._pipelines[group_id]

            # 1. VLLM GPU 메모리에서 유사한 문서 검색
            search_results = await self.vector_store.search_similar(
                query, top_k=self.config.search_top_k
            )

            # 2. 컨텍스트 구성
            context = self._build_context(search_results)

            # 3. 응답 생성
            response = await self.chat_generator.generate_response(
                query=query,
                context=context,
                system_message=pipeline_info["system_message"],
                influencer_name=pipeline_info["influencer_name"],
            )

            # 4. 결과 구성
            result = {
                "query": query,
                "response": response,
                "timestamp": datetime.now().isoformat(),
                "model_info": {
                    "influencer_name": pipeline_info["influencer_name"],
                    "system_message": pipeline_info["system_message"],
                },
            }

            # 출처 정보 포함
            if include_sources and search_results:
                result["sources"] = [
                    {
                        "text": (
                            item["text"][:200] + "..."
                            if len(item["text"]) > 200
                            else item["text"]
                        ),
                        "score": item["score"],
                        "source": item["metadata"]["source"],
                        "page": item["metadata"]["page"],
                    }
                    for item in search_results[:3]  # 상위 3개만
                ]
                result["context_preview"] = (
                    context[:200] + "..." if len(context) > 200 else context
                )

            return result

        except Exception as e:
            logger.error(f"❌ VLLM GPU RAG 채팅 실패: {e}")
            return {
                "error": f"VLLM GPU 채팅 중 오류가 발생했습니다: {str(e)}",
                "query": query,
                "response": "",
                "sources": [],
                "timestamp": datetime.now().isoformat(),
            }

    def _build_context(self, search_results: List[Dict]) -> str:
        """검색 결과로부터 컨텍스트 구성"""
        if not search_results:
            return ""

        context_parts = []
        for item in search_results:
            context_parts.append(f"참고 문서: {item['text']}")

        return "\n\n".join(context_parts)

    def get_pipeline_info(self, group_id: int) -> Optional[Dict]:
        """파이프라인 정보 조회"""
        return self._pipelines.get(group_id)

    def list_pipelines(self) -> List[Dict]:
        """모든 파이프라인 목록"""
        return [
            {"group_id": group_id, **info} for group_id, info in self._pipelines.items()
        ]

    async def cleanup_pipeline(self, group_id: int) -> bool:
        """파이프라인 정리"""
        try:
            if group_id in self._pipelines:
                del self._pipelines[group_id]
                logger.info(f"✅ 파이프라인 정리 완료: group_id={group_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ 파이프라인 정리 실패: {e}")
            return False


# 전역 RAG 서비스 인스턴스
_rag_service = None


def get_rag_service() -> RAGService:
    """전역 RAG 서비스 인스턴스 반환"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
