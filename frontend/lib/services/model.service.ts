import apiClient from '../api'

export interface AIInfluencer {
  influencer_id: string
  user_id: string
  group_id: number
  style_preset_id: string
  mbti_id?: number
  influencer_name: string
  influencer_description?: string
  image_url?: string
  influencer_data_url?: string
  learning_status: number
  influencer_model_repo: string
  chatbot_option: boolean
  created_at?: string
  updated_at?: string
  style_preset?: StylePreset
  mbti?: ModelMBTI
}

export interface StylePreset {
  style_preset_id: string
  style_preset_name: string
  influencer_type: number
  influencer_gender: number
  influencer_age_group: number
  influencer_hairstyle: string
  influencer_style: string
  influencer_personality: string
  influencer_speech: string
  created_at?: string
  updated_at?: string
}

export interface ModelMBTI {
  mbti_id: number
  mbti_name: string
  mbti_traits: string
  mbti_speech: string
}

export interface CreateInfluencerRequest {
  user_id: string
  group_id: number
  style_preset_id: string
  mbti_id?: number
  influencer_name: string
  image_url?: string
  influencer_data_url?: string
  learning_status: number
  influencer_model_repo: string
  chatbot_option: boolean
}

export interface UpdateInfluencerRequest {
  style_preset_id?: string
  mbti_id?: number
  influencer_name?: string
  image_url?: string
  influencer_data_url?: string
  learning_status?: number
  influencer_model_repo?: string
  chatbot_option?: boolean
}

export interface MultiChatRequest {
  influencers: Array<{
    influencer_id: string
    influencer_model_repo: string
  }>
  message: string
}

export interface MultiChatResponse {
  results: Array<{
    influencer_id: string
    response: string
  }>
}


export class ModelService {
  /**
   * 사용자별 AI 인플루언서 목록 조회
   */
  static async getInfluencers(params?: {
    skip?: number
    limit?: number
  }): Promise<AIInfluencer[]> {
    const searchParams = new URLSearchParams()
    
    if (params?.skip) searchParams.set('skip', params.skip.toString())
    if (params?.limit) searchParams.set('limit', params.limit.toString())

    const query = searchParams.toString()
    const endpoint = `/api/v1/influencers/${query ? `?${query}` : ''}`
    
    return await apiClient.get<AIInfluencer[]>(endpoint)
  }

  /**
   * 특정 AI 인플루언서 조회
   */
  static async getInfluencer(influencerId: string): Promise<AIInfluencer> {
    return await apiClient.get<AIInfluencer>(`/api/v1/influencers/${influencerId}`)
  }

  /**
   * AI 인플루언서 생성
   */
  static async createInfluencer(data: CreateInfluencerRequest): Promise<AIInfluencer> {
    return await apiClient.post<AIInfluencer>('/api/v1/influencers', data)
  }

  /**
   * AI 인플루언서 업데이트
   */
  static async updateInfluencer(influencerId: string, data: UpdateInfluencerRequest): Promise<AIInfluencer> {
    return await apiClient.put<AIInfluencer>(`/api/v1/influencers/${influencerId}`, data)
  }

  /**
   * AI 인플루언서 삭제
   */
  static async deleteInfluencer(influencerId: string): Promise<void> {
    await apiClient.delete(`/api/v1/influencers/${influencerId}`)
  }

  /**
   * 스타일 프리셋 목록 조회
   */
  static async getStylePresets(params?: {
    skip?: number
    limit?: number
  }): Promise<StylePreset[]> {
    const searchParams = new URLSearchParams()
    
    if (params?.skip) searchParams.set('skip', params.skip.toString())
    if (params?.limit) searchParams.set('limit', params.limit.toString())

    const query = searchParams.toString()
    const endpoint = `/api/v1/influencers/style-presets${query ? `?${query}` : ''}`
    
    return await apiClient.get<StylePreset[]>(endpoint)
  }

  /**
   * MBTI 목록 조회
   */
  static async getMBTIList(): Promise<ModelMBTI[]> {
    return await apiClient.get<ModelMBTI[]>('/api/v1/influencers/mbti')
  }

  /**
   * 멀티 채팅 (모델 테스트)
   */
  static async multiChat(request: MultiChatRequest): Promise<MultiChatResponse> {
    return await apiClient.post<MultiChatResponse>('/api/v1/model-test/multi-chat', request)
  }

}

export default ModelService