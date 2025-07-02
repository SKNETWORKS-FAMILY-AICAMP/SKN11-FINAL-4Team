"use client"

import { useEffect, useState, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { BackendAuthService } from '@/lib/backend-auth'
import { useAuth } from '@/hooks/use-auth'

function NaverCallbackContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { login } = useAuth()
  const [status, setStatus] = useState<'processing' | 'success' | 'error'>('processing')
  const [errorMessage, setErrorMessage] = useState<string>('')

  useEffect(() => {
    const processAuth = async () => {
      const code = searchParams.get('code')
      const error = searchParams.get('error')
      const state = searchParams.get('state')
      const returnUrl = localStorage.getItem('social_auth_return_url') || '/'

      if (error) {
        setStatus('error')
        setErrorMessage(error || 'Naver authentication failed')
        setTimeout(() => {
          router.push(returnUrl)
        }, 3000)
        return
      }

      if (!code) {
        setStatus('error')
        setErrorMessage('No authorization code received')
        setTimeout(() => {
          router.push(returnUrl)
        }, 3000)
        return
      }

      try {
        // 먼저 Naver에서 토큰 교환
        const tokenResponse = await fetch('https://nid.naver.com/oauth2.0/token', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: new URLSearchParams({
            grant_type: 'authorization_code',
            client_id: process.env.NEXT_PUBLIC_NAVER_CLIENT_ID || '',
            client_secret: process.env.NAVER_CLIENT_SECRET || '',
            code: code,
            state: state || '',
          }),
        })

        const tokenData = await tokenResponse.json()

        if (!tokenResponse.ok || tokenData.error) {
          throw new Error(tokenData.error_description || 'Token exchange failed')
        }

        // 사용자 정보 가져오기
        const userResponse = await fetch('https://openapi.naver.com/v1/nid/me', {
          headers: {
            'Authorization': `Bearer ${tokenData.access_token}`,
          },
        })

        const userData = await userResponse.json()

        if (!userResponse.ok || userData.resultcode !== '00') {
          throw new Error(userData.message || 'Failed to fetch user data')
        }

        const user = userData.response

        // 백엔드에 사용자 정보 전달
        const backendResponse = await BackendAuthService.authenticateWithUserInfo('naver', {
          id: user.id,
          email: user.email,
          name: user.name,
          picture: user.profile_image || ''
        })

        // AuthContext의 login 함수를 사용하여 인증 상태 업데이트
        await login(backendResponse.access_token)
        
        // localStorage에서 소셜 인증 관련 데이터 정리
        localStorage.removeItem('social_auth_return_url')
        localStorage.removeItem('social_auth_provider')

        setStatus('success')
        setTimeout(() => {
          // 로그인 성공 시 dashboard로 리다이렉트
          router.push('/dashboard')
        }, 1000)
      } catch (error) {
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
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Naver 로그인 처리 중...</p>
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

export default function NaverCallback() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">인증 처리 중...</p>
        </div>
      </div>
    }>
      <NaverCallbackContent />
    </Suspense>
  )
}