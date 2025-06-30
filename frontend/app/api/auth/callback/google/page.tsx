"use client"

import { useEffect } from 'react'
import { useSearchParams } from 'next/navigation'

export default function GoogleCallback() {
  const searchParams = useSearchParams()

  useEffect(() => {
    const code = searchParams.get('code')
    const error = searchParams.get('error')
    const state = searchParams.get('state')

    if (typeof window !== 'undefined' && window.opener) {
      if (error) {
        // 에러 발생 시 부모 창에 에러 메시지 전달
        window.opener.postMessage({
          type: 'GOOGLE_AUTH_ERROR',
          error: error || 'Google authentication failed'
        }, window.location.origin)
      } else if (code) {
        // 성공 시 부모 창에 authorization code 전달
        window.opener.postMessage({
          type: 'GOOGLE_AUTH_SUCCESS',
          code: code,
          state: state
        }, window.location.origin)
      } else {
        // 코드가 없는 경우
        window.opener.postMessage({
          type: 'GOOGLE_AUTH_ERROR',
          error: 'No authorization code received'
        }, window.location.origin)
      }
      
      // 팝업 창 닫기
      window.close()
    }
  }, [searchParams])

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-4 text-gray-600">Google 로그인 처리 중...</p>
      </div>
    </div>
  )
}