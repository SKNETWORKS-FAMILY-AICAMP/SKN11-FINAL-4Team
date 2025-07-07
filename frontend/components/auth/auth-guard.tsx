"use client"

import React, { useEffect } from 'react'
import { useAuth } from '@/hooks/use-auth'
import { useRouter, usePathname } from 'next/navigation'

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
      console.log('User not authenticated, redirecting to login')
      router.push('/login')
      return
    }

    // group_id가 2인 사용자는 접근 차단 (특정 페이지 제외)
    if (user?.teams?.some(team => team.group_id === 2)) {
      console.log('User has blocked group_id 2, redirecting to login')
      router.push('/login')
      return
    }
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

  // 차단된 그룹 사용자는 빈 화면 (리디렉션 중)
  if (user?.teams?.some(team => team.group_id === 2)) {
    return <LoadingScreen />
  }

  // 모든 조건을 통과한 경우 자식 컴포넌트 렌더링
  return <>{children}</>
}