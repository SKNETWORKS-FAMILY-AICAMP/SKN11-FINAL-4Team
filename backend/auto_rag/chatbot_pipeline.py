import os
import sys
import json
import asyncio
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

# backend 경로 추가
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

# SQLAlchemy import 추가
from sqlalchemy.orm import Session

# 기존 import들
from rag_search import RAGSearcher, SearchConfig, retrieve_relevant_chunks
from chat_generator import (
    ChatGenerator, 
    VLLMGenerationConfig, 
    PromptTemplate, 
    truncate_history_by_char,
    TextNormalizer,
    ModelIdValidator
)
from embed_store import EmbeddingStore
from document_loader import PDFToQAProcessor

# 환경변수에도 설정 (전체 시스템 동기화)
from dotenv import load_dotenv
load_dotenv()

# VLLM 설정 - 환경 변수 우선, 없으면 기본값 사용
DYNAMIC_VLLM_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000")

try:
    from app.services.vllm_client import VLLMConfig
    print(f"✅ Backend VLLM 클라이언트 로드 성공")
except ImportError as e:
    print(f"⚠️ Backend VLLM 클라이언트 로드 실패: {e}")
    print("💡 기본 VLLM 설정을 사용합니다")
    # 기본 VLLM 설정 클래스 정의
    @dataclass
    class VLLMConfig:
        base_url: str = DYNAMIC_VLLM_URL

try:
    from app.services.vllm_client import vllm_health_check
    print(f"✅ Backend VLLM 헬스체크 함수 로드 성공")
except ImportError as e:
    print(f"⚠️ Backend VLLM 헬스체크 함수 로드 실패: {e}")
    print("💡 기본 헬스체크 함수를 사용합니다")
    # 기본 헬스체크 함수 정의
    async def vllm_health_check():
        return True

# 환경변수에도 설정 (전체 시스템 동기화)
os.environ["VLLM_BASE_URL"] = DYNAMIC_VLLM_URL

# 우리가 만든 모듈들 임포트
from document_loader import load_pdf_and_generate_qa, PDFToQAProcessor
from embed_store import EmbeddingStore, EmbeddingConfig, MilvusConfig
from rag_search import RAGSearcher, SearchConfig, retrieve_relevant_chunks
from chat_generator import (
    ChatGenerator, VLLMGenerationConfig, PromptTemplate,
    TextNormalizer, ModelIdValidator, 
    generate_response, vllm_chat, truncate_history_by_char
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Single Responsibility Principle: 설정 검증 전용 클래스
class ConfigValidator:
    """파이프라인 설정 검증 담당 클래스"""
    
    @staticmethod
    def validate_pipeline_config(config: 'PipelineConfig') -> bool:
        """파이프라인 설정 검증"""
        try:
            # PDF 경로 검증
            if config.pdf_path and not Path(config.pdf_path).exists():
                logger.error(f"PDF 파일을 찾을 수 없습니다: {config.pdf_path}")
                return False
            
            # 출력 디렉토리 생성 가능성 검증
            try:
                Path(config.output_dir).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"출력 디렉토리 생성 실패: {config.output_dir}, {e}")
                return False
            
            # 수치 범위 검증
            if not 10 <= config.min_paragraph_length <= 1000:
                logger.warning(f"min_paragraph_length 값이 비정상적입니다: {config.min_paragraph_length}")
                config.min_paragraph_length = 30
            
            if not 1 <= config.max_qa_pairs <= 10000:
                logger.warning(f"max_qa_pairs 값이 비정상적입니다: {config.max_qa_pairs}")
                config.max_qa_pairs = 100
            
            if not 1 <= config.search_top_k <= 20:
                logger.warning(f"search_top_k 값이 비정상적입니다: {config.search_top_k}")
                config.search_top_k = 3
            
            if not 0.0 <= config.search_threshold <= 1.0:
                logger.warning(f"search_threshold 값이 비정상적입니다: {config.search_threshold}")
                config.search_threshold = 0.7
            
            if not 0.1 <= config.response_temperature <= 2.0:
                logger.warning(f"response_temperature 값이 비정상적입니다: {config.response_temperature}")
                config.response_temperature = 0.8
            
            if not 50 <= config.response_max_tokens <= 4096:
                logger.warning(f"response_max_tokens 값이 비정상적입니다: {config.response_max_tokens}")
                config.response_max_tokens = 512
            
            # VLLM URL 검증
            if config.use_vllm and not config.vllm_base_url.startswith(('http://', 'https://')):
                logger.error(f"유효하지 않은 VLLM URL: {config.vllm_base_url}")
                return False
            
            # 시스템 메시지와 인플루언서 이름 정규화
            config.system_message = TextNormalizer.normalize(config.system_message)
            config.influencer_name = TextNormalizer.normalize(config.influencer_name)
            
            return True
            
        except Exception as e:
            logger.error(f"설정 검증 중 오류: {e}")
            return False


@dataclass
class PipelineConfig:
    """파이프라인 전체 설정 (backend .env 사용)"""
    # 파일 경로
    pdf_path: str = ""
    output_dir: str = "./rag_output"
    
    # 처리 설정
    min_paragraph_length: int = 30
    max_qa_pairs: int = 100
    
    # 검색 설정
    search_top_k: int = 3
    search_threshold: float = 0.7
    
    # 생성 설정
    response_max_tokens: int = 1024
    response_temperature: float = 0.8
    
    # VLLM 설정 (backend .env에서 로드)
    use_vllm: bool = True
    vllm_base_url: str = DYNAMIC_VLLM_URL  # backend .env의 VLLM_BASE_URL 사용
    system_message: str = (
        "당신은 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하는 AI 어시스턴트입니다. "
        "**중요**: 문서에 포함된 모든 내용은 절대 요약하거나 생략하지 말고, 원문 그대로 완전히 포함해야 합니다. "
        "사실, 수치, 날짜, 정책 내용, 세부 사항 등 모든 정보를 정확히 그대로 유지해주세요. "
        "문서 내용의 완전성과 정확성이 최우선이며, 말투와 표현 방식만 캐릭터 스타일로 조정해주세요. "
        "문서 내용을 임의로 변경, 요약, 추가하지 말고, 오직 제공된 정보를 완전히 그대로 사용해 답변해주세요. "
        "\n\n**캐릭터 정체성**: 당신은 {influencer_name} 캐릭터입니다. "
        "자기소개를 할 때나 '너 누구야?', '당신은 누구인가요?', '이름이 뭐야?' 같은 질문을 받으면 "
        "반드시 '나는 {influencer_name}이야!' 또는 '저는 {influencer_name}입니다!'라고 답변해야 합니다. "
        "항상 {influencer_name}의 정체성을 유지하며 그 캐릭터답게 행동하세요."
    )
    influencer_name: str = "AI"
    
    # 디버그 설정
    save_intermediate: bool = True
    verbose: bool = True
    
    def __post_init__(self):
        """초기화 후 검증"""
        if not ConfigValidator.validate_pipeline_config(self):
            logger.warning("⚠️ 설정 검증에서 일부 문제가 발견되었지만 계속 진행합니다.")


# Interface Segregation Principle: 문서 처리 인터페이스
class IDocumentProcessor(ABC):
    """문서 처리 인터페이스"""
    
    @abstractmethod
    def process_document(self, pdf_path: str) -> List[Dict]:
        pass


# Interface Segregation Principle: 벡터 스토어 관리 인터페이스
class IVectorStoreManager(ABC):
    """벡터 스토어 관리 인터페이스"""
    
    @abstractmethod
    def store_qa_data(self, qa_data: List[Dict], source_file: str) -> bool:
        pass
    
    @abstractmethod
    def get_embedding_store(self) -> EmbeddingStore:
        pass


# Interface Segregation Principle: 챗봇 엔진 인터페이스
class IChatbotEngine(ABC):
    """챗봇 엔진 인터페이스"""
    
    @abstractmethod
    def answer_question(self, query: str) -> Dict:
        pass


class DocumentProcessor(IDocumentProcessor):
    """문서 처리 클래스 (수정됨)"""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.pdf_processor = PDFToQAProcessor()
    
    def process_document(self, pdf_path: str) -> List[Dict]:
        """PDF 문서를 QA 쌍으로 변환 (개선된 검증)"""
        # 입력 검증
        if not pdf_path or not pdf_path.strip():
            raise ValueError("PDF 경로가 비어있습니다.")
        
        pdf_path_obj = Path(pdf_path)
        if not pdf_path_obj.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
        
        if not pdf_path_obj.suffix.lower() == '.pdf':
            raise ValueError(f"PDF 파일이 아닙니다: {pdf_path}")
        
        logger.info(f"📄 PDF 문서 처리 시작: {pdf_path}")
        
        try:
            # PDF → QA 생성
            qa_pairs = self.pdf_processor.process(pdf_path)
            
            if not qa_pairs:
                logger.warning("⚠️ PDF에서 QA 쌍을 생성하지 못했습니다.")
                return []
            
            # 개수 제한 적용
            if len(qa_pairs) > self.config.max_qa_pairs:
                qa_pairs = qa_pairs[:self.config.max_qa_pairs]
                logger.info(f"QA 쌍을 {self.config.max_qa_pairs}개로 제한")
            
            # 텍스트 정규화 및 검증 적용
            normalized_qa_pairs = []
            for qa in qa_pairs:
                try:
                    normalized_qa = {
                        "question": TextNormalizer.normalize(qa.question),
                        "answer": TextNormalizer.normalize(qa.answer),
                        "context": TextNormalizer.normalize(qa.context),
                        "source_page": qa.source_page
                    }
                    
                    # 비어있는 질문이나 답변 필터링
                    if (normalized_qa["question"].strip() and 
                        normalized_qa["answer"].strip() and
                        len(normalized_qa["question"]) >= 5 and
                        len(normalized_qa["answer"]) >= 10):
                        normalized_qa_pairs.append(normalized_qa)
                    else:
                        logger.debug(f"빈 QA 쌍 필터링: Q={qa.question[:50]}")
                        
                except Exception as e:
                    logger.warning(f"QA 쌍 정규화 실패: {e}")
                    continue
            
            if not normalized_qa_pairs:
                raise ValueError("유효한 QA 쌍을 생성하지 못했습니다.")
            
            # 중간 결과 저장
            if self.config.save_intermediate:
                self._save_qa_pairs(normalized_qa_pairs, pdf_path)
            
            logger.info(f"✅ 문서 처리 완료: {len(normalized_qa_pairs)}개 QA 쌍 생성")
            return normalized_qa_pairs
            
        except Exception as e:
            logger.error(f"❌ 문서 처리 실패: {e}")
            raise
    
    def _save_qa_pairs(self, qa_pairs, pdf_path: str):
        """QA 쌍을 JSON 파일로 저장"""
        try:
            output_dir = Path(self.config.output_dir)
            output_dir.mkdir(exist_ok=True)
            
            filename = Path(pdf_path).stem
            output_path = output_dir / f"{filename}_qa_pairs.json"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 QA 쌍 저장: {output_path}")
            
        except Exception as e:
            logger.error(f"QA 쌍 저장 실패: {e}")


class VectorStoreManager(IVectorStoreManager):
    """벡터 스토어 관리 클래스 (수정됨)"""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        
        # 출력 디렉토리 먼저 생성
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
        
        # 임베딩 및 벡터 스토어 설정
        embedding_config = EmbeddingConfig(
            device="cuda" if os.getenv("CUDA_AVAILABLE") else "cpu"
        )
        
        milvus_config = MilvusConfig(
            uri=f"{config.output_dir}/rag_vectorstore.db",
            collection_name="document_qa_collection"
        )
        
        try:
            self.embedding_store = EmbeddingStore(embedding_config, milvus_config)
        except Exception as e:
            logger.error(f"임베딩 스토어 초기화 실패: {e}")
            raise
    
    def store_qa_data(self, qa_data: List[Dict], source_file: str) -> bool:
        """QA 데이터를 벡터 스토어에 저장 (개선된 검증)"""
        if not qa_data:
            logger.error("저장할 QA 데이터가 없습니다.")
            return False
        
        if not source_file or not source_file.strip():
            logger.error("소스 파일 경로가 비어있습니다.")
            return False
        
        logger.info(f"🔄 벡터 스토어에 데이터 저장 중... ({len(qa_data)}개 항목)")
        
        try:
            success = self.embedding_store.store_qa_chunks(qa_data, source_file)
            
            if success:
                logger.info(f"✅ 벡터 스토어 저장 완료: {len(qa_data)}개 항목")
            else:
                logger.error("❌ 벡터 스토어 저장 실패")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 벡터 스토어 저장 중 오류: {e}")
            return False
    
    def get_embedding_store(self) -> EmbeddingStore:
        """임베딩 스토어 반환"""
        return self.embedding_store


class ChatbotEngine(IChatbotEngine):
    """챗봇 엔진 클래스 (인스타그램 챗봇 스타일 적용)"""
    
    def __init__(self, 
                 config: PipelineConfig, 
                 embedding_store: EmbeddingStore, 
                 lora_adapter: Optional[str] = None,
                 hf_token: Optional[str] = None,
                 influencer_id: Optional[str] = None,  # 인플루언서 ID 추가
                 db_session: Optional[Session] = None):  # 데이터베이스 세션 추가
        
        self.config = config
        self.embedding_store = embedding_store
        self.lora_adapter = lora_adapter
        self.hf_token = hf_token
        self.influencer_id = influencer_id
        self.db_session = db_session
        
        # 검색 엔진 초기화
        self.searcher = RAGSearcher(embedding_store)
        
        # 채팅 생성기 지연 초기화
        self._generator_initialized = False
        self.chat_generator = None
        
        # 채팅 히스토리 (인스타그램 챗봇 스타일)
        self.chat_history = []
        
        # 인플루언서 정보 로드 (인스타그램 챗봇 스타일)
        self.influencer_info = self._load_influencer_info()
        
        logger.info(f"🤖 RAG 챗봇 엔진 초기화 완료")
        if self.influencer_info:
            logger.info(f"👤 인플루언서: {self.influencer_info.get('name', 'Unknown')}")
    
    def _load_influencer_info(self) -> Optional[Dict]:
        """인플루언서 정보 로드 (인스타그램 챗봇 스타일)"""
        if not self.influencer_id or not self.db_session:
            logger.info("⚠️ 인플루언서 ID 또는 DB 세션이 없어 기본 설정 사용")
            return None
        
        try:
            from app.models.influencer import AIInfluencer
            
            influencer = (
                self.db_session.query(AIInfluencer)
                .filter(AIInfluencer.influencer_id == self.influencer_id)
                .first()
            )
            
            if influencer:
                logger.info(f"✅ 인플루언서 정보 로드 성공: {influencer.influencer_name}")
                return {
                    'name': influencer.influencer_name,
                    'personality': influencer.influencer_personality,
                    'tone': influencer.influencer_tone,
                    'system_prompt': influencer.system_prompt,
                    'model_repo': influencer.influencer_model_repo
                }
            else:
                logger.warning(f"⚠️ 인플루언서 ID {self.influencer_id}에 해당하는 인플루언서를 찾을 수 없습니다")
                return None
                
        except Exception as e:
            logger.error(f"❌ 인플루언서 정보 로드 실패: {e}")
            return None
    
    def _initialize_generator(self):
        """채팅 생성기 지연 초기화 (인스타그램 챗봇 스타일 적용)"""
        if not self._generator_initialized:
            logger.info("🤖 AI 모델 로딩 중... (시간이 걸릴 수 있습니다)")
            
            try:
                # 인플루언서 정보 활용 (인스타그램 챗봇 스타일)
                influencer_name = "AI"
                system_prompt = self.config.system_message
                model_id = self.lora_adapter
                
                if self.influencer_info:
                    # 데이터베이스에서 로드한 인플루언서 정보 사용
                    influencer_name = self.influencer_info.get('name', 'AI')
                    
                    # 저장된 시스템 프롬프트가 있으면 사용
                    if self.influencer_info.get('system_prompt'):
                        system_prompt = str(self.influencer_info['system_prompt'])
                        logger.info(f"✅ 저장된 시스템 프롬프트 사용: {system_prompt[:100]}...")
                    else:
                        # 기본 시스템 프롬프트에 인플루언서 정보 적용
                        personality = self.influencer_info.get('personality', '친근하고 도움이 되는 AI 인플루언서')
                        tone = self.influencer_info.get('tone', '친근하고 자연스러운 말투')
                        
                        system_prompt = f"""당신은 {influencer_name}라는 AI 인플루언서입니다.

성격: {personality}
말투: {tone}

다음 규칙을 따라 응답해주세요:
1. 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하세요
2. 문서에 포함된 모든 내용은 절대 요약하거나 생략하지 말고, 원문 그대로 완전히 포함하세요
3. 사실, 수치, 날짜, 정책 내용, 세부 사항 등 모든 정보를 정확히 그대로 유지하세요
4. {influencer_name}의 개성을 살려서 응답하세요
5. 자기소개를 할 때나 '너 누구야?', '당신은 누구인가요?', '이름이 뭐야?' 같은 질문을 받으면 반드시 '나는 {influencer_name}이야!' 또는 '저는 {influencer_name}입니다!'라고 답변하세요"""
                        logger.info("⚠️ 저장된 시스템 프롬프트가 없어 기본 시스템 메시지 사용")
                    
                    # 인플루언서 전용 모델이 있으면 사용
                    if self.influencer_info.get('model_repo'):
                        model_id = self.influencer_info['model_repo']
                        logger.info(f"🤖 인플루언서 전용 모델 사용: {model_id}")
                
                # VLLM 모드 설정
                vllm_config = VLLMConfig(base_url=self.config.vllm_base_url)
                generation_config = VLLMGenerationConfig(
                    max_new_tokens=self.config.response_max_tokens,
                    temperature=self.config.response_temperature,
                    influencer_name=influencer_name,
                    system_prompt=system_prompt,
                    model_id=model_id,  # 검증된 어댑터 사용
                    vllm_config=vllm_config
                )
                
                prompt_template = PromptTemplate()
                
                # ChatGenerator 초기화
                self.chat_generator = ChatGenerator(
                    generation_config=generation_config,
                    prompt_template=prompt_template,
                    vllm_config=vllm_config
                )
                
                # VLLM 어댑터 로드 (재시도 로직 추가)
                if model_id and self.hf_token:
                    self._load_adapter_with_retry(model_id)
                
                self._generator_initialized = True
                logger.info(f"✅ AI 모델 로딩 완료 - 인플루언서: {influencer_name}")
                
            except Exception as e:
                logger.error(f"❌ AI 모델 초기화 실패: {e}")
                raise
    
    def _load_adapter_with_retry(self, model_id: str):
        """어댑터 로드 (재시도 로직)"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 LoRA 어댑터 로드 시도 {attempt + 1}/{max_retries}: {model_id}")
                
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 새 이벤트 루프에서 실행
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run, 
                            self.chat_generator.load_vllm_adapter(model_id, self.hf_token)
                        )
                        adapter_loaded = future.result(timeout=60)
                else:
                    adapter_loaded = loop.run_until_complete(
                        self.chat_generator.load_vllm_adapter(model_id, self.hf_token)
                    )
                
                if adapter_loaded:
                    logger.info(f"✅ VLLM LoRA 어댑터 로드 성공: {model_id}")
                    break
                else:
                    logger.warning(f"⚠️ VLLM LoRA 어댑터 로드 실패 (시도 {attempt + 1}/{max_retries}): {model_id}")
                    if attempt < max_retries - 1:
                        logger.info(f"🔄 {retry_delay}초 후 재시도...")
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 1.5
                        
            except Exception as e:
                logger.error(f"❌ VLLM 어댑터 로드 중 오류 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"🔄 {retry_delay}초 후 재시도...")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 1.5
                else:
                    logger.warning("⚠️ 모든 어댑터 로드 시도 실패, 기본 모델로 계속 진행")
    
    def answer_question(self, query: str) -> Dict:
        """사용자 질문에 대한 답변 생성 (히스토리 포함)"""
        try:
            # 입력 검증
            if not query or not query.strip():
                return self._create_error_response("질문을 입력해주세요.", query)
            
            # 입력 질의 정규화
            normalized_query = TextNormalizer.normalize(query)
            
            if len(normalized_query) < 2:
                return self._create_error_response("질문이 너무 짧습니다.", query)
            
            # 1. 관련 문맥 검색
            if self.config.verbose:
                logger.info(f"🔍 관련 문맥 검색 중...")
            
            search_results = self.searcher.search(normalized_query, top_k=self.config.search_top_k)
            context = self.searcher.get_context(search_results)
            
            # 컨텍스트도 정규화
            normalized_context = TextNormalizer.normalize(context)
            
            if self.config.verbose:
                logger.info(f"📚 {len(search_results)}개 관련 문서 발견")
            
            # 2. 히스토리 기반 컨텍스트 추가
            if self.chat_history:
                history_context = self._build_history_context()
                if history_context:
                    normalized_context = f"{normalized_context}\n\n이전 대화:\n{history_context}"
                    if self.config.verbose:
                        logger.info(f"📝 히스토리 컨텍스트 추가 ({len(self.chat_history)}개 대화)")
            
            # 3. AI 응답 생성
            if not self._generator_initialized:
                self._initialize_generator()
            
            if self.config.verbose:
                logger.info(f"🤖 AI 응답 생성 중...")
            
            response = self.chat_generator.generate_response(normalized_query, normalized_context)
            
            # 응답도 정규화
            normalized_response = TextNormalizer.normalize(response)
            
            # 4. 히스토리 저장
            self.chat_history.append({
                "query": normalized_query,
                "response": normalized_response,
                "context": normalized_context,
                "sources": [
                    {
                        "source": r.source,
                        "page": r.page,
                        "score": round(r.score, 3)
                    }
                    for r in search_results
                ],
                "model_info": {
                    "mode": "vllm",
                    "adapter": self.lora_adapter,
                    "temperature": self.config.response_temperature
                },
                "timestamp": datetime.now().isoformat()
            })
            
            # 히스토리 자르기 (1000자 단위)
            self.chat_history = truncate_history_by_char(self.chat_history)
            
            return {
                "query": normalized_query,
                "response": normalized_response,
                "context": normalized_context,
                "sources": [
                    {
                        "source": r.source,
                        "page": r.page,
                        "score": round(r.score, 3)
                    }
                    for r in search_results
                ],
                "model_info": {
                    "mode": "vllm",
                    "adapter": self.lora_adapter,
                    "temperature": self.config.response_temperature
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 질문 처리 실패: {e}")
            return self._create_error_response(f"질문 처리 중 오류가 발생했습니다: {str(e)}", query)
    
    def _create_error_response(self, error_message: str, original_query: str) -> Dict:
        """에러 응답 생성"""
        return {
            "query": TextNormalizer.normalize(original_query),
            "response": error_message,
            "context": "",
            "sources": [],
            "model_info": {
                "mode": "error",
                "error": error_message
            },
            "timestamp": datetime.now().isoformat()
        }

    def _build_history_context(self) -> str:
        """히스토리에서 컨텍스트 문자열 생성"""
        if not self.chat_history:
            return ""
        
        # 최근 대화들을 문자열로 변환
        history_parts = []
        for i, chat in enumerate(self.chat_history[-3:], 1):  # 최근 3개만
            history_parts.append(f"Q{i}: {chat['query']}")
            history_parts.append(f"A{i}: {chat['response']}")
        
        return "\n".join(history_parts)


# Interface Segregation Principle: 서버 상태 확인 인터페이스
class IServerStatusChecker(ABC):
    """서버 상태 확인 인터페이스"""
    
    @abstractmethod
    async def check_vllm_server(self) -> bool:
        pass


class ServerStatusChecker(IServerStatusChecker):
    """서버 상태 확인 클래스"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    async def check_vllm_server(self) -> bool:
        """VLLM 서버 상태 확인"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                is_healthy = await vllm_health_check()
                
                if is_healthy:
                    logger.info(f"✅ VLLM 서버 연결 확인: {self.base_url}")
                    return True
                else:
                    logger.warning(f"⚠️ VLLM 서버 응답 없음 (시도 {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        logger.info(f"🔄 {retry_delay}초 후 재시도...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 1.5
                        
            except Exception as e:
                logger.error(f"❌ VLLM 서버 확인 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"🔄 {retry_delay}초 후 재시도...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5
        
        logger.error(f"❌ VLLM 서버 연결 실패: {self.base_url}")
        return False


class RAGChatbotPipeline:
    """RAG 챗봇 파이프라인 (인스타그램 챗봇 스타일 적용)"""
    
    def __init__(self, 
                 config: PipelineConfig, 
                 lora_adapter: Optional[str] = None,
                 hf_token: Optional[str] = None,
                 influencer_id: Optional[str] = None,  # 인플루언서 ID 추가
                 db_session: Optional[Session] = None,  # 데이터베이스 세션 추가
                 document_processor: Optional[IDocumentProcessor] = None,
                 vector_store_manager: Optional[IVectorStoreManager] = None,
                 server_status_checker: Optional[IServerStatusChecker] = None):
        
        # 설정 검증
        if not ConfigValidator.validate_pipeline_config(config):
            logger.warning("⚠️ 설정 검증에서 일부 문제가 발견되었지만 계속 진행합니다.")
        
        self.config = config
        self.lora_adapter = lora_adapter
        self.hf_token = hf_token
        self.influencer_id = influencer_id
        self.db_session = db_session
        
        # 의존성 주입 (인스타그램 챗봇 스타일)
        self.document_processor = document_processor or DocumentProcessor(config)
        self.vector_store_manager = vector_store_manager or VectorStoreManager(config)
        self.server_status_checker = server_status_checker or ServerStatusChecker(config.vllm_base_url)
        
        self.chatbot_engine = None
        
        logger.info(f"🎯 RAG 챗봇 파이프라인 초기화 완료")
        if self.influencer_id:
            logger.info(f"👤 인플루언서 ID: {self.influencer_id}")
    
    async def check_vllm_server(self) -> bool:
        """VLLM 서버 상태 확인 (위임)"""
        return await self.server_status_checker.check_vllm_server()
    
    def ingest_document(self, pdf_path: str) -> bool:
        """문서 인제스트 (PDF → QA → 벡터 저장)"""
        try:
            logger.info(f"📋 문서 인제스트 시작: {pdf_path}")
            
            # 입력 검증
            if not pdf_path or not pdf_path.strip():
                logger.error("❌ PDF 경로가 비어있습니다.")
                return False
            
            # VLLM 서버 상태 확인
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, self.check_vllm_server())
                        server_healthy = future.result(timeout=30)
                else:
                    server_healthy = loop.run_until_complete(self.check_vllm_server())
                
                if not server_healthy:
                    logger.warning("⚠️ VLLM 서버가 응답하지 않지만 문서 인제스트는 계속 진행합니다.")
                    
            except Exception as e:
                logger.warning(f"⚠️ VLLM 서버 확인 중 오류: {e}, 계속 진행합니다.")
            
            # 1. PDF → QA 생성
            qa_data = self.document_processor.process_document(pdf_path)
            
            if not qa_data:
                logger.error("❌ QA 데이터 생성 실패")
                return False
            
            # 2. 벡터 스토어에 저장
            success = self.vector_store_manager.store_qa_data(qa_data, pdf_path)
            
            if success:
                # 3. 챗봇 엔진 초기화 (LoRA 어댑터 포함)
                embedding_store = self.vector_store_manager.get_embedding_store()
                self.chatbot_engine = ChatbotEngine(
                    self.config, 
                    embedding_store, 
                    self.lora_adapter,
                    self.hf_token,
                    self.influencer_id,
                    self.db_session
                )
                
                logger.info(f"🎉 문서 인제스트 완료!")
                logger.info(f"🔧 모델 모드: VLLM 서버")
                if self.lora_adapter:
                    logger.info(f"🎯 LoRA 어댑터: {self.lora_adapter}")
                
                return True
            else:
                logger.error("❌ 문서 인제스트 실패")
                return False
                
        except Exception as e:
            logger.error(f"❌ 문서 인제스트 중 오류: {e}")
            return False
    
    def chat(self, query: str) -> Dict:
        """채팅 인터페이스"""
        if not self.chatbot_engine:
            return {
                "query": TextNormalizer.normalize(query),
                "response": "문서를 먼저 인제스트해주세요.",
                "context": "",
                "sources": [],
                "timestamp": datetime.now().isoformat()
            }
        
        return self.chatbot_engine.answer_question(query)
    
    def interactive_chat(self):
        """대화형 채팅 모드"""
        print("\n🤖 RAG 챗봇이 준비되었습니다!")
        print(f"🔧 모델 모드: VLLM 서버")
        if self.lora_adapter:
            print(f"🎯 LoRA 어댑터: {self.lora_adapter}")
        print("💡 도움말: 'help', 종료: 'exit'/'quit'/'종료'")
        print("-" * 50)
        
        while True:
            try:
                user_input = input("\n💬 질문을 입력하세요: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ["exit", "quit", "종료"]:
                    print("👋 채팅을 종료합니다. 안녕히 가세요!")
                    break
                
                if user_input.lower() == "help":
                    self._show_help()
                    continue
                
                if user_input.lower() == "history":
                    # chatbot_engine의 히스토리 사용
                    if self.chatbot_engine:
                        self._show_history(self.chatbot_engine.chat_history)
                    else:
                        print("\n📝 아직 채팅 기록이 없습니다.")
                    continue
                
                if user_input.lower() == "info":
                    self._show_model_info()
                    continue
                
                # 질문 처리
                result = self.chat(user_input)
                
                # 응답 출력
                print(f"\n🤖 답변: {result['response']}")
                
                if self.config.verbose and result['sources']:
                    print(f"\n📚 참고 문서:")
                    for i, source in enumerate(result['sources'][:3]):
                        print(f"  {i+1}. {source['source']} (페이지 {source['page']}, 신뢰도: {source['score']})")
                
            except KeyboardInterrupt:
                print("\n\n👋 채팅을 종료합니다.")
                break
            except Exception as e:
                print(f"\n❌ 오류 발생: {e}")
    
    def _show_help(self):
        """도움말 표시"""
        print("\n📖 사용 가능한 명령어:")
        print("  help     - 이 도움말 표시")
        print("  history  - 채팅 기록 표시")
        print("  info     - 모델 정보 표시")
        print("  exit     - 채팅 종료")
        print("  그 외    - 일반 질문")
    
    def _show_history(self, history: List[Dict]):
        """채팅 기록 표시 (1000자 단위로 자른 히스토리)"""
        if not history:
            print("\n📝 아직 채팅 기록이 없습니다.")
            return
        
        # 1000자 단위로 자른 히스토리 사용
        truncated_history = truncate_history_by_char(history)
        
        print(f"\n📝 최근 채팅 기록 ({len(truncated_history)}개, 최대 1000자):")
        for i, chat in enumerate(truncated_history, 1):
            print(f"  {i}. Q: {chat['query'][:50]}...")
            print(f"     A: {chat['response'][:50]}...")
        
        # 전체 문자 수 표시
        total_chars = sum(len(chat['query']) + len(chat['response']) for chat in truncated_history)
        print(f"📊 총 문자 수: {total_chars}자")
    
    def _show_model_info(self):
        """모델 정보 표시"""
        if self.chatbot_engine and self.chatbot_engine.chat_generator:
            try:
                info = self.chatbot_engine.chat_generator.get_model_info()
                print(f"\n🔧 모델 정보:")
                for key, value in info.items():
                    print(f"  {key}: {value}")
            except Exception as e:
                print(f"\n⚠️ 모델 정보 가져오기 실패: {e}")
        else:
            print("\n⚠️ 모델이 아직 초기화되지 않았습니다.")


# 편의 함수들 (기존 코드와 호환성)
def ingest_document(pdf_path: str, 
                   config: Optional[PipelineConfig] = None, 
                   lora_adapter: Optional[str] = None,
                   hf_token: Optional[str] = None,
                   use_vllm: bool = True) -> bool:
    """문서 인제스트 편의 함수"""
    pipeline_config = config or PipelineConfig(pdf_path=pdf_path, use_vllm=use_vllm)
    pipeline = RAGChatbotPipeline(pipeline_config, lora_adapter, hf_token)
    return pipeline.ingest_document(pdf_path)


def answer_question(query: str, config: Optional[PipelineConfig] = None) -> str:
    """질문 답변 편의 함수 (기존 호환성)"""
    try:
        return retrieve_relevant_chunks(query)
    except Exception as e:
        logger.error(f"답변 생성 실패: {e}")
        return "죄송합니다. 답변 생성 중 오류가 발생했습니다."


def create_vllm_pipeline(pdf_path: str, 
                        lora_adapter: str, 
                        hf_token: str,
                        vllm_base_url: str = DYNAMIC_VLLM_URL,
                        system_message: str = (
                            "당신은 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하는 AI 어시스턴트입니다. "
                            "**중요**: 문서에 포함된 모든 내용은 절대 요약하거나 생략하지 말고, 원문 그대로 완전히 포함해야 합니다. "
                            "사실, 수치, 날짜, 정책 내용, 세부 사항 등 모든 정보를 정확히 그대로 유지해주세요. "
                            "문서 내용의 완전성과 정확성이 최우선이며, 말투와 표현 방식만 캐릭터 스타일로 조정해주세요. "
                            "문서 내용을 임의로 변경, 요약, 추가하지 말고, 오직 제공된 정보를 완전히 그대로 사용해 답변해주세요. "
                            "\n\n**캐릭터 정체성**: 당신은 {influencer_name} 캐릭터입니다. "
                            "자기소개를 할 때나 '너 누구야?', '당신은 누구인가요?', '이름이 뭐야?' 같은 질문을 받으면 "
                            "반드시 '나는 {influencer_name}이야!' 또는 '저는 {influencer_name}입니다!'라고 답변해야 합니다. "
                            "항상 {influencer_name}의 정체성을 유지하며 그 캐릭터답게 행동하세요."
                        ),
                        influencer_name: str = "AI",
                        temperature: float = 0.8,
                        influencer_id: Optional[str] = None,  # 인플루언서 ID 추가
                        db_session: Optional[Session] = None) -> RAGChatbotPipeline:  # 데이터베이스 세션 추가
    """VLLM 기반 RAG 파이프라인 생성 편의 함수 (인스타그램 챗봇 스타일)"""
    config = PipelineConfig(
        pdf_path=pdf_path,
        use_vllm=True,
        vllm_base_url=vllm_base_url,
        system_message=system_message,
        influencer_name=influencer_name,
        response_temperature=temperature
    )
    
    return RAGChatbotPipeline(
        config, 
        lora_adapter, 
        hf_token,
        influencer_id,
        db_session
    )


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="RAG 챗봇 파이프라인 (VLLM 지원, SOLID 원칙 적용)")
    parser.add_argument("pdf_path", help="PDF 파일 경로")
    parser.add_argument("--output-dir", default="./rag_output", help="출력 디렉토리")
    parser.add_argument("--verbose", action="store_true", help="상세 출력")
    parser.add_argument("--max-tokens", type=int, default=1024, help="최대 생성 토큰 수")
    parser.add_argument("--temperature", type=float, default=0.8, help="생성 온도 (높을수록 창의적)")
    parser.add_argument("--search-k", type=int, default=3, help="검색할 문서 수")
    parser.add_argument("--lora-adapter", type=str, default="khj0816/EXAONE-Ian", help="LoRA 어댑터 이름")
    parser.add_argument("--hf-token", type=str, help="HuggingFace 토큰")
    parser.add_argument("--system-message", default="당신은 도움이 되는 AI 어시스턴트입니다.", help="시스템 메시지")
    parser.add_argument("--influencer-name", default="AI", help="AI 캐릭터 이름")
    
    args = parser.parse_args()
    
    # LoRA 어댑터 설정 및 검증
    lora_adapter = None
    if args.lora_adapter and args.lora_adapter.lower() != "none":
        if ModelIdValidator.is_valid_adapter_format(args.lora_adapter):
            lora_adapter = ModelIdValidator.validate_model_id(args.lora_adapter)
            if not lora_adapter:
                logger.error(f"❌ 유효하지 않은 LoRA 어댑터: {args.lora_adapter}")
                sys.exit(1)
        else:
            logger.error(f"❌ 잘못된 LoRA 어댑터 형식: {args.lora_adapter}")
            sys.exit(1)
    
    hf_token = os.getenv("HF_TOKEN")
    
    if not hf_token and lora_adapter:
        logger.warning("⚠️ HuggingFace 토큰이 없습니다. LoRA 어댑터 로드에 실패할 수 있습니다.")
    
    # 설정 생성 및 검증
    try:
        config = PipelineConfig(
            pdf_path=args.pdf_path,
            output_dir=args.output_dir,
            verbose=args.verbose,
            response_max_tokens=args.max_tokens,
            response_temperature=args.temperature,
            search_top_k=args.search_k,
            use_vllm=True,
            vllm_base_url=DYNAMIC_VLLM_URL,  # backend .env에서 로드된 URL 사용
            influencer_name=TextNormalizer.normalize(args.influencer_name),
            system_message=TextNormalizer.normalize(args.system_message)
        )
    except Exception as e:
        logger.error(f"❌ 설정 생성 실패: {e}")
        sys.exit(1)
    
    # 파이프라인 생성 및 실행
    try:
        pipeline = RAGChatbotPipeline(config, lora_adapter, hf_token)
        
        # 문서 인제스트
        if not pipeline.ingest_document(args.pdf_path):
            print("❌ 문서 인제스트 실패")
            sys.exit(1)
        
        # 대화형 채팅 시작
        pipeline.interactive_chat()
        
    except Exception as e:
        logger.error(f"❌ 파이프라인 실행 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("🚀 RAG 챗봇 파이프라인 (VLLM 지원, SOLID 원칙 적용)")
        print("\n사용법:")
        print("  python chatbot_pipeline.py <PDF파일경로> [옵션]")
        print("\n주요 옵션:")
        print("  --lora-adapter STR    LoRA 어댑터 이름 (기본: khj0816/EXAONE-Ian)")
        print("  --hf-token STR        HuggingFace 토큰")
        print("  --influencer-name STR AI 캐릭터 이름 (기본: AI)")
        print("  --temperature FLOAT   생성 온도 (기본: 0.8)")
        print("  --verbose             상세 출력")
        print("\n예시:")
        print("  # VLLM 서버 사용")
        print("  python chatbot_pipeline.py document.pdf --hf-token your_token")
        print("  python chatbot_pipeline.py document.pdf --lora-adapter user/model --hf-token your_token")
        print("  ")
        print("  # 캐릭터 설정")
        print("  python chatbot_pipeline.py document.pdf --influencer-name '한세나' --system-message '당신은 친근한 AI 어시스턴트 한세나입니다.'")
        print("\n💡 VLLM 서버를 먼저 시작해야 합니다:")
        print("  python -m vllm.entrypoints.openai.api_server --model LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct --enable-lora")
        print("\n📋 Backend .env 파일에 VLLM_BASE_URL을 설정하세요:")
        print("  echo 'VLLM_BASE_URL=https://your-vllm-base-url' >> backend/.env")
        sys.exit(1)
    
    main()