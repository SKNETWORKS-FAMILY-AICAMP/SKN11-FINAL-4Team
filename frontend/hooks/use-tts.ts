import { useState, useEffect, useRef, useCallback } from 'react'

export interface TTSOptions {
  lang?: string
  voice?: SpeechSynthesisVoice | null
  rate?: number
  pitch?: number
  volume?: number
}

export type TTSStatus = 'idle' | 'speaking' | 'paused' | 'loading'

export const useTTS = (defaultOptions?: TTSOptions) => {
  const [isSupported, setIsSupported] = useState(false)
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([])
  const [status, setStatus] = useState<TTSStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)
  const optionsRef = useRef<TTSOptions>({
    lang: 'ko-KR',
    voice: null,
    rate: 1,
    pitch: 1,
    volume: 1,
    ...defaultOptions
  })

  // TTS 지원 여부 확인
  useEffect(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      setIsSupported(true)
      
      // 음성 목록 로드
      const loadVoices = () => {
        const availableVoices = window.speechSynthesis.getVoices()
        setVoices(availableVoices)
        
        // 기본 한국어 음성 설정
        if (!optionsRef.current.voice && availableVoices.length > 0) {
          const koreanVoice = availableVoices.find(voice => voice.lang.startsWith('ko'))
          if (koreanVoice) {
            optionsRef.current.voice = koreanVoice
          }
        }
      }

      loadVoices()
      
      // 일부 브라우저에서는 음성 목록이 비동기로 로드됨
      if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = loadVoices
      }
    }
  }, [])

  // 텍스트 음성 변환
  const speak = useCallback((text: string, options?: TTSOptions) => {
    if (!isSupported || !text) {
      setError('TTS가 지원되지 않거나 텍스트가 없습니다.')
      return
    }

    try {
      // 기존 음성 중지
      window.speechSynthesis.cancel()
      
      // 새 발화 생성
      const utterance = new SpeechSynthesisUtterance(text)
      const currentOptions = { ...optionsRef.current, ...options }
      
      // 옵션 설정
      utterance.lang = currentOptions.lang || 'ko-KR'
      utterance.rate = currentOptions.rate || 1
      utterance.pitch = currentOptions.pitch || 1
      utterance.volume = currentOptions.volume || 1
      
      if (currentOptions.voice) {
        utterance.voice = currentOptions.voice
      }
      
      // 이벤트 핸들러 설정
      utterance.onstart = () => {
        setStatus('speaking')
        setError(null)
      }
      
      utterance.onend = () => {
        setStatus('idle')
      }
      
      utterance.onerror = (event) => {
        setStatus('idle')
        setError(`TTS 오류: ${event.error}`)
        console.error('TTS Error:', event)
      }
      
      utterance.onpause = () => {
        setStatus('paused')
      }
      
      utterance.onresume = () => {
        setStatus('speaking')
      }
      
      utteranceRef.current = utterance
      window.speechSynthesis.speak(utterance)
      
    } catch (err) {
      setError(`TTS 실행 중 오류: ${err instanceof Error ? err.message : '알 수 없는 오류'}`)
      setStatus('idle')
    }
  }, [isSupported])

  // 일시정지
  const pause = useCallback(() => {
    if (window.speechSynthesis.speaking && !window.speechSynthesis.paused) {
      window.speechSynthesis.pause()
    }
  }, [])

  // 재개
  const resume = useCallback(() => {
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume()
    }
  }, [])

  // 정지
  const stop = useCallback(() => {
    window.speechSynthesis.cancel()
    setStatus('idle')
  }, [])

  // 옵션 업데이트
  const updateOptions = useCallback((newOptions: Partial<TTSOptions>) => {
    optionsRef.current = { ...optionsRef.current, ...newOptions }
  }, [])

  // 특정 언어의 음성 목록 가져오기
  const getVoicesByLanguage = useCallback((lang: string) => {
    return voices.filter(voice => voice.lang.startsWith(lang))
  }, [voices])

  return {
    // 상태
    isSupported,
    voices,
    status,
    error,
    
    // 제어 함수
    speak,
    pause,
    resume,
    stop,
    
    // 유틸리티
    updateOptions,
    getVoicesByLanguage,
    
    // 현재 옵션
    currentOptions: optionsRef.current
  }
}