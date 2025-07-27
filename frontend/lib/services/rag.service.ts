// API 클라이언트 대신 직접 fetch 사용
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

// 토큰 유틸리티 import
import { tokenUtils } from '@/lib/auth'

// ============================================================================
// 타입 정의
// ============================================================================

export interface QAChunk {
  question: string
  answer: string
  source: string
  page: number
  metadata?: Record<string, any>
}

export interface DocumentUploadRequest {
  group_id: number
  file_path: string
  source_name?: string
  max_qa_pairs?: number
}

export interface RAGSearchRequest {
  query: string
  top_k?: number
  min_score?: number
  include_context?: boolean
}

export interface RAGChatRequest {
  query: string
  group_id: number
  include_sources?: boolean
}

export interface SearchResult {
  text: string
  score: number
  source: string
  page: number
  question: string
  answer: string
}

export interface RAGSearchResponse {
  success: boolean
  query: string
  results: SearchResult[]
  total_found: number
  context?: string
}

export interface RAGResponse {
  query: string
  response: string
  sources?: Array<{
    source: string
    page: number
    score: number
    question: string
  }>
  context?: string
  confidence_score?: number
}

export interface DocumentUploadResponse {
  success: boolean
  message: string
  data: {
    qa_generated: number
    rag_stored: boolean
    source_name: string
    sample_qa: Array<{
      question: string
      answer: string
    }>
  }
}

export interface CollectionInfo {
  collection_name: string
  total_chunks: number
  embedding_dimension: number
  metric_type: string
}

export interface RAGDocument {
  document_id: string
  group_id: number
  original_filename: string
  source_name: string
  file_size?: number
  total_chunks: number
  qa_pairs_generated: number
  status: string
  error_message?: string
  created_at: string
  updated_at?: string
}

export interface RAGDocumentList {
  documents: RAGDocument[]
  total_count: number
}

export interface RAGDocumentSummary {
  total_documents: number
  total_chunks: number
  total_qa_pairs: number
  completed_documents: number
  processing_documents: number
}

export interface RAGHealthResponse {
  status: 'healthy' | 'unhealthy'
  rag_service?: any
  vllm_base_url?: string
  error?: string
}

// ============================================================================
// RAG 서비스 클래스
// ============================================================================

export class RAGService {
  private baseUrl: string

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'
  }

  // ============================================================================
  // 문서 업로드 및 처리
  // ============================================================================

  async uploadDocument(request: DocumentUploadRequest): Promise<DocumentUploadResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/rag/upload_document`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenUtils.getToken()}`
        },
        body: JSON.stringify(request)
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '문서 업로드 중 오류가 발생했습니다.')
      }
      
      return await response.json()
    } catch (error: any) {
      console.error('문서 업로드 실패:', error)
      throw new Error(error.message || '문서 업로드 중 오류가 발생했습니다.')
    }
  }

  // ============================================================================
  // RAG 검색
  // ============================================================================

  async search(request: RAGSearchRequest): Promise<RAGSearchResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/rag/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenUtils.getToken()}`
        },
        body: JSON.stringify(request)
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '검색 중 오류가 발생했습니다.')
      }
      
      return await response.json()
    } catch (error: any) {
      console.error('RAG 검색 실패:', error)
      throw new Error(error.message || '검색 중 오류가 발생했습니다.')
    }
  }

  // ============================================================================
  // RAG 채팅
  // ============================================================================

  async chat(request: RAGChatRequest): Promise<RAGResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/rag/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenUtils.getToken()}`
        },
        body: JSON.stringify(request)
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '채팅 중 오류가 발생했습니다.')
      }
      
      return await response.json()
    } catch (error: any) {
      console.error('RAG 채팅 실패:', error)
      throw new Error(error.message || '채팅 중 오류가 발생했습니다.')
    }
  }

  // ============================================================================
  // 헬스 체크
  // ============================================================================

  async healthCheck(): Promise<RAGHealthResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/rag/health`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${tokenUtils.getToken()}`
        }
      })
      
      if (!response.ok) {
        return {
          status: 'unhealthy',
          error: '헬스 체크 중 오류가 발생했습니다.'
        }
      }
      
      return await response.json()
    } catch (error: any) {
      console.error('RAG 헬스 체크 실패:', error)
      return {
        status: 'unhealthy',
        error: error.message || '헬스 체크 중 오류가 발생했습니다.'
      }
    }
  }

  // ============================================================================
  // 컬렉션 관리
  // ============================================================================

  async getCollectionInfo(): Promise<{ success: boolean; collection_info: CollectionInfo }> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/rag/collection_info`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${tokenUtils.getToken()}`
        }
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '컬렉션 정보 조회 중 오류가 발생했습니다.')
      }
      
      return await response.json()
    } catch (error: any) {
      console.error('컬렉션 정보 조회 실패:', error)
      throw new Error(error.message || '컬렉션 정보 조회 중 오류가 발생했습니다.')
    }
  }

  async clearCollection(): Promise<{ success: boolean; message: string }> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/rag/clear_collection`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${tokenUtils.getToken()}`
        }
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '컬렉션 초기화 중 오류가 발생했습니다.')
      }
      
      return await response.json()
    } catch (error: any) {
      console.error('컬렉션 초기화 실패:', error)
      throw new Error(error.message || '컬렉션 초기화 중 오류가 발생했습니다.')
    }
  }

  // ============================================================================
  // QA 데이터 저장
  // ============================================================================

  async storeQAChunks(qaData: QAChunk[], sourceFile: string = 'document.pdf'): Promise<{
    success: boolean
    message: string
    data: any
  }> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/rag/store_qa_chunks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenUtils.getToken()}`
        },
        body: JSON.stringify({
          qa_data: qaData,
          source_file: sourceFile
        })
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'QA 데이터 저장 중 오류가 발생했습니다.')
      }
      
      return await response.json()
    } catch (error: any) {
      console.error('QA 데이터 저장 실패:', error)
      throw new Error(error.message || 'QA 데이터 저장 중 오류가 발생했습니다.')
    }
  }

  // ============================================================================
  // 유틸리티 메서드
  // ============================================================================

  async isServiceAvailable(): Promise<boolean> {
    try {
      const health = await this.healthCheck()
      return health.status === 'healthy'
    } catch (error) {
      return false
    }
  }

  async getServiceStatus(): Promise<{
    available: boolean
    health: RAGHealthResponse
    collectionInfo?: CollectionInfo
  }> {
    const health = await this.healthCheck()
    const available = health.status === 'healthy'

    let collectionInfo: CollectionInfo | undefined
    if (available) {
      try {
        const info = await this.getCollectionInfo()
        collectionInfo = info.collection_info
      } catch (error) {
        console.warn('컬렉션 정보 조회 실패:', error)
      }
    }

    return {
      available,
      health,
      collectionInfo
    }
  }

  // ============================================================================
  // 문서 관리
  // ============================================================================

  async getDocumentsByGroup(groupId: number, skip: number = 0, limit: number = 100): Promise<RAGDocumentList> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/rag/documents/${groupId}?skip=${skip}&limit=${limit}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${tokenUtils.getToken()}`
        }
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '문서 목록 조회 중 오류가 발생했습니다.')
      }
      
      return await response.json()
    } catch (error: any) {
      console.error('문서 목록 조회 실패:', error)
      throw new Error(error.message || '문서 목록 조회 중 오류가 발생했습니다.')
    }
  }

  async getDocumentsSummary(groupId: number): Promise<RAGDocumentSummary> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/rag/documents/${groupId}/summary`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${tokenUtils.getToken()}`
        }
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '문서 요약 정보 조회 중 오류가 발생했습니다.')
      }
      
      const result = await response.json()
      return result.summary
    } catch (error: any) {
      console.error('문서 요약 정보 조회 실패:', error)
      throw new Error(error.message || '문서 요약 정보 조회 중 오류가 발생했습니다.')
    }
  }

  async deleteDocument(documentId: string): Promise<{ success: boolean; message: string }> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/rag/documents/${documentId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${tokenUtils.getToken()}`
        }
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '문서 삭제 중 오류가 발생했습니다.')
      }
      
      return await response.json()
    } catch (error: any) {
      console.error('문서 삭제 실패:', error)
      throw new Error(error.message || '문서 삭제 중 오류가 발생했습니다.')
    }
  }
}

// ============================================================================
// 전역 인스턴스
// ============================================================================

export const ragService = new RAGService()

// ============================================================================
// 훅 (React에서 사용)
// ============================================================================

import { useState, useCallback } from 'react'

export function useRAGService() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const uploadDocument = useCallback(async (request: DocumentUploadRequest) => {
    setLoading(true)
    setError(null)
    try {
      const result = await ragService.uploadDocument(request)
      return result
    } catch (err: any) {
      setError(err.message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  const search = useCallback(async (request: RAGSearchRequest) => {
    setLoading(true)
    setError(null)
    try {
      const result = await ragService.search(request)
      return result
    } catch (err: any) {
      setError(err.message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  const chat = useCallback(async (request: RAGChatRequest) => {
    setLoading(true)
    setError(null)
    try {
      const result = await ragService.chat(request)
      return result
    } catch (err: any) {
      setError(err.message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  const healthCheck = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await ragService.healthCheck()
      return result
    } catch (err: any) {
      setError(err.message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  const getServiceStatus = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await ragService.getServiceStatus()
      return result
    } catch (err: any) {
      setError(err.message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return {
    loading,
    error,
    uploadDocument,
    search,
    chat,
    healthCheck,
    getServiceStatus
  }
}

// ============================================================================
// 사용 예시
// ============================================================================

export async function exampleUsage() {
  try {
    // 서비스 상태 확인
    const status = await ragService.getServiceStatus()
    console.log('RAG 서비스 상태:', status)

    if (!status.available) {
      console.warn('RAG 서비스가 사용할 수 없습니다.')
      return
    }

    // 문서 업로드
    const uploadResult = await ragService.uploadDocument({
      group_id: 1,
      file_path: '/path/to/document.pdf',
      source_name: '테스트 문서',
      max_qa_pairs: 50
    })
    console.log('문서 업로드 결과:', uploadResult)

    // 검색
    const searchResult = await ragService.search({
      query: '파이썬이란 무엇인가요?',
      top_k: 3,
      min_score: 0.7,
      include_context: true
    })
    console.log('검색 결과:', searchResult)

    // 채팅
    const chatResult = await ragService.chat({
      query: '머신러닝에 대해 알려주세요',
      group_id: 1,
      include_sources: true
    })
    console.log('채팅 결과:', chatResult)

  } catch (error) {
    console.error('RAG 서비스 사용 중 오류:', error)
  }
} 