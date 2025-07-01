"use client"

import { useEffect, useState } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { BackendAuthService } from '@/lib/backend-auth'
import { useAuth } from '@/hooks/use-auth'

export default function GoogleCallback() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { login } = useAuth()
  const [status, setStatus] = useState<'processing' | 'success' | 'error'>('processing')
  const [errorMessage, setErrorMessage] = useState<string>('')

  useEffect(() => {
    const processAuth = async () => {
      console.log('Google 콜백 처리 시작')
      const code = searchParams.get('code')
      const error = searchParams.get('error')
      const state = searchParams.get('state')
      const returnUrl = localStorage.getItem('social_auth_return_url') || '/'

      console.log('콜백 파라미터:', { code: !!code, error, state, returnUrl })

      if (error) {
        console.error('Google OAuth 에러:', error)
        setStatus('error')
        setErrorMessage(error || 'Google authentication failed')
        setTimeout(() => {
          router.push(returnUrl)
        }, 3000)
        return
      }

      if (!code) {
        console.error('Authorization code가 없음')
        setStatus('error')
        setErrorMessage('No authorization code received')
        setTimeout(() => {
          router.push(returnUrl)
        }, 3000)
        return
      }

      try {
        console.log('백엔드 API 호출 시작')
        const redirectUri = process.env.NEXT_PUBLIC_GOOGLE_REDIRECT_URI || `${window.location.origin}/api/auth/callback/google`
        console.log('사용할 redirect URI:', redirectUri)
        
        // 백엔드에 authorization code 전달
        const backendResponse = await BackendAuthService.exchangeCodeForToken(
          'google',
          code,
          redirectUri
        )

        console.log('백엔드 응답 성공:', backendResponse)

        // AuthContext의 login 함수를 사용하여 인증 상태 업데이트
        login(backendResponse.access_token)
        
        // localStorage에서 소셜 인증 관련 데이터 정리
        localStorage.removeItem('social_auth_return_url')
        localStorage.removeItem('social_auth_provider')

        setStatus('success')
        setTimeout(() => {
          // 로그인 성공 시 dashboard로 리다이렉트
          router.push('/dashboard')
        }, 1000) // 짧게 조정
      } catch (error) {
        console.error('백엔드 API 호출 실패:', error)
        setStatus('error')
        setErrorMessage(error instanceof Error ? error.message : 'Backend authentication failed')
        setTimeout(() => {
          router.push(returnUrl)
        }, 3000)
      }
    }

    processAuth()
  }, [searchParams, router])

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        {status === 'processing' && (
          <>
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Google 로그인 처리 중...</p>
          </>
        )}
        {status === 'success' && (
          <>
            <div className="rounded-full h-12 w-12 bg-green-100 mx-auto flex items-center justify-center">
              <svg className="h-6 w-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="mt-4 text-green-600">로그인 성공! 잠시 후 이동합니다...</p>
          </>
        )}
        {status === 'error' && (
          <>
            <div className="rounded-full h-12 w-12 bg-red-100 mx-auto flex items-center justify-center">
              <svg className="h-6 w-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <p className="mt-4 text-red-600">로그인 실패: {errorMessage}</p>
            <p className="mt-2 text-gray-500 text-sm">잠시 후 이전 페이지로 이동합니다...</p>
          </>
        )}
      </div>
    </div>
  )
}