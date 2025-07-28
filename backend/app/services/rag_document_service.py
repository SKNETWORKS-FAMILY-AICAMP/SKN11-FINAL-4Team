"""
RAG 문서 처리 서비스
PDF 문서를 처리하고 QA 쌍을 생성하는 서비스
"""

import os
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
import re
import asyncio

# PDF 처리 라이브러리
try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

# 텍스트 처리 라이브러리
try:
    import nltk
    from nltk.tokenize import sent_tokenize, word_tokenize
    from nltk.corpus import stopwords

    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """문서 처리기"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.min_paragraph_length = self.config.get("min_paragraph_length", 30)
        self.max_qa_pairs = self.config.get("max_qa_pairs", 100)
        self.chunk_size = self.config.get("chunk_size", 500)  # 더 세분화된 청크
        self.chunk_overlap = self.config.get("chunk_overlap", 100)  # 오버랩도 줄임

        # NLTK 초기화 (가능한 경우)
        if NLTK_AVAILABLE:
            try:
                nltk.download("punkt", quiet=True)
                nltk.download("stopwords", quiet=True)
            except Exception as e:
                logger.warning(f"NLTK 초기화 실패: {e}")

    async def process_pdf(self, pdf_path: str) -> List[Dict]:
        """PDF 문서 처리"""
        if not PdfReader:
            raise ImportError(
                "PyPDF2가 설치되지 않았습니다. pip install PyPDF2를 실행하세요."
            )

        try:
            logger.info(f"📄 PDF 처리 시작: {pdf_path}")

            # PDF 읽기
            with open(pdf_path, "rb") as file:
                reader = PdfReader(file)
                text_content = ""

                for page_num, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    text_content += f"\n--- 페이지 {page_num + 1} ---\n{page_text}\n"

            # 텍스트 전처리
            cleaned_text = self._preprocess_text(text_content)

            # 텍스트 청킹
            chunks = self._create_chunks(cleaned_text)

            # QA 쌍 생성
            qa_pairs = await self._generate_qa_pairs(chunks, pdf_path)

            logger.info(f"✅ PDF 처리 완료: {len(qa_pairs)}개 QA 쌍 생성")
            return qa_pairs

        except Exception as e:
            logger.error(f"❌ PDF 처리 실패: {e}")
            raise

    def _preprocess_text(self, text: str) -> str:
        """텍스트 전처리"""
        # 불필요한 공백 제거
        text = re.sub(r"\s+", " ", text)

        # 특수 문자 정리
        text = re.sub(r"[^\w\s\.\,\!\?\;\:\-\(\)\[\]\{\}]", "", text)

        # 문단 구분 정리
        text = re.sub(r"\n\s*\n", "\n\n", text)

        return text.strip()

    def _create_chunks(self, text: str) -> List[str]:
        """텍스트를 청크로 분할"""
        if NLTK_AVAILABLE:
            return self._create_chunks_with_nltk(text)
        else:
            return self._create_chunks_simple(text)

    def _create_chunks_with_nltk(self, text: str) -> List[str]:
        """NLTK를 사용한 고급 청킹"""
        # 문장 단위로 분할
        sentences = sent_tokenize(text)

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:  # 너무 짧은 문장 제외
                continue

            # 청크 크기 제한 확인
            if len(current_chunk + sentence) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += " " + sentence

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _create_chunks_simple(self, text: str) -> List[str]:
        """간단한 청킹"""
        # 문단 단위로 분할
        paragraphs = re.split(r"\n\s*\n", text)

        chunks = []
        current_chunk = ""

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if len(paragraph) < self.min_paragraph_length:
                continue

            if len(current_chunk + paragraph) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                current_chunk += "\n" + paragraph

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    async def _generate_qa_pairs(
        self, chunks: List[str], source_file: str
    ) -> List[Dict]:
        """청크에서 QA 쌍 생성"""
        qa_pairs = []

        for i, chunk in enumerate(chunks[: self.max_qa_pairs]):
            # 간단한 QA 생성
            question = self._generate_question(chunk, i)
            answer = chunk

            qa_pairs.append(
                {
                    "question": question,
                    "answer": answer,
                    "chunk_id": i,
                    "source": source_file,
                    "page": i // 5 + 1,  # 대략적인 페이지 번호
                    "metadata": {
                        "chunk_type": "document",
                        "length": len(chunk),
                        "word_count": len(chunk.split()),
                    },
                }
            )

        return qa_pairs

    def _generate_question(self, chunk: str, chunk_id: int) -> str:
        """청크에서 질문 생성"""
        # 간단한 질문 생성 (실제로는 더 정교한 방법 사용 가능)
        if chunk_id == 0:
            return "이 문서의 주요 내용은 무엇인가요?"
        else:
            return f"이 문서의 {chunk_id + 1}번째 섹션에 대해 설명해주세요."


class AdvancedDocumentProcessor(DocumentProcessor):
    """고급 문서 처리기"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.use_ai_generation = self.config.get("use_ai_generation", False)
        self.qa_generation_prompt = self.config.get("qa_generation_prompt", "")

    async def _generate_qa_pairs(
        self, chunks: List[str], source_file: str
    ) -> List[Dict]:
        """AI를 사용한 고급 QA 쌍 생성"""
        if self.use_ai_generation:
            return await self._generate_qa_with_ai(chunks, source_file)
        else:
            return await super()._generate_qa_pairs(chunks, source_file)

    async def _generate_qa_with_ai(
        self, chunks: List[str], source_file: str
    ) -> List[Dict]:
        """AI를 사용한 QA 쌍 생성"""
        # TODO: VLLM 서버를 사용한 QA 생성 구현
        # 현재는 기본 구현 사용
        return await super()._generate_qa_pairs(chunks, source_file)


class DocumentAnalyzer:
    """문서 분석기"""

    def __init__(self):
        pass

    def analyze_document(self, text: str) -> Dict[str, Any]:
        """문서 분석"""
        analysis = {
            "total_length": len(text),
            "word_count": len(text.split()),
            "sentence_count": len(re.split(r"[.!?]+", text)),
            "paragraph_count": len(re.split(r"\n\s*\n", text)),
            "avg_sentence_length": 0,
            "avg_word_length": 0,
            "common_words": [],
            "topics": [],
        }

        # 평균 계산
        words = text.split()
        if words:
            analysis["avg_word_length"] = sum(len(word) for word in words) / len(words)

        sentences = re.split(r"[.!?]+", text)
        if sentences:
            analysis["avg_sentence_length"] = sum(
                len(s.split()) for s in sentences
            ) / len(sentences)

        # 빈도 분석 (NLTK 사용 가능한 경우)
        if NLTK_AVAILABLE:
            analysis["common_words"] = self._get_common_words(text)

        return analysis

    def _get_common_words(self, text: str, top_n: int = 10) -> List[str]:
        """자주 사용되는 단어 추출"""
        try:
            # 불용어 제거
            stop_words = set(stopwords.words("english"))
            words = word_tokenize(text.lower())
            words = [
                word for word in words if word.isalnum() and word not in stop_words
            ]

            # 빈도 계산
            from collections import Counter

            word_freq = Counter(words)

            return [word for word, freq in word_freq.most_common(top_n)]
        except Exception as e:
            logger.warning(f"단어 빈도 분석 실패: {e}")
            return []


# 전역 인스턴스
_document_processor = None
_advanced_processor = None
_document_analyzer = None


def get_document_processor(config: Dict[str, Any] = None) -> DocumentProcessor:
    """문서 처리기 인스턴스 반환"""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor(config)
    return _document_processor


def get_advanced_processor(config: Dict[str, Any] = None) -> AdvancedDocumentProcessor:
    """고급 문서 처리기 인스턴스 반환"""
    global _advanced_processor
    if _advanced_processor is None:
        _advanced_processor = AdvancedDocumentProcessor(config)
    return _advanced_processor


def get_document_analyzer() -> DocumentAnalyzer:
    """문서 분석기 인스턴스 반환"""
    global _document_analyzer
    if _document_analyzer is None:
        _document_analyzer = DocumentAnalyzer()
    return _document_analyzer
