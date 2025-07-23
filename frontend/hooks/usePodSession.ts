/**
 * Pod 세션 사전 로더 훅
 * 
 * 요구사항에 따라 이미지 생성 페이지 진입시 자동으로 RunPod 세션을 시작하고
 * 15분 입력 대기, 10분 이미지 생성 타임리밋을 관리
 * 
 */

import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '@/hooks/use-auth'

interface PodSessionStatus {
  success: boolean
  session_id: string
  session_status: 'input_waiting' | 'processing' | 'idle' | 'expired'
  pod_status: 'starting' | 'ready' | 'processing' | 'terminating'
  pod_endpoint_url?: string
  remaining_input_time?: number  // 초 단위
  remaining_processing_time?: number  // 초 단위
  total_generations: number
  message: string
}

interface UsePodSessionReturn {
  sessionStatus: PodSessionStatus | null
  isLoading: boolean
  error: string | null
  startSession: () => Promise<void>
  extendTimeout: () => Promise<void>
  terminateSession: () => Promise<void>
  refreshStatus: () => Promise<void>
  remainingTimeFormatted: string
}

export function usePodSession(): UsePodSessionReturn {
  const { user, isAuthenticated } = useAuth()
  const [sessionStatus, setSessionStatus] = useState<PodSessionStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 세션 시작 (페이지 진입시 자동 호출)
  const startSession = useCallback(async () => {
    if (!isAuthenticated || !user) {
      setError('로그인이 필요합니다.')
      return
    }

    try {
      setIsLoading(true)
      setError(null)

      const response = await fetch('/api/v1/sessions/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          page_type: 'image_generator'
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '세션 시작에 실패했습니다.')
      }

      const data = await response.json()
      setSessionStatus(data)
      
      console.log('Pod 세션 시작됨:', data.message)
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다.'
      setError(errorMessage)
      console.error('세션 시작 실패:', err)
    } finally {
      setIsLoading(false)
    }
  }, [isAuthenticated, user])

  // 세션 상태 조회
  const refreshStatus = useCallback(async () => {
    if (!isAuthenticated || !user) return

    try {
      const response = await fetch('/api/v1/sessions/status', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      })

      if (response.ok) {
        const data = await response.json()
        setSessionStatus(data)
      } else if (response.status === 404) {
        // 활성 세션이 없으면 자동으로 새 세션 시작
        await startSession()
      }
    } catch (err) {
      console.error('세션 상태 조회 실패:', err)
    }
  }, [isAuthenticated, user, startSession])

  // 타임아웃 연장 (재생성시)
  const extendTimeout = useCallback(async () => {
    if (!isAuthenticated || !user) return

    try {
      const response = await fetch('/api/v1/sessions/extend-timeout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          timeout_type: 'processing'
        })
      })

      if (response.ok) {
        const data = await response.json()
        setSessionStatus(data)
        console.log('타임아웃 연장됨')
      }
    } catch (err) {
      console.error('타임아웃 연장 실패:', err)
    }
  }, [isAuthenticated, user])

  // 세션 강제 종료
  const terminateSession = useCallback(async () => {
    if (!isAuthenticated || !user) return

    try {
      const response = await fetch('/api/v1/sessions/terminate', {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      })

      if (response.ok) {
        setSessionStatus(null)
        console.log('세션이 종료되었습니다.')
      }
    } catch (err) {
      console.error('세션 종료 실패:', err)
    }
  }, [isAuthenticated, user])

  // 남은 시간 포맷팅
  const remainingTimeFormatted = useCallback(() => {
    if (!sessionStatus) return ''

    const { session_status, remaining_input_time, remaining_processing_time } = sessionStatus

    if (session_status === 'input_waiting' && remaining_input_time) {
      const minutes = Math.floor(remaining_input_time / 60)
      const seconds = remaining_input_time % 60
      return `입력 대기: ${minutes}:${seconds.toString().padStart(2, '0')}`
    }

    if (session_status === 'processing' && remaining_processing_time) {
      const minutes = Math.floor(remaining_processing_time / 60)
      const seconds = remaining_processing_time % 60
      return `처리 중: ${minutes}:${seconds.toString().padStart(2, '0')}`
    }

    return ''
  }, [sessionStatus])

  // 페이지 진입시 자동으로 세션 시작
  useEffect(() => {
    if (isAuthenticated && user && !sessionStatus && !isLoading) {
      startSession()
    }
  }, [isAuthenticated, user, sessionStatus, isLoading, startSession])

  // 주기적으로 세션 상태 업데이트 (30초마다)
  useEffect(() => {
    if (!sessionStatus || !isAuthenticated) return

    const interval = setInterval(() => {
      refreshStatus()
    }, 30000) // 30초마다 상태 체크

    return () => clearInterval(interval)
  }, [sessionStatus, isAuthenticated, refreshStatus])

  // 세션 만료 체크 및 자동 정리
  useEffect(() => {
    if (!sessionStatus) return

    const { session_status, remaining_input_time, remaining_processing_time } = sessionStatus

    if (session_status === 'input_waiting' && remaining_input_time === 0) {
      console.log('입력 타임아웃으로 세션이 만료되었습니다.')
      setSessionStatus(null)
      setError('15분 입력 대기 시간이 만료되었습니다. 페이지를 새로고침해주세요.')
    }

    if (session_status === 'processing' && remaining_processing_time === 0) {
      console.log('처리 타임아웃으로 세션이 만료되었습니다.')
      setSessionStatus(null)
      setError('10분 처리 시간이 만료되었습니다. 새로운 세션이 시작됩니다.')
      // 자동으로 새 세션 시작
      setTimeout(() => {
        setError(null)
        startSession()
      }, 2000)
    }
  }, [sessionStatus, startSession])

  return {
    sessionStatus,
    isLoading,
    error,
    startSession,
    extendTimeout,
    terminateSession,
    refreshStatus,
    remainingTimeFormatted: remainingTimeFormatted()
  }
}
