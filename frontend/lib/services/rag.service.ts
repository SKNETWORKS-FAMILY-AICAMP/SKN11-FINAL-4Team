import { apiClient } from '../api';

export interface RAGUploadRequest {
  group_id: number;
  pdf_path: string;
  system_message?: string;
  influencer_name?: string;
}

export interface RAGUploadResponse {
  status: string;
  message: string;
  pipeline_info: {
    group_id: number;
    pdf_path: string;
    qa_count: number;
    system_message: string;
    influencer_name: string;
    created_at: string;
  };
}

export interface RAGChatRequest {
  message: string;  // query를 message로 변경
  similarity_threshold?: number;  // 추가
  max_tokens?: number;  // 추가
  include_sources?: boolean;
}

export interface RAGSource {
  text: string;
  score: number;
  source: string;
  page: number;
}

export interface RAGChatResponse {
  query: string;
  response: string;
  timestamp: string;
  sources?: RAGSource[];
  context_preview?: string;
  model_info?: {
    influencer_name: string;
    system_message: string;
  };
  error?: string;
}

export interface RAGPipelineInfo {
  group_id: number;
  pdf_path: string;
  qa_count: number;
  system_message: string;
  influencer_name: string;
  created_at: string;
}

export interface RAGHealthResponse {
  status: string;
  vllm_server: string;
  active_pipelines: number;
  pipeline_groups: number[];
  timestamp: string;
}

export class RAGService {
  /**
   * 문서 업로드 및 RAG 파이프라인 생성 (GPU 기반)
   */
  static async uploadDocument(request: RAGUploadRequest): Promise<RAGUploadResponse> {
    return await apiClient.post<RAGUploadResponse>('/api/v1/rag/upload_document_gpu', request);
  }

  /**
   * RAG 채팅 (GPU 기반)
   */
  static async chat(request: RAGChatRequest): Promise<RAGChatResponse> {
    return await apiClient.post<RAGChatResponse>('/api/v1/rag/chat_gpu', request);
  }

  /**
   * RAG 파이프라인 상태 조회
   */
  static async getPipelineStatus(groupId: number): Promise<RAGPipelineInfo | null> {
    try {
      return await apiClient.get<RAGPipelineInfo>(`/api/v1/rag/status/${groupId}`);
    } catch (error) {
      // 404 오류는 null 반환 (파이프라인이 없는 경우)
      if (error instanceof Error && error.message.includes('404')) {
        return null;
      }
      throw error;
    }
  }

  /**
   * RAG 서비스 상태 확인
   */
  static async getHealth(): Promise<RAGHealthResponse> {
    return await apiClient.get<RAGHealthResponse>('/api/v1/rag/health');
  }

  /**
   * 모든 RAG 파이프라인 목록 조회
   */
  static async getPipelines(): Promise<RAGPipelineInfo[]> {
    return await apiClient.get<RAGPipelineInfo[]>('/api/v1/rag/pipelines');
  }

  /**
   * RAG 파이프라인 정리
   */
  static async cleanupPipeline(groupId: number): Promise<{ status: string; message: string }> {
    return await apiClient.delete<{ status: string; message: string }>(`/api/v1/rag/cleanup/${groupId}`);
  }

  /**
   * 파일 업로드 (FormData 사용, GPU 기반)
   */
  static async uploadFile(
    file: File,
    groupId: number = 1,
    systemMessage?: string,
    influencerName?: string
  ): Promise<RAGUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('group_id', groupId.toString());
    if (systemMessage) formData.append('system_message', systemMessage);
    if (influencerName) formData.append('influencer_name', influencerName);

    return await apiClient.post<RAGUploadResponse>('/api/v1/rag/upload_document_gpu', formData, {
      headers: {}, // FormData는 자동으로 Content-Type 설정
    });
  }
} 