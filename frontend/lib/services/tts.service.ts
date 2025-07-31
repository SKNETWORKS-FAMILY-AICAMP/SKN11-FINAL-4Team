import { tokenUtils } from '@/lib/auth'

export interface TTSRequest {
  text: string
  influencer_id: string
  language?: string
  speed?: number
  pitch?: number
}

export interface TTSResponse {
  audio_url: string
  duration?: number
  format?: string
}

export class TTSService {
  private static baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

  /**
   * 인플루언서 음성으로 텍스트를 음성으로 변환
   */
  static async generateSpeech(request: TTSRequest): Promise<TTSResponse> {
    const token = tokenUtils.getToken()
    if (!token) {
      throw new Error('인증이 필요합니다.')
    }

    const response = await fetch(`${this.baseUrl}/api/v1/tts/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        text: request.text,
        influencer_id: request.influencer_id,
        language: request.language || 'ko',
        speed: request.speed || 1.0,
        pitch: request.pitch || 1.0,
      }),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.message || '음성 생성에 실패했습니다.')
    }

    return response.json()
  }

  /**
   * 음성 파일 스트림 가져오기
   */
  static async getAudioStream(audioUrl: string): Promise<Blob> {
    const token = tokenUtils.getToken()
    if (!token) {
      throw new Error('인증이 필요합니다.')
    }

    // 상대 경로인 경우 전체 URL로 변환
    const fullUrl = audioUrl.startsWith('http') ? audioUrl : `${this.baseUrl}${audioUrl}`

    const response = await fetch(fullUrl, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    })

    if (!response.ok) {
      throw new Error('음성 파일을 가져오는데 실패했습니다.')
    }

    return response.blob()
  }

  /**
   * 인플루언서의 기본 음성 샘플 가져오기
   */
  static async getInfluencerVoiceSample(influencerId: string): Promise<string | null> {
    const token = tokenUtils.getToken()
    if (!token) {
      throw new Error('인증이 필요합니다.')
    }

    try {
      const response = await fetch(`${this.baseUrl}/api/v1/influencers/${influencerId}/voice-sample`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })

      if (!response.ok) {
        return null
      }

      const data = await response.json()
      return data.voice_sample_url || null
    } catch (error) {
      console.error('음성 샘플을 가져오는데 실패했습니다:', error)
      return null
    }
  }
}