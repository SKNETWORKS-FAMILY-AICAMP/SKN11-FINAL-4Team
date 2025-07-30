import { useEffect, useRef, useState, useCallback } from 'react'
import { useToast } from '@/hooks/use-toast'
import { tokenUtils } from '@/lib/auth'

interface WebSocketOptions {
  onMessage?: (message: any) => void
  onSessionStatus?: (status: any) => void
  onGenerationProgress?: (progress: any) => void
  onGenerationComplete?: (data: any) => void
  onError?: (error: any) => void
  onConnect?: () => void
  onDisconnect?: () => void
}

export function useWebSocket(options: WebSocketOptions = {}) {
  const { toast } = useToast()
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const isConnectingRef = useRef(false)
  const [isConnected, setIsConnected] = useState(false)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)
  const optionsRef = useRef(options)

  // Options를 ref에 저장하여 최신 상태 유지
  useEffect(() => {
    optionsRef.current = options
  }, [options])

  const cleanup = useCallback(() => {
    // 재연결 타이머 정리
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    // WebSocket 연결 종료
    if (wsRef.current) {
      wsRef.current.close(1000, 'Cleanup')
      wsRef.current = null
    }

    isConnectingRef.current = false
    setIsConnected(false)
  }, [])

  const connect = useCallback(() => {
    // 이미 연결 중이거나 연결되어 있으면 무시
    if (isConnectingRef.current) {
      console.log('WebSocket connection already in progress, skipping...')
      return
    }
    
    if (wsRef.current) {
      const state = wsRef.current.readyState
      if (state === WebSocket.CONNECTING || state === WebSocket.OPEN) {
        console.log('WebSocket already connected or connecting, skipping...')
        return
      }
    }

    const accessToken = tokenUtils.getToken()
    if (!accessToken) {
      console.error('No access token available for WebSocket connection')
      return
    }

    isConnectingRef.current = true

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
      const wsProtocol = backendUrl.startsWith('https') ? 'wss:' : 'ws:'
      const wsHost = backendUrl.replace(/^https?:\/\//, '')
      const wsUrl = `${wsProtocol}//${wsHost}/api/v1/image-generation/ws?token=${accessToken}`

      console.log('Attempting WebSocket connection to:', wsUrl.replace(accessToken, '[REDACTED]'))
      
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('WebSocket connected')
        isConnectingRef.current = false
        setIsConnected(true)
        setReconnectAttempts(0)
        optionsRef.current.onConnect?.()
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          
          // 일반 메시지 핸들러
          optionsRef.current.onMessage?.(message)

          // 특정 타입별 핸들러
          console.log('WebSocket message type:', message.type, 'data:', message.data)
          
          switch (message.type) {
            case 'session_status':
            case 'session_created':
              optionsRef.current.onSessionStatus?.(message.data)
              break
            case 'generation_progress':
              optionsRef.current.onGenerationProgress?.(message.data)
              break
            case 'generation_complete':
              console.log('🎨 Generation complete message received in useWebSocket')
              optionsRef.current.onGenerationComplete?.(message.data)
              break
            case 'error':
              optionsRef.current.onError?.(message.data)
              break
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      ws.onerror = (event) => {
        console.error('WebSocket error event:', event)
        console.error('WebSocket readyState:', ws.readyState)
        console.error('WebSocket url:', ws.url)
        isConnectingRef.current = false
        setIsConnected(false)
      }

      ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason)
        isConnectingRef.current = false
        setIsConnected(false)
        wsRef.current = null
        optionsRef.current.onDisconnect?.()

        // 인증 실패가 아닌 경우에만 재연결 시도
        if (event.code !== 1008 && !event.reason?.includes('403') && reconnectAttempts < 3) {
          setReconnectAttempts(prev => prev + 1)
          
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log(`WebSocket reconnect attempt ${reconnectAttempts + 1}/3`)
            connect()
          }, 5000)
        } else if (event.code === 1008 || event.reason?.includes('403')) {
          toast({
            title: "인증 오류",
            description: '다시 로그인해주세요.',
            variant: "destructive",
            duration: 5000,
          })
        } else if (reconnectAttempts >= 3) {
          toast({
            title: "연결 실패",
            description: '서버 연결에 실패했습니다. 페이지를 새로고침해주세요.',
            variant: "destructive",
            duration: 5000,
          })
        }
      }

      wsRef.current = ws
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
      isConnectingRef.current = false
      setIsConnected(false)
    }
  }, [reconnectAttempts, toast])

  const send = useCallback((data: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
      return true
    }
    return false
  }, [])

  // 초기 연결
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      const accessToken = tokenUtils.getToken()
      if (accessToken) {
        connect()
      }
    }, 100) // 약간의 딜레이를 주어 중복 실행 방지

    return () => {
      clearTimeout(timeoutId)
      cleanup()
    }
  }, []) // 빈 의존성 배열로 한 번만 실행

  // 토큰 변경 감지
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'access_token') {
        cleanup()
        if (e.newValue) {
          setTimeout(connect, 100) // 약간의 딜레이 후 재연결
        }
      }
    }

    window.addEventListener('storage', handleStorageChange)
    return () => window.removeEventListener('storage', handleStorageChange)
  }, [cleanup, connect])

  return {
    isConnected,
    send,
    reconnect: connect,
    disconnect: cleanup,
  }
}