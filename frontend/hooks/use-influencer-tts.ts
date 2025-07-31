import { useState, useCallback, useRef, useEffect } from 'react'
import { TTSService, TTSRequest } from '@/lib/services/tts.service'

export interface InfluencerTTSOptions {
  influencerId: string
  language?: string
  speed?: number
  pitch?: number
  volume?: number
}

export type TTSStatus = 'idle' | 'generating' | 'playing' | 'paused' | 'error'

export const useInfluencerTTS = (options: InfluencerTTSOptions) => {
  const [status, setStatus] = useState<TTSStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [currentMessageId, setCurrentMessageId] = useState<string | null>(null)
  
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const audioUrlsCache = useRef<Map<string, string>>(new Map())

  // Audio 요소 초기화
  useEffect(() => {
    audioRef.current = new Audio()
    
    // 이벤트 리스너 설정
    const audio = audioRef.current
    
    audio.addEventListener('play', () => {
      setStatus('playing')
    })
    
    audio.addEventListener('pause', () => {
      setStatus('paused')
    })
    
    audio.addEventListener('ended', () => {
      setStatus('idle')
      setCurrentMessageId(null)
    })
    
    audio.addEventListener('error', (e) => {
      setStatus('error')
      setError('오디오 재생 중 오류가 발생했습니다.')
      console.error('Audio playback error:', e)
    })

    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.src = ''
      }
    }
  }, [])

  // 텍스트를 음성으로 변환하고 재생
  const speak = useCallback(async (messageId: string, text: string) => {
    if (!text || !options.influencerId) {
      setError('텍스트 또는 인플루언서 ID가 없습니다.')
      return
    }

    try {
      setError(null)
      setCurrentMessageId(messageId)
      
      // 캐시 확인
      const cachedUrl = audioUrlsCache.current.get(messageId)
      if (cachedUrl) {
        // 캐시된 오디오 재생
        if (audioRef.current) {
          audioRef.current.src = cachedUrl
          audioRef.current.volume = options.volume || 1
          await audioRef.current.play()
        }
        return
      }

      // 새로운 음성 생성
      setStatus('generating')
      setIsLoading(true)

      const request: TTSRequest = {
        text,
        influencer_id: options.influencerId,
        language: options.language,
        speed: options.speed,
        pitch: options.pitch,
      }

      const response = await TTSService.generateSpeech(request)
      
      // 오디오 URL 캐싱
      audioUrlsCache.current.set(messageId, response.audio_url)
      
      // 오디오 재생
      if (audioRef.current) {
        audioRef.current.src = response.audio_url
        audioRef.current.volume = options.volume || 1
        await audioRef.current.play()
      }
      
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : '음성 생성 중 오류가 발생했습니다.')
      console.error('TTS Error:', err)
    } finally {
      setIsLoading(false)
    }
  }, [options])

  // 재생/일시정지 토글
  const togglePlayPause = useCallback(() => {
    if (!audioRef.current) return

    if (audioRef.current.paused) {
      audioRef.current.play()
    } else {
      audioRef.current.pause()
    }
  }, [])

  // 정지
  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
      setStatus('idle')
      setCurrentMessageId(null)
    }
  }, [])

  // 볼륨 조정
  const setVolume = useCallback((volume: number) => {
    if (audioRef.current) {
      audioRef.current.volume = Math.max(0, Math.min(1, volume))
    }
  }, [])

  // 재생 속도 조정
  const setPlaybackRate = useCallback((rate: number) => {
    if (audioRef.current) {
      audioRef.current.playbackRate = Math.max(0.5, Math.min(2, rate))
    }
  }, [])

  // 캐시 클리어
  const clearCache = useCallback(() => {
    audioUrlsCache.current.clear()
  }, [])

  return {
    // 상태
    status,
    error,
    isLoading,
    currentMessageId,
    
    // 제어 함수
    speak,
    togglePlayPause,
    stop,
    setVolume,
    setPlaybackRate,
    clearCache,
    
    // 오디오 정보
    duration: audioRef.current?.duration || 0,
    currentTime: audioRef.current?.currentTime || 0,
  }
}