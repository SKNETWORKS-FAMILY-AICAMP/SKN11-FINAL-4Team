import json
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
from pymilvus import MilvusClient

logger = logging.getLogger(__name__)
router = APIRouter()

# 전역 Milvus 클라이언트
milvus_client = None
collection_name = "rag_documents"


class VectorDBConfig(BaseModel):
    """벡터DB 설정"""

    uri: str = "./milvus_vector.db"
    collection_name: str = "rag_documents"
    dimension: int = 1024  # BGE-M3 기본 차원


class DocumentChunk(BaseModel):
    """문서 청크"""

    id: str
    text: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


class StoreRequest(BaseModel):
    """문서 저장 요청"""

    documents: List[DocumentChunk]


class SearchRequest(BaseModel):
    """검색 요청"""

    query: str
    top_k: int = 5
    score_threshold: float = 0.4


class SearchResult(BaseModel):
    """검색 결과"""

    id: str
    text: str
    score: float
    metadata: Dict[str, Any]


class VectorDBResponse(BaseModel):
    """벡터DB 응답"""

    success: bool
    message: str
    data: Optional[Any] = None


def initialize_milvus(config: VectorDBConfig = None):
    """Milvus 초기화"""
    global milvus_client, collection_name

    if config is None:
        config = VectorDBConfig()

    try:
        # Milvus 클라이언트 생성
        milvus_client = MilvusClient(uri=config.uri)
        collection_name = config.collection_name

        # 컬렉션이 없으면 생성
        if not milvus_client.has_collection(collection_name=collection_name):
            milvus_client.create_collection(
                collection_name=collection_name,
                dimension=config.dimension,
                metric_type="COSINE",
                index_type="AUTOINDEX",
            )
            logger.info(f"✅ 새 컬렉션 생성: {collection_name}")
        else:
            logger.info(f"✅ 기존 컬렉션 사용: {collection_name}")

        return True

    except Exception as e:
        logger.error(f"❌ Milvus 초기화 실패: {e}")
        return False


@router.post("/vector-db/init", response_model=VectorDBResponse)
async def init_vector_db(config: VectorDBConfig):
    """벡터DB 초기화"""
    try:
        success = initialize_milvus(config)
        if success:
            return VectorDBResponse(success=True, message="벡터DB 초기화 완료")
        else:
            raise HTTPException(status_code=500, detail="벡터DB 초기화 실패")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"초기화 실패: {str(e)}")


@router.post("/vector-db/store", response_model=VectorDBResponse)
async def store_documents(request: StoreRequest):
    """문서를 벡터DB에 저장"""
    global milvus_client

    if milvus_client is None:
        raise HTTPException(status_code=500, detail="벡터DB가 초기화되지 않았습니다")

    try:
        # 데이터 준비
        data = []
        for i, doc in enumerate(request.documents):
            if doc.embedding is None:
                raise HTTPException(
                    status_code=400, detail=f"문서 {doc.id}에 임베딩이 없습니다"
                )

            data.append(
                {
                    "id": i + 1,  # 정수 ID
                    "vector": doc.embedding,
                    "text": doc.text,
                    "metadata": json.dumps(doc.metadata, ensure_ascii=False),
                }
            )

        # Milvus에 저장
        result = milvus_client.insert(collection_name=collection_name, data=data)

        logger.info(f"✅ {len(request.documents)}개 문서 저장 완료")

        return VectorDBResponse(
            success=True,
            message=f"{len(request.documents)}개 문서 저장 완료",
            data={"stored_count": len(request.documents)},
        )

    except Exception as e:
        logger.error(f"❌ 문서 저장 실패: {e}")
        raise HTTPException(status_code=500, detail=f"저장 실패: {str(e)}")


@router.post("/vector-db/search", response_model=List[SearchResult])
async def search_documents(request: SearchRequest):
    """문서 검색 (임베딩 자동 생성)"""
    global milvus_client

    if milvus_client is None:
        raise HTTPException(status_code=500, detail="벡터DB가 초기화되지 않았습니다")

    try:
        # 1. 쿼리 임베딩 생성
        from app.routers.embedding import embedding_model

        if embedding_model is None:
            raise HTTPException(
                status_code=500, detail="임베딩 모델이 초기화되지 않았습니다"
            )

        query_embedding = embedding_model.encode(
            [request.query],
            batch_size=1,
            show_progress_bar=False,
            convert_to_numpy=True,
        )[0].tolist()

        # 2. 검색 실행
        results = milvus_client.search(
            collection_name=collection_name,
            data=[query_embedding],
            limit=request.top_k,
            output_fields=["text", "metadata"],
        )

        # 3. 결과 변환
        search_results = []
        for hit in results[0]:
            metadata = json.loads(hit["entity"]["metadata"])
            score = 1 - hit["distance"]  # 거리를 유사도로 변환

            if score >= request.score_threshold:
                # 안전한 필드 접근
                text = hit["entity"].get("text", "")
                chunk_id = metadata.get("chunk_id", "unknown")

                search_results.append(
                    SearchResult(
                        id=str(chunk_id),  # 문자열로 변환
                        text=text,
                        score=score,
                        metadata=metadata,
                    )
                )

        return search_results

    except Exception as e:
        logger.error(f"❌ 검색 실패: {e}")
        raise HTTPException(status_code=500, detail=f"검색 실패: {str(e)}")


@router.post("/vector-db/embed-and-store", response_model=VectorDBResponse)
async def embed_and_store_documents(request: StoreRequest):
    """임베딩 생성 후 벡터DB에 저장 (통합 API)"""
    global milvus_client

    if milvus_client is None:
        raise HTTPException(status_code=500, detail="벡터DB가 초기화되지 않았습니다")

    try:
        # 1. 텍스트 추출
        texts = [doc.text for doc in request.documents]

        # 2. 임베딩 생성 (embedding.py의 모델 사용)
        from app.routers.embedding import embedding_model

        if embedding_model is None:
            raise HTTPException(
                status_code=500, detail="임베딩 모델이 초기화되지 않았습니다"
            )

        embeddings = embedding_model.encode(
            texts, batch_size=32, show_progress_bar=True, convert_to_numpy=True
        )

        # 3. 임베딩을 문서에 할당
        for i, doc in enumerate(request.documents):
            doc.embedding = embeddings[i].tolist()

        # 4. 벡터DB에 저장
        data = []
        for i, doc in enumerate(request.documents):
            data.append(
                {
                    "id": i + 1,
                    "vector": doc.embedding,
                    "text": doc.text,
                    "metadata": json.dumps(doc.metadata, ensure_ascii=False),
                }
            )

        # Milvus에 저장
        result = milvus_client.insert(collection_name=collection_name, data=data)

        logger.info(f"✅ {len(request.documents)}개 문서 임베딩 및 저장 완료")

        return VectorDBResponse(
            success=True,
            message=f"{len(request.documents)}개 문서 임베딩 및 저장 완료",
            data={"stored_count": len(request.documents)},
        )

    except Exception as e:
        logger.error(f"❌ 임베딩 및 저장 실패: {e}")
        raise HTTPException(status_code=500, detail=f"처리 실패: {str(e)}")


@router.post("/vector-db/embed-and-search", response_model=List[SearchResult])
async def embed_and_search(query: str, top_k: int = 5, score_threshold: float = 0.4):
    """쿼리 임베딩 생성 후 검색 (통합 API)"""
    global milvus_client

    if milvus_client is None:
        raise HTTPException(status_code=500, detail="벡터DB가 초기화되지 않았습니다")

    try:
        # 1. 쿼리 임베딩 생성 (embedding.py의 모델 사용)
        from app.routers.embedding import embedding_model

        if embedding_model is None:
            raise HTTPException(
                status_code=500, detail="임베딩 모델이 초기화되지 않았습니다"
            )

        query_embedding = embedding_model.encode(
            [query], batch_size=1, show_progress_bar=False, convert_to_numpy=True
        )[0].tolist()

        # 2. 검색 실행
        results = milvus_client.search(
            collection_name=collection_name,
            data=[query_embedding],
            limit=top_k,
            output_fields=["text", "metadata"],
        )

        # 3. 결과 변환
        search_results = []
        for hit in results[0]:
            metadata = json.loads(hit["entity"]["metadata"])
            score = 1 - hit["distance"]

            if score >= score_threshold:
                # 안전한 필드 접근
                text = hit["entity"].get("text", "")
                chunk_id = metadata.get("chunk_id", "unknown")

                search_results.append(
                    SearchResult(
                        id=str(chunk_id),  # 문자열로 변환
                        text=text,
                        score=score,
                        metadata=metadata,
                    )
                )

        return search_results

    except Exception as e:
        logger.error(f"❌ 임베딩 및 검색 실패: {e}")
        raise HTTPException(status_code=500, detail=f"처리 실패: {str(e)}")


@router.get("/vector-db/stats", response_model=Dict[str, Any])
async def get_vector_db_stats():
    """벡터DB 통계 조회"""
    global milvus_client, collection_name

    if milvus_client is None:
        raise HTTPException(status_code=500, detail="벡터DB가 초기화되지 않았습니다")

    try:
        stats = milvus_client.get_collection_stats(collection_name=collection_name)
        return {
            "collection_name": collection_name,
            "num_entities": stats.get("row_count", 0),
            "status": "active",
        }
    except Exception as e:
        logger.error(f"❌ 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


@router.delete("/vector-db/clear", response_model=VectorDBResponse)
async def clear_vector_db():
    """벡터DB 초기화"""
    global milvus_client, collection_name

    if milvus_client is None:
        raise HTTPException(status_code=500, detail="벡터DB가 초기화되지 않았습니다")

    try:
        milvus_client.drop_collection(collection_name=collection_name)

        # 컬렉션 재생성
        config = VectorDBConfig()
        milvus_client.create_collection(
            collection_name=collection_name,
            dimension=config.dimension,
            metric_type="COSINE",
            index_type="AUTOINDEX",
        )

        logger.info(f"✅ 벡터DB 초기화 완료: {collection_name}")

        return VectorDBResponse(success=True, message="벡터DB 초기화 완료")

    except Exception as e:
        logger.error(f"❌ 벡터DB 초기화 실패: {e}")
        raise HTTPException(status_code=500, detail=f"초기화 실패: {str(e)}")


# 서버 시작 시 자동 초기화
def init_vector_db_on_startup():
    """서버 시작 시 벡터DB 자동 초기화"""
    try:
        success = initialize_milvus()
        if success:
            logger.info("✅ 벡터DB 자동 초기화 완료")
        else:
            logger.warning("⚠️ 벡터DB 자동 초기화 실패")
    except Exception as e:
        logger.error(f"❌ 벡터DB 자동 초기화 오류: {e}")
