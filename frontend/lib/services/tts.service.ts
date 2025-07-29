import { apiClient } from '../api'

export interface StreamingVoiceRequest {
  texts: string[]
  influencer_id: string
  chunk_schedule?: number[]
  chunk_overlap?: number
}

export interface TTSChunk {
  type: 'boundary' | 'audio'
  data: string
  shape?: number[]
  index: number
}

export interface StreamEvent {
  event: 'start' | 'chunk' | 'complete' | 'error'
  influencer_id?: string
  message?: string
  chunk?: TTSChunk
  sample_rate?: number
  error?: string
}

export class TTSService {
  /**
   * 텍스트를 음성으로 스트리밍 변환
   * @param request 스트리밍 요청 데이터
   * @param onChunk 청크 수신 콜백
   * @param onError 에러 콜백
   * @returns AbortController (취소용)
   */
  static async streamVoice(
    request: StreamingVoiceRequest,
    onChunk: (event: StreamEvent) => void,
    onError?: (error: Error) => void
  ): Promise<AbortController> {
    const abortController = new AbortController()
    
    try {
      // apiClient의 stream 메서드 사용
      const response = await apiClient.stream('/api/v1/tts/stream_voice', request, {
        signal: abortController.signal
      })

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('스트림을 읽을 수 없습니다')
      }

      // SSE 스트림 읽기
      const readStream = async () => {
        let buffer = ''
        
        try {
          while (true) {
            const { done, value } = await reader.read()
            if (done) break

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6))
                  onChunk(data as StreamEvent)
                } catch (e) {
                  console.error('SSE 데이터 파싱 오류:', e)
                }
              }
            }
          }
        } catch (error) {
          if (error.name !== 'AbortError') {
            throw error
          }
        }
      }

      // 비동기로 스트림 읽기 시작
      readStream().catch(error => {
        if (onError && error.name !== 'AbortError') {
          onError(error)
        }
      })

      return abortController
      
    } catch (error) {
      if (onError) {
        onError(error as Error)
      }
      throw error
    }
  }

  /**
   * 문장 분할 유틸리티
   */
  static splitIntoSentences(text: string): string[] {
    // 한국어 문장 종결 처리를 위한 정규표현식
    const sentences = text.match(/[^.!?]+[.!?]+/g) || [text]
    return sentences.map(s => s.trim()).filter(s => s.length > 0)
  }
}

export default TTSService