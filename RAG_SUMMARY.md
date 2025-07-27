# RAG 브랜치 핵심 변경사항 요약

## 🎯 **주요 개선사항**

### ✅ **새로 추가된 기능**
- **RAG (Retrieval-Augmented Generation)** 시스템 완전 구현
- **MCP + RAG 통합** 처리
- **문서 업로드 및 관리** 시스템
- **벡터 검색** 및 **의미적 검색**
- **인플루언서별 RAG 파이프라인**

### 🔧 **기술적 개선**
- **VLLM + 로컬 모델** 이중 지원
- **Milvus 벡터 데이터베이스** 연동
- **BGE-M3 임베딩 모델** 사용
- **고급 검색 전략** (의미적/키워드/하이브리드)
- **재랭킹 및 필터링** 시스템

## 📁 **새로 추가된 파일들**

### Backend
```
backend/auto_rag/
├── config.py              # RAG 시스템 설정 관리
├── chat_generator.py      # VLLM/로컬 모델 채팅 생성기
├── rag_search.py          # 고급 검색 시스템
├── embed_store.py         # VLLM 서버 리다이렉트
├── document_loader.py     # 문서 처리 및 청킹
├── chatbot_pipeline.py    # 전체 RAG 파이프라인
├── rag_chatbot.py         # RAG 전용 챗봇
└── requirements_rag.txt   # RAG 의존성
```

### VLLM Server
```
vllm/app/routers/rag.py    # VLLM 서버 RAG 통합
```

### Frontend
```
frontend/components/rag-pipeline-setup.tsx  # RAG UI
frontend/lib/services/mcp.service.ts        # RAG API 클라이언트
```

## 🔄 **처리 흐름**

### 기존 (develop 브랜치)
```
사용자 질문 → LLM 응답
```

### 새로운 (rag 브랜치)
```
사용자 질문 → RAG 검색 → 컨텍스트 생성 → LLM 응답 → 캐릭터 스타일 적용
```

### MCP+RAG 통합
```
사용자 질문 → RAG 검색 → 컨텍스트 포함 → MCP 도구 사용 → 최종 응답
```

## 🎨 **UI/UX 개선**

### 새로운 기능
- **문서 업로드 인터페이스**
- **RAG 파이프라인 설정**
- **업로드된 문서 관리**
- **실시간 상태 표시**

## 📊 **성능 최적화**

### 개선사항
- **비동기 처리** 모든 I/O 작업
- **캐싱** 임베딩 및 검색 결과
- **배치 처리** 문서 업로드 및 벡터화
- **에러 처리** 포괄적인 폴백 메커니즘

## 🔐 **보안 및 설정**

### 새로운 기능
- **중앙화된 설정 관리**
- **환경 변수 자동 로드**
- **설정 파일 지원** (YAML/JSON)
- **모델 모드 자동 감지**

## 🚀 **결과**

`rag` 브랜치는 기존의 단순한 챗봇에서 **문서 기반 지식 증강이 가능한 고도화된 AI 어시스턴트 시스템**으로 완전히 진화했습니다.

### 핵심 가치
- ✅ **정확한 정보 제공** (문서 기반)
- ✅ **실시간 도구 사용** (MCP 통합)
- ✅ **캐릭터 정체성 유지** (인플루언서별)
- ✅ **확장 가능한 아키텍처** (모듈화)
- ✅ **사용자 친화적 UI** (직관적 인터페이스) 