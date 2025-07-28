"""
RAG 문서 처리 서비스
auto_rag/document_loader.py를 backend/services로 이동
"""

import os
import PyPDF2
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class DocumentConfig:
    """문서 처리 설정"""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_qa_pairs: int = 10


class PDFToQAProcessor:
    """PDF를 QA 쌍으로 변환하는 프로세서"""
    
    def __init__(self, config: DocumentConfig = None):
        self.config = config or DocumentConfig()
    
    def process_pdf(self, pdf_path: str) -> List[Dict]:
        """PDF 파일을 QA 쌍으로 처리"""
        try:
            # PDF 텍스트 추출
            text = self._extract_text_from_pdf(pdf_path)
            
            # 텍스트를 청크로 분할
            chunks = self._split_text_into_chunks(text)
            
            # 각 청크를 QA 쌍으로 변환
            qa_pairs = []
            for i, chunk in enumerate(chunks):
                qa_pair = self._convert_chunk_to_qa(chunk, i)
                if qa_pair:
                    qa_pairs.append(qa_pair)
                
                # 최대 QA 쌍 수 제한
                if len(qa_pairs) >= self.config.max_qa_pairs:
                    break
            
            logger.info(f"✅ PDF 처리 완료: {len(qa_pairs)}개 QA 쌍 생성")
            return qa_pairs
            
        except Exception as e:
            logger.error(f"❌ PDF 처리 실패: {str(e)}")
            return []
    
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """PDF에서 텍스트 추출"""
        try:
            text = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- 페이지 {page_num + 1} ---\n"
                        text += page_text
                        text += "\n"
            
            return text.strip()
            
        except Exception as e:
            raise RuntimeError(f"PDF 텍스트 추출 실패: {str(e)}")
    
    def _split_text_into_chunks(self, text: str) -> List[str]:
        """텍스트를 청크로 분할"""
        if not text:
            return []
        
        chunks = []
        start = 0
        
        while start < len(text):
            # 청크 크기만큼 텍스트 추출
            end = start + self.config.chunk_size
            
            if end >= len(text):
                chunk = text[start:]
            else:
                # 문장 경계에서 자르기
                chunk = text[start:end]
                last_period = chunk.rfind('.')
                last_question = chunk.rfind('?')
                last_exclamation = chunk.rfind('!')
                
                # 가장 마지막 문장 부호 찾기
                last_sentence_end = max(last_period, last_question, last_exclamation)
                
                if last_sentence_end > start + self.config.chunk_size // 2:
                    chunk = text[start:start + last_sentence_end + 1]
                    end = start + last_sentence_end + 1
            
            if chunk.strip():
                chunks.append(chunk.strip())
            
            # 다음 청크 시작점 (오버랩 고려)
            start = end - self.config.chunk_overlap
            if start >= len(text):
                break
        
        return chunks
    
    def _convert_chunk_to_qa(self, chunk: str, chunk_index: int) -> Optional[Dict]:
        """청크를 QA 쌍으로 변환"""
        try:
            # 간단한 QA 생성 (실제로는 더 정교한 로직 필요)
            lines = chunk.split('\n')
            if len(lines) < 2:
                return None
            
            # 첫 번째 줄을 질문으로, 나머지를 답변으로
            question = lines[0][:100] + "..." if len(lines[0]) > 100 else lines[0]
            answer = '\n'.join(lines[1:])[:500] + "..." if len('\n'.join(lines[1:])) > 500 else '\n'.join(lines[1:])
            
            return {
                'question': f"청크 {chunk_index + 1}: {question}",
                'answer': answer,
                'page': chunk_index + 1,
                'source': 'pdf_document'
            }
            
        except Exception as e:
            logger.warning(f"청크 {chunk_index} QA 변환 실패: {str(e)}")
            return None


def load_pdf_and_generate_qa(pdf_path: str, config: DocumentConfig = None) -> List[Dict]:
    """PDF 파일을 로드하고 QA 쌍을 생성하는 함수"""
    processor = PDFToQAProcessor(config)
    return processor.process_pdf(pdf_path) 