# RAG 브랜치 파일별 상세 분석

## 🔧 **핵심 설정 파일**

### 📄 **backend/auto_rag/config.py**

#### **주요 클래스 구조:**
```python
@dataclass
class RAGSystemConfig:
    model_mode: ModelMode = ModelMode.AUTO
    database: DatabaseConfig
    vllm: VLLMConfig
    local_model: LocalModelConfig
    rag: RAGConfig
    server: ServerConfig
    security: SecurityConfig
```

#### **핵심 기능:**
1. **모델 모드 자동 감지**
   ```python
   def _detect_model_mode(self) -> ModelMode:
       # VLLM 서버 연결 테스트
       # GPU 사용 가능성 확인
       # 기본값은 VLLM (서버 기반이 권장)
   ```

2. **환경 변수 자동 로드**
   ```python
   def _load_tokens_from_env(self):
       self.security.hf_token = os.getenv(self.security.hf_token_env)
       self.security.api_key = os.getenv(self.security.api_key_env)
   ```

3. **설정 파일 지원**
   ```python
   @classmethod
   def from_file(cls, config_path: str) -> 'RAGSystemConfig':
       # JSON/YAML 파일에서 설정 로드
   ```

## 🤖 **채팅 생성 시스템**

### 📄 **backend/auto_rag/chat_generator.py**

#### **주요 클래스:**
```python
class VLLMGenerator(ITextGenerator):
    """VLLM 서버 기반 텍스트 생성기"""
    
class LocalGenerator(ITextGenerator):
    """로컬 모델 기반 텍스트 생성기"""
    
class ChatGenerator:
    """통합 채팅 생성기"""
```

#### **핵심 기능:**
1. **VLLM 어댑터 로딩**
   ```python
   async def load_vllm_adapter(self, adapter_name: str, hf_token: Optional[str] = None) -> bool:
       # VLLM 서버에 LoRA 어댑터 로드
   ```

2. **RAG 컨텍스트 기반 응답 생성**
   ```python
   async def generate_response(self, query: str, context: str = "", max_tokens: int = 512) -> str:
       # 컨텍스트를 포함한 프롬프트 생성
       # VLLM 또는 로컬 모델로 응답 생성
   ```

3. **프롬프트 템플릿**
   ```python
   class PromptTemplate:
       system_message: str = (
           "당신은 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하는 AI 어시스턴트입니다. "
           "**중요**: 문서에 포함된 모든 내용은 절대 요약하거나 생략하지 말고, 원문 그대로 완전히 포함해야 합니다."
       )
   ```

## 🔍 **검색 시스템**

### 📄 **backend/auto_rag/rag_search.py**

#### **검색 전략:**
```python
class SearchStrategy(Enum):
    SEMANTIC = "semantic"    # 의미적 유사도
    KEYWORD = "keyword"      # 키워드 매칭
    HYBRID = "hybrid"        # 의미적 + 키워드
```

#### **필터링 시스템:**
```python
class ScoreFilter(SearchFilter):
    """점수 기반 필터"""
    
class DuplicateFilter(SearchFilter):
    """중복 제거 필터"""
    
class SourceFilter(SearchFilter):
    """출처 기반 필터"""
```

#### **검색 결과 처리:**
```python
class RAGSearcher:
    def search(self, query: str, **kwargs) -> List[SearchResult]:
        # 벡터 검색 수행
        # 필터 적용
        # 재랭킹 (선택적)
        
    def get_context(self, results: List[SearchResult], include_sources: bool = True) -> str:
        # 검색 결과를 컨텍스트로 변환
```

## 📚 **임베딩 스토어**

### 📄 **backend/auto_rag/embed_store.py**

#### **VLLM 서버 리다이렉트:**
```python
class EmbedStore:
    def __init__(self, milvus_config: Dict = None, embed_model_name: str = "BAAI/bge-m3"):
        self.vllm_base_url = "http://localhost:8000"
    
    async def add_document(self, file_path: str, group_id: str = "1", ...) -> bool:
        # VLLM 서버의 /rag/upload_document 엔드포인트 호출
        
    async def search(self, query: str, group_id: str = "1", top_k: int = 5) -> List[Dict]:
        # VLLM 서버의 /rag/search 엔드포인트 호출
```

## 🚀 **VLLM 서버 RAG 통합**

### 📄 **vllm/app/routers/rag.py**

#### **엔드포인트 구조:**
```python
@router.post("/upload_document")
async def upload_document(
    file: UploadFile = File(...),
    group_id: str = Form("1"),
    chunk_size: int = Form(1000),
    chunk_overlap: int = Form(200),
    top_k: int = Form(5)
):
    # 문서 업로드 및 벡터화

@router.post("/search")
async def search_documents(
    query: str,
    group_id: str = "1",
    top_k: int = 5
):
    # 의미적 검색 수행

@router.post("/chat")
async def rag_chat(
    message: str,
    group_id: str = "1",
    top_k: int = 5
):
    # RAG 기반 챗봇 응답
```

#### **Milvus 연동:**
```python
def initialize_rag_components():
    milvus_config = {
        "host": os.getenv("MILVUS_HOST", "localhost"),
        "port": int(os.getenv("MILVUS_PORT", "19530")),
        "collection_name": "rag_documents",
        "dim": 1024  # BGE-M3 임베딩 차원
    }
```

## 🔄 **백엔드 RAG 프록시**

### 📄 **backend/app/api/v1/endpoints/rag.py**

#### **프록시 기능:**
```python
async def get_vllm_rag_client():
    """VLLM RAG 클라이언트 생성"""
    return httpx.AsyncClient(
        base_url=VLLM_RAG_BASE_URL,
        timeout=httpx.Timeout(300.0)
    )

@router.post("/upload_file")
async def upload_file(
    file: UploadFile = File(...),
    group_id: str = Form("1"),
    chunk_size: int = Form(1000),
    chunk_overlap: int = Form(200),
    top_k: int = Form(5)
):
    # VLLM 서버로 파일 업로드 요청 전달
```

## 🎯 **MCP+RAG 통합**

### 📄 **backend/app/api/v1/endpoints/mcp.py**

#### **새로운 엔드포인트:**
```python
@router.post("/process-with-rag")
async def process_message_with_rag_and_mcp(
    message: str = Body(..., embed=True),
    influencer_id: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    # 1. RAG 검색으로 관련 문서 찾기
    # 2. 컨텍스트 생성
    # 3. MCP 도구 사용 여부 판단
    # 4. 최종 응답 생성

@router.post("/create-rag-pipeline")
async def create_rag_pipeline(
    influencer_id: str = Body(..., embed=True),
    pdf_path: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    # 인플루언서별 RAG 파이프라인 생성
```

## 🎨 **프론트엔드 RAG UI**

### 📄 **frontend/components/rag-pipeline-setup.tsx**

#### **주요 상태:**
```typescript
const [uploadMode, setUploadMode] = useState<'path' | 'file'>('path')
const [uploadedDocuments, setUploadedDocuments] = useState<UploadedDocument[]>([])
const [isLoading, setIsLoading] = useState(false)
```

#### **핵심 기능:**
```typescript
const handleCreatePipeline = async () => {
    // RAG 파이프라인 생성
    const response = await MCPService.createRAGPipeline(request)
}

const handleRemoveDocument = async (pdfPath: string) => {
    // 문서 삭제
    const response = await MCPService.removeUploadedDocument(groupId, pdfPath)
}
```

### 📄 **frontend/lib/services/mcp.service.ts**

#### **새로운 인터페이스:**
```typescript
export interface RAGMCPChatResponse {
    response: string
    source: 'rag' | 'mcp' | 'llm' | 'error'
    rag_context: string
    mcp_tools_used: string[]
    confidence: number
}

export interface UploadedDocument {
    pdf_path: string
    group_id: number
    lora_adapter: string
    system_message: string
    influencer_name: string
    temperature: number
    chunk_size: number
    chunk_overlap: number
    top_k: number
    status: string
    file_size: number
    file_size_formatted: string
    uploaded_at: string
}
```

#### **새로운 메서드:**
```typescript
static async processMessageWithRAG(request: MCPChatRequest): Promise<RAGMCPChatResponse>
static async createRAGPipeline(request: CreateRAGPipelineRequest): Promise<CreateRAGPipelineResponse>
static async getUploadedDocuments(groupId: number): Promise<UploadedDocumentsResponse>
static async removeUploadedDocument(groupId: number, pdfPath: string): Promise<RemoveDocumentResponse>
```

## 📊 **데이터 처리 파이프라인**

### 📄 **backend/auto_rag/chatbot_pipeline.py**

#### **전체 파이프라인:**
```python
class ChatbotPipeline:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.embed_store = None
        self.rag_search = None
        self.chat_generator = None
    
    async def run_pipeline(self, pdf_path: str) -> Dict[str, Any]:
        # 1. 문서 로드 및 청킹
        # 2. 임베딩 생성
        # 3. 벡터 저장
        # 4. QA 쌍 생성
        # 5. 파인튜닝 데이터 준비
```

### 📄 **backend/auto_rag/document_loader.py**

#### **문서 처리:**
```python
class DocumentLoader:
    def load_pdf(self, pdf_path: str) -> List[str]:
        # PDF 텍스트 추출
        
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        # 텍스트 청킹
        
    def extract_metadata(self, pdf_path: str) -> Dict[str, Any]:
        # 메타데이터 추출
```

## 🔧 **설정 및 의존성**

### 📄 **backend/auto_rag/requirements_rag.txt**
```
pymilvus==2.3.4          # Milvus 벡터 데이터베이스
sentence-transformers==2.2.2  # 임베딩 모델
chromadb==0.4.22         # 벡터 데이터베이스 (대안)
langchain==0.1.0         # LangChain 프레임워크
langchain-community==0.0.10
```

### 📄 **backend/auto_rag/.gitignore**
```
rag_data/                # RAG 데이터 디렉토리
logs/                    # 로그 파일
temp/                    # 임시 파일
*.db                     # 데이터베이스 파일
```

## 🔄 **처리 흐름 상세**

### 1. **문서 업로드 흐름:**
```
Frontend (rag-pipeline-setup.tsx)
    ↓
Backend MCP API (/create-rag-pipeline)
    ↓
VLLM RAG API (/upload_document)
    ↓
Milvus Vector Database
```

### 2. **RAG 챗봇 응답 흐름:**
```
사용자 질문
    ↓
RAG 검색 (rag_search.py)
    ↓
컨텍스트 생성
    ↓
LLM 응답 생성 (chat_generator.py)
    ↓
캐릭터 스타일 적용
    ↓
최종 응답
```

### 3. **MCP+RAG 통합 흐름:**
```
사용자 질문
    ↓
RAG 검색 (관련 문서 찾기)
    ↓
컨텍스트 포함
    ↓
MCP 도구 사용 여부 판단
    ↓
도구 사용 (필요시)
    ↓
최종 응답 생성
```

이러한 파일 구조와 기능들로 `rag` 브랜치는 **완전히 새로운 RAG 시스템**을 구축하여, 기존의 단순한 챗봇에서 **문서 기반 지식 증강이 가능한 고도화된 AI 어시스턴트**로 진화했습니다. 