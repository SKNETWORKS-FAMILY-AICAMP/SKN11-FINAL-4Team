# RAG 브랜치 변경사항 상세 분석

## 📁 **새로 추가된 디렉토리 및 파일들**

### 🆕 **backend/auto_rag/** - 완전히 새로운 RAG 시스템

#### 📄 **config.py** (14KB, 417줄)
```python
# RAG 시스템의 모든 설정을 관리하는 중앙 설정 시스템
class RAGSystemConfig:
    - ModelMode: LOCAL/VLLM/AUTO 모드 지원
    - DatabaseConfig: Milvus + SQLite 설정
    - VLLMConfig: VLLM 서버 연결 설정
    - LocalModelConfig: 로컬 모델 설정
    - RAGConfig: 검색 및 청킹 설정
    - ServerConfig: API 서버 설정
    - SecurityConfig: 보안 설정
```

**주요 기능:**
- 환경 변수 자동 로드
- 설정 파일 (YAML/JSON) 지원
- 모델 모드 자동 감지
- 디렉토리 자동 생성

#### 📄 **chat_generator.py** (35KB, 798줄)
```python
# VLLM과 로컬 모델을 모두 지원하는 고급 채팅 생성기
class ChatGenerator:
    - VLLMGenerator: VLLM 서버 기반 생성
    - LocalGenerator: 로컬 모델 기반 생성
    - PromptTemplate: RAG 전용 프롬프트 템플릿
    - TextNormalizer: 텍스트 정규화
    - ModelIdValidator: 모델 ID 검증
```

**주요 기능:**
- VLLM/로컬 모델 자동 전환
- RAG 컨텍스트 기반 응답 생성
- 캐릭터 정체성 유지
- 에러 처리 및 폴백

#### 📄 **rag_search.py** (12KB, 357줄)
```python
# 고급 검색 및 재랭킹 시스템
class RAGSearcher:
    - SearchStrategy: SEMANTIC/KEYWORD/HYBRID
    - SearchFilter: 점수/출처/중복 필터
    - Reranker: 키워드 기반 재랭킹
    - SearchResult: 검색 결과 데이터 구조
```

**주요 기능:**
- 다중 검색 전략 지원
- 자동 중복 제거
- 점수 기반 필터링
- 컨텍스트 생성

#### 📄 **embed_store.py** (5KB, 120줄)
```python
# VLLM 서버로 리다이렉트하는 임베딩 스토어
class EmbedStore:
    - add_document(): 문서 추가
    - search(): 문서 검색
    - list_documents(): 문서 목록
    - remove_documents(): 문서 삭제
```

**주요 기능:**
- VLLM 서버의 RAG 기능 활용
- 비동기 HTTP 클라이언트
- 에러 처리 및 로깅

#### 📄 **document_loader.py** (9KB, 272줄)
```python
# 문서 처리 및 청킹 시스템
class DocumentLoader:
    - PDF 처리
    - 텍스트 청킹
    - 메타데이터 추출
    - 벡터화 준비
```

#### 📄 **chatbot_pipeline.py** (42KB, 978줄)
```python
# 전체 RAG 파이프라인 관리
class ChatbotPipeline:
    - 문서 업로드부터 응답 생성까지 전체 과정
    - QA 쌍 생성
    - 파인튜닝 데이터 준비
    - 성능 모니터링
```

#### 📄 **rag_chatbot.py** (6KB, 201줄)
```python
# RAG 전용 챗봇 구현
class RAGChatbot:
    - 문서 기반 대화
    - 컨텍스트 관리
    - 응답 품질 평가
```

### 🆕 **vllm/app/routers/rag.py** - VLLM 서버 RAG 통합

#### 📄 **rag.py** (8.6KB, 269줄)
```python
# VLLM 서버에 통합된 RAG 기능
@router.post("/upload_document")
@router.post("/search")
@router.post("/chat")
@router.get("/documents/{group_id}")
@router.delete("/documents/{group_id}")
```

**주요 기능:**
- Milvus 벡터 데이터베이스 연동
- BGE-M3 임베딩 모델 사용
- 문서 업로드 및 검색
- RAG 기반 챗봇 응답

### 🆕 **backend/app/api/v1/endpoints/rag.py** - 백엔드 RAG 프록시

#### 📄 **rag.py** (4.8KB, 148줄)
```python
# 백엔드에서 VLLM RAG 기능을 프록시
@router.post("/upload_file")
@router.post("/search")
@router.post("/chat")
@router.get("/documents/{group_id}")
@router.delete("/documents/{group_id}")
```

**주요 기능:**
- VLLM 서버로 요청 전달
- 파일 업로드 처리
- 검색 결과 반환
- 에러 처리

### 🔄 **기존 파일 확장**

#### 📄 **backend/app/api/v1/endpoints/mcp.py** - MCP+RAG 통합

**새로 추가된 엔드포인트:**
```python
@router.post("/process-with-rag")  # RAG → MCP 순서 처리
@router.post("/create-rag-pipeline")  # RAG 파이프라인 생성
@router.post("/upload-document")  # 문서 업로드
```

**주요 변경사항:**
- RAG와 MCP를 통합한 처리 로직
- 인플루언서별 RAG 파이프라인 생성
- 문서 업로드 및 관리 기능

#### 📄 **frontend/components/rag-pipeline-setup.tsx** - RAG UI

**새로 추가된 컴포넌트:**
```typescript
interface RAGPipelineSetupProps {
    influencerId: string
    onSuccess?: () => void
}

// 주요 기능:
- PDF 파일 업로드
- 업로드된 문서 목록 표시
- 문서 삭제 기능
- RAG 파이프라인 생성
```

#### 📄 **frontend/lib/services/mcp.service.ts** - RAG API 클라이언트

**새로 추가된 인터페이스:**
```typescript
interface RAGMCPChatResponse {
    response: string
    source: 'rag' | 'mcp' | 'llm' | 'error'
    rag_context: string
    mcp_tools_used: string[]
    confidence: number
}

// 새로운 메서드:
- processMessageWithRAG()
- createRAGPipeline()
- getUploadedDocuments()
- removeUploadedDocument()
```

#### 📄 **frontend/app/chat/[id]/page.tsx** - 챗봇 페이지 확장

**새로 추가된 기능:**
```typescript
// RAG 설정 UI 통합
const [showRAGSetup, setShowRAGSetup] = useState(false)

// RAG 파이프라인 설정 컴포넌트
<RAGPipelineSetup 
    influencerId={model.id} 
    onSuccess={() => {
        // RAG 설정 완료 후 처리
    }}
/>
```

## 🔧 **설정 파일들**

#### 📄 **backend/auto_rag/requirements_rag.txt**
```
# RAG 시스템 전용 의존성
pymilvus==2.3.4
sentence-transformers==2.2.2
chromadb==0.4.22
langchain==0.1.0
langchain-community==0.0.10
```

#### 📄 **backend/auto_rag/.gitignore**
```
# RAG 데이터 및 로그 파일 제외
rag_data/
logs/
temp/
*.db
```

## 📊 **데이터 구조**

#### 📄 **backend/auto_rag/rag_output/**
```
rag_output/
├── documents/          # 업로드된 문서
├── embeddings/         # 벡터 임베딩
├── metadata/          # 메타데이터
└── qa_pairs/          # 생성된 QA 쌍
```

## 🔄 **처리 흐름**

### 1. **문서 업로드 흐름**
```
Frontend → Backend RAG API → VLLM RAG → Milvus DB
```

### 2. **RAG 챗봇 응답 흐름**
```
사용자 질문 → RAG 검색 → 컨텍스트 생성 → LLM 응답 → 캐릭터 스타일 적용
```

### 3. **MCP+RAG 통합 흐름**
```
사용자 질문 → RAG 검색 → 컨텍스트 포함 → MCP 도구 사용 → 최종 응답
```

## 🎯 **주요 개선사항**

### 1. **모델 지원 확장**
- VLLM 서버 + 로컬 모델 지원
- 자동 모드 감지 및 전환

### 2. **검색 기능 고도화**
- 의미적/키워드/하이브리드 검색
- 재랭킹 및 필터링
- 중복 제거

### 3. **설정 관리 시스템**
- 중앙화된 설정 관리
- 환경 변수 자동 로드
- 설정 파일 지원

### 4. **UI/UX 개선**
- 문서 업로드 인터페이스
- RAG 파이프라인 설정
- 실시간 상태 표시

### 5. **에러 처리 강화**
- 포괄적인 에러 처리
- 폴백 메커니즘
- 상세한 로깅

## 📈 **성능 최적화**

### 1. **비동기 처리**
- 모든 I/O 작업 비동기화
- 병렬 처리 지원

### 2. **캐싱**
- 임베딩 캐싱
- 검색 결과 캐싱

### 3. **배치 처리**
- 문서 배치 업로드
- 벡터화 배치 처리

이러한 변경으로 `rag` 브랜치는 단순한 챗봇에서 **문서 기반 지식 증강이 가능한 고도화된 AI 어시스턴트 시스템**으로 완전히 진화했습니다. 