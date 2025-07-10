"use client"

import React, { useEffect } from 'react'
import { useAuth } from '@/hooks/use-auth'
import { useRouter, usePathname } from 'next/navigation'
import { Navigation } from '@/components/navigation'

interface AuthGuardProps {
  children: React.ReactNode
}

// 인증이 필요없는 공개 페이지 목록
const PUBLIC_ROUTES = [
  '/login',
  '/api/auth/callback/google',
  '/api/auth/callback/naver',
  '/auth/instagram/callback'
]

// 로딩 중 표시할 컴포넌트
const LoadingScreen: React.FC = () => (
  <div className="fixed inset-0 bg-white bg-opacity-90 flex items-center justify-center z-50">
    <div className="text-center">
      <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-600 mx-auto mb-4"></div>
      <p className="text-lg font-medium text-gray-700">인증 확인 중...</p>
      <p className="text-sm text-gray-500 mt-2">잠시만 기다려주세요</p>
    </div>
  </div>
)

export const AuthGuard: React.FC<AuthGuardProps> = ({ children }) => {
  const { isAuthenticated, isLoading, user } = useAuth()
  const router = useRouter()
  const pathname = usePathname()

  // 공개 페이지인지 확인
  const isPublicRoute = PUBLIC_ROUTES.some(route => pathname.startsWith(route))

  useEffect(() => {
    // 로딩 중이면 대기
    if (isLoading) return

    // 공개 페이지는 인증 없이 접근 가능
    if (isPublicRoute) return

    // 인증되지 않은 사용자는 로그인 페이지로 리디렉션
    if (!isAuthenticated) {
      router.push('/login')
      return
    }

    // 그룹이 할당되지 않은 사용자는 권한 요청 메시지 표시
    // 이 경우 useEffect에서는 처리하지 않고 렌더링 부분에서 처리
  }, [isAuthenticated, isLoading, user, pathname, router, isPublicRoute])

  // 로딩 중일 때 로딩 스크린 표시
  if (isLoading) {
    return <LoadingScreen />
  }

  // 공개 페이지는 바로 렌더링
  if (isPublicRoute) {
    return <>{children}</>
  }

  // 인증되지 않은 사용자는 빈 화면 (리디렉션 중)
  if (!isAuthenticated) {
    return <LoadingScreen />
  }

  // 그룹이 할당되지 않은 사용자는 권한 요청 메시지 표시
  if (!user?.teams || user.teams.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="flex items-center justify-center" style={{ minHeight: 'calc(100vh - 64px)' }}>
          <div className="max-w-md mx-auto text-center p-8 bg-white rounded-lg shadow-lg">
            <div className="mb-6">
              <div className="w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">권한 요청 필요</h2>
              <p className="text-gray-600 text-lg">
                관리자에게 권한을 요청하세요
              </p>
            </div>
            <div className="text-sm text-gray-500">
              <p>현재 계정으로는 서비스에 접근할 수 없습니다.</p>
              <p className="mt-2">시스템 관리자에게 문의하여 적절한 권한을 요청해주세요.</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // 모든 조건을 통과한 경우 자식 컴포넌트 렌더링
  return <>{children}</>
}