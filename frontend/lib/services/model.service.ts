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
  system_prompt?: string
  // Instagram 연동 정보
  instagram_id?: string
  instagram_username?: string
  instagram_account_type?: string
  instagram_is_active?: boolean
  instagram_connected_at?: string
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
  // 추가 컬럼
  mbti_id?: number
  system_prompt?: string
  influencer_description?: string
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
  style_preset_id?: string  // 선택적 필드로 변경 - 빈 문자열이나 undefined면 새로운 프리셋 생성
  mbti_id?: number
  influencer_name: string
  image_url?: string
  influencer_data_url?: string
  learning_status: number
  influencer_model_repo: string
  chatbot_option: boolean
  
  // 프리셋 자동 생성을 위한 추가 필드들
  personality?: string  // 성격
  tone?: string         // 말투
  model_type?: string   // 모델 타입
  mbti?: string         // MBTI
  gender?: string       // 성별
  age?: string          // 나이
  hair_style?: string   // 헤어스타일
  mood?: string         // 분위기/스타일
  system_prompt?: string // 시스템 프롬프트
  
  // 말투 정보 필드들
  tone_type?: string    // "system" 또는 "custom"
  tone_data?: string    // 선택된 시스템 프롬프트 또는 사용자 입력 데이터
}

export interface UpdateInfluencerRequest {
  style_preset_id?: string
  mbti_id?: number
  influencer_name?: string
  influencer_description?: string
  image_url?: string
  influencer_data_url?: string
  learning_status?: number
  influencer_model_repo?: string
  chatbot_option?: boolean
  system_prompt?: string
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

export interface ToneGenerationRequest {
  personality: string
  name?: string
  description?: string
  mbti?: string
  gender?: string
  age?: string
}

export interface ConversationExample {
  title: string
  example: string
  tone: string
  hashtags: string
  system_prompt: string
}

export interface ToneGenerationResponse {
  personality: string
  character_info: string
  question: string
  conversation_examples: ConversationExample[]
  generated_at: string
  regenerated?: boolean
}

export interface HuggingFaceToken {
  hf_manage_id: string
  hf_token_nickname: string
  hf_user_name: string
  group_id?: number
  created_at?: string
  updated_at?: string
}

export interface APIKeyResponse {
  influencer_id: string
  api_key: string
  message: string
}

export interface APIKeyInfo {
  influencer_id: string
  api_key: string
  created_at: string
  updated_at: string
}

export interface ChatbotRequest {
  message: string
  session_id?: string
}

export interface ChatbotResponse {
  response: string
  session_id: string
  influencer_name: string
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
    const endpoint = `/api/v1/influencers${query ? `?${query}` : ''}`
    
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
   * AI 인플루언서 생성 (이미지 포함)
   */
  static async createInfluencerWithImage(formData: FormData): Promise<AIInfluencer> {
    return await apiClient.post<AIInfluencer>('/api/v1/influencers/with-image', formData)
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
   * 스타일 프리셋 목록 조회 (MBTI 정보 포함)
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
   * 단일 스타일 프리셋 조회
   */
  static async getStylePresetById(stylePresetId: string): Promise<StylePreset> {
    return await apiClient.get<StylePreset>(`/api/v1/influencers/style-presets/${stylePresetId}`)
  }

  /**
   * 허깅페이스 토큰 목록 조회 (그룹별)
   */
  static async getHuggingFaceTokens(groupId: number): Promise<HuggingFaceToken[]> {
    const response = await apiClient.get<{tokens: HuggingFaceToken[]}>(`/api/v1/hf-tokens/group/${groupId}`)
    return response.tokens || []
  }

  /**
   * Instagram 계정 연결
   */
  static async connectInstagram(influencerId: string, data: {
    code: string
    redirect_uri: string
  }): Promise<any> {
    return await apiClient.post(`/api/v1/influencers/${influencerId}/instagram/connect`, data)
  }

  /**
   * Instagram 계정 연결 해제
   */
  static async disconnectInstagram(influencerId: string): Promise<any> {
    return await apiClient.delete(`/api/v1/influencers/${influencerId}/instagram/disconnect`)
  }

  /**
   * Instagram 연결 상태 확인
   */
  static async getInstagramStatus(influencerId: string): Promise<{
    is_connected: boolean;
    instagram_id?: string;
    instagram_page_id?: string;
    instagram_username?: string;
    instagram_account_type?: string;
    connected_at?: string;
    token_expires_at?: string;
    token_expired?: boolean;
    instagram_info?: {
      id: string;
      username: string;
      account_type: string;
      name?: string;
      biography?: string;
      followers_count?: number;
      follows_count?: number;
      media_count?: number;
      profile_picture_url?: string;
      website?: string;
    };
  }> {
    return await apiClient.get(`/api/v1/influencers/${influencerId}/instagram/status`)
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
    return await apiClient.post<MultiChatResponse>('/api/v1/model-test/multi-chat', request, {
      timeout: 300000  // 5분으로 증가
    })
  }

  /**
   * 말투 생성
   */
  static async generateTones(request: ToneGenerationRequest): Promise<ToneGenerationResponse> {
    return await apiClient.post<ToneGenerationResponse>('/api/v1/influencers/generate-tones', request, {
      timeout: 90000 // 1분 타임아웃
    })
  }

  /**
   * 말투 재생성
   */
  static async regenerateTones(request: ToneGenerationRequest): Promise<ToneGenerationResponse> {
    return await apiClient.post<ToneGenerationResponse>('/api/v1/influencers/regenerate-tones', request, {
      timeout: 90000 // 1분 타임아웃
    })
  }

  /**
   * API 키 생성 또는 업데이트
   */
  static async generateApiKey(influencerId: string): Promise<APIKeyResponse> {
    try {
      const result = await apiClient.post<APIKeyResponse>(`/api/v1/influencers/${influencerId}/api-key/generate`)
      return result
    } catch (error) {
      throw error
    }
  }

  /**
   * API 키 조회
   */
  static async getApiKey(influencerId: string): Promise<APIKeyInfo> {
    try {
      const result = await apiClient.get<APIKeyInfo>(`/api/v1/influencers/${influencerId}/api-key`)
      return result
    } catch (error) {
      throw error
    }
  }

  /**
   * API 키로 챗봇 호출
   */
  static async callChatbot(
    apiKey: string, 
    request: ChatbotRequest
  ): Promise<ChatbotResponse> {
    return await apiClient.post<ChatbotResponse>(
      '/api/v1/chat/chatbot',
      request,
      {
        headers: {
          'Authorization': `Bearer ${apiKey}`
        }
      }
    )
  }

  /**
   * API 키로 스트리밍 챗봇 호출
   */
  static async callChatbotStream(
    apiKey: string, 
    request: ChatbotRequest,
    onToken: (token: string) => void,
    onComplete: () => void,
    onError: (error: string) => void
  ): Promise<void> {
    try {
      const response = await fetch('/api/chat/chatbot/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify(request)
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.error || '스트리밍 요청 실패')
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('스트리밍 응답을 읽을 수 없습니다')
      }

      const decoder = new TextDecoder()
      
      while (true) {
        const { done, value } = await reader.read()
        
        if (done) {
          onComplete()
          break
        }

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n')
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              
              if (data.text) {
                onToken(data.text)
              } else if (data.done) {
                onComplete()
                return
              } else if (data.error) {
                onError(data.error)
                return
              }
            } catch (e) {
              // 필요시 에러 핸들링만 남김
            }
          }
        }
      }
    } catch (error) {
      onError(error instanceof Error ? error.message : '스트리밍 요청 중 오류가 발생했습니다')
    }
  }

}

export default ModelService