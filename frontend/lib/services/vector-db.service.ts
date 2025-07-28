import { apiClient } from '../api'

// 벡터DB 관련 타입 정의
export interface DocumentChunk {
    id: string
    text: string
    metadata: Record<string, any>
    embedding?: number[]
}

export interface StoreRequest {
    documents: DocumentChunk[]
}

export interface SearchRequest {
    query: string
    top_k: number
    score_threshold: number
}

export interface SearchResult {
    id: string
    text: string
    score: number
    metadata: Record<string, any>
}

export interface VectorDBResponse {
    success: boolean
    message: string
    data?: any
}

export interface VectorSearchResponse {
    results: SearchResult[]
    query_embedding: number[]
    total_found: number
}

export interface VectorStoreResponse {
    stored_count: number
    total_chunks: number
    success: boolean
}

export interface DocumentUploadResponse {
    status: string
    message: string
    pipeline_info?: {
        qa_count: number
        source_file: string
    }
}

export class VectorDBService {
    private static baseUrl = '/api/v1'



    // 벡터DB 초기화
    static async initVectorDB(config?: any): Promise<VectorDBResponse> {
        return apiClient.post<VectorDBResponse>(`${this.baseUrl}/rag/init_vector_db`, config)
    }

    // 문서 저장 (임베딩 포함) - FormData 형태로 변경
    static async storeDocuments(request: StoreRequest): Promise<VectorStoreResponse> {
        // StoreRequest를 FormData로 변환
        const formData = new FormData()

        // 파일이 있다면 추가
        if (request.documents && request.documents.length > 0) {
            // 실제로는 파일 업로드가 필요하므로 다른 방식으로 처리
            throw new Error("문서 저장은 파일 업로드를 통해 처리해야 합니다.")
        }

        return apiClient.post<VectorStoreResponse>(`${this.baseUrl}/rag/upload_document_gpu`, formData)
    }

    // 문서 검색
    static async searchDocuments(request: SearchRequest): Promise<SearchResult[]> {
        return apiClient.post<SearchResult[]>(`${this.baseUrl}/rag/search_documents`, request)
    }

    // 임베딩 생성 및 검색
    static async embedAndSearch(
        query: string,
        topK: number = 5,
        scoreThreshold: number = 0.5
    ): Promise<SearchResult[]> {
        const params = new URLSearchParams({
            query,
            top_k: topK.toString(),
            score_threshold: scoreThreshold.toString()
        })
        return apiClient.post<any>(`${this.baseUrl}/rag/embed_and_search?${params}`)
    }

    // 벡터DB 통계 - 백엔드 프록시 사용
    static async getStats(): Promise<any> {
        return apiClient.get<any>(`${this.baseUrl}/rag/vector_stats`)
    }

    // 벡터DB 초기화 - 백엔드 프록시 사용
    static async clearVectorDB(): Promise<VectorDBResponse> {
        return apiClient.delete<VectorDBResponse>(`${this.baseUrl}/rag/clear_vector_store`)
    }

    // 문서 업로드 및 벡터DB 저장
    static async uploadAndStoreDocuments(
        files: File[]
    ): Promise<VectorStoreResponse> {
        // 백엔드의 upload_document_gpu 엔드포인트에 맞게 FormData로 전송
        const formData = new FormData()

        // 첫 번째 파일만 처리 (백엔드가 단일 파일만 지원)
        if (files.length > 0) {
            formData.append('file', files[0])
            formData.append('system_message', '당신은 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하는 AI 어시스턴트입니다.')
            formData.append('influencer_name', 'AI')
        }

        // 백엔드 엔드포인트 호출
        const response = await apiClient.post<DocumentUploadResponse>(`${this.baseUrl}/rag/upload_document_gpu`, formData)

        return {
            stored_count: response.pipeline_info?.qa_count || 0,
            total_chunks: response.pipeline_info?.qa_count || 0,
            success: response.status === 'success'
        }
    }

    // 파일을 텍스트로 읽기
    private static async readFileAsText(file: File): Promise<string> {
        return new Promise((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = (e) => {
                const text = e.target?.result as string
                resolve(text)
            }
            reader.onerror = reject
            reader.readAsText(file)
        })
    }

    // 텍스트를 청크로 분할
    private static splitTextIntoChunks(
        text: string,
        chunkSize: number,
        chunkOverlap: number
    ): string[] {
        const chunks: string[] = []
        let start = 0

        while (start < text.length) {
            const end = Math.min(start + chunkSize, text.length)
            const chunk = text.slice(start, end)
            chunks.push(chunk)

            if (end === text.length) break
            start = end - chunkOverlap
        }

        return chunks
    }
} 