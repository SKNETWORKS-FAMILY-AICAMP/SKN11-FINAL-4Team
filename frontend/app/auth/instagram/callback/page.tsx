"use client"

import { useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { CheckCircle, AlertCircle, Loader2, Instagram } from "lucide-react"

export default function InstagramCallbackPage() {
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('Instagram 인증을 처리하고 있습니다...')

  useEffect(() => {
    const handleCallback = () => {
      try {
        const code = searchParams.get('code')
        const error = searchParams.get('error')
        const state = searchParams.get('state') // 모델 ID
        
        if (error) {
          setStatus('error')
          setMessage('Instagram 연동이 취소되었거나 오류가 발생했습니다.')
          
          // 부모 창에 에러 메시지 전송
          if (window.opener) {
            window.opener.postMessage({
              type: 'INSTAGRAM_AUTH_ERROR',
              error: error,
              state: state
            }, window.location.origin)
          }
          
          // 3초 후 창 닫기
          setTimeout(() => {
            window.close()
          }, 3000)
          return
        }

        if (!code) {
          setStatus('error')
          setMessage('Instagram 인증 코드를 받지 못했습니다.')
          
          // 부모 창에 에러 메시지 전송
          if (window.opener) {
            window.opener.postMessage({
              type: 'INSTAGRAM_AUTH_ERROR',
              error: 'No authorization code received',
              state: state
            }, window.location.origin)
          }
          
          // 3초 후 창 닫기
          setTimeout(() => {
            window.close()
          }, 3000)
          return
        }

        // 성공적으로 code를 받은 경우
        setStatus('success')
        setMessage('Instagram 인증이 완료되었습니다! 계정을 연동하고 있습니다...')
        
        // 부모 창에 성공 메시지 및 code 전송
        if (window.opener) {
          window.opener.postMessage({
            type: 'INSTAGRAM_AUTH_SUCCESS',
            code: code,
            state: state
          }, window.location.origin)
        }
        
        // 1초 후 창 닫기
        setTimeout(() => {
          window.close()
        }, 1000)
        
      } catch (error) {
        console.error('Instagram 콜백 처리 오류:', error)
        setStatus('error')
        setMessage('처리 중 오류가 발생했습니다.')
        
        // 부모 창에 에러 메시지 전송
        if (window.opener) {
          window.opener.postMessage({
            type: 'INSTAGRAM_AUTH_ERROR',
            error: 'Processing error',
            state: searchParams.get('state')
          }, window.location.origin)
        }
        
        // 3초 후 창 닫기
        setTimeout(() => {
          window.close()
        }, 3000)
      }
    }

    handleCallback()
  }, [searchParams])

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            {status === 'loading' && <Loader2 className="h-12 w-12 text-blue-500 animate-spin" />}
            {status === 'success' && <CheckCircle className="h-12 w-12 text-green-500" />}
            {status === 'error' && <AlertCircle className="h-12 w-12 text-red-500" />}
          </div>
          <CardTitle className="flex items-center justify-center space-x-2">
            <Instagram className="h-5 w-5 text-pink-600" />
            <span>Instagram 인증</span>
          </CardTitle>
          <CardDescription>
            {status === 'loading' && 'Instagram 인증을 처리하고 있습니다...'}
            {status === 'success' && '인증이 완료되었습니다!'}
            {status === 'error' && '인증 중 오류가 발생했습니다'}
          </CardDescription>
        </CardHeader>
        
        <CardContent>
          <div className="text-center">
            <p className="text-sm text-gray-600">{message}</p>
            
            {status === 'success' && (
              <p className="text-xs text-gray-500 mt-3">
                잠시 후 이 창이 자동으로 닫힙니다...
              </p>
            )}
            
            {status === 'error' && (
              <p className="text-xs text-gray-500 mt-3">
                3초 후 이 창이 자동으로 닫힙니다...
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}