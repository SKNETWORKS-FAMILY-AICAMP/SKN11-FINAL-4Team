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

export class VectorDBService {
    private static baseUrl = '/api/v1'



    // 벡터DB 초기화
    static async initVectorDB(config?: any): Promise<VectorDBResponse> {
        return apiClient.post<VectorDBResponse>(`${this.baseUrl}/rag/init_vector_db`, config)
    }

    // 문서 저장 (임베딩 포함)
    static async storeDocuments(request: StoreRequest): Promise<VectorStoreResponse> {
        return apiClient.post<VectorStoreResponse>(`${this.baseUrl}/rag/store_documents`, request)
    }

    // 문서 검색
    static async searchDocuments(request: SearchRequest): Promise<SearchResult[]> {
        return apiClient.post<SearchResult[]>(`${this.baseUrl}/rag/search_documents`, request)
    }

    // 통합 검색 (임베딩 + 검색)
    static async embedAndSearch(query: string, top_k: number = 5, score_threshold: number = 0.7): Promise<SearchResult[]> {
        return apiClient.post<SearchResult[]>(`${this.baseUrl}/rag/embed_and_search`, {
            query,
            top_k,
            score_threshold
        })
    }

    // 벡터DB 통계
    static async getStats(): Promise<any> {
        return apiClient.get<any>(`${this.baseUrl}/rag/vector_stats`)
    }

    // 벡터DB 초기화
    static async clearVectorDB(): Promise<VectorDBResponse> {
        return apiClient.delete<VectorDBResponse>(`${this.baseUrl}/rag/clear_vector_store`)
    }

    // 문서 업로드 및 벡터DB 저장
    static async uploadAndStoreDocuments(
        files: File[],
        chunkSize: number = 1000,
        chunkOverlap: number = 200
    ): Promise<VectorStoreResponse> {
        // 파일을 텍스트로 변환하고 청크로 분할
        const documents: DocumentChunk[] = []

        for (const file of files) {
            try {
                // 파일을 텍스트로 읽기 (PDF의 경우 PDF.js 사용 필요)
                const text = await this.readFileAsText(file)

                // 텍스트를 청크로 분할
                const chunks = this.splitTextIntoChunks(text, chunkSize, chunkOverlap)

                // 청크를 DocumentChunk로 변환
                chunks.forEach((chunk, index) => {
                    documents.push({
                        id: `${file.name}_${index}`,
                        text: chunk,
                        metadata: {
                            filename: file.name,
                            filesize: file.size,
                            chunk_index: index,
                            total_chunks: chunks.length,
                            chunk_size: chunkSize,
                            chunk_overlap: chunkOverlap
                        }
                    })
                })
            } catch (error) {
                console.error(`Error processing file ${file.name}:`, error)
            }
        }

        // 벡터DB에 저장
        return this.storeDocuments({ documents })
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