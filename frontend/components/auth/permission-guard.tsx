"use client"

import { ReactNode } from 'react'
import { useAuth } from '@/hooks/use-auth'
import { requiresPermissionRequest, canCreateModel, canCreatePost, canManageContent } from '@/lib/auth'
import PermissionRequestPage from './permission-request'

interface PermissionGuardProps {
  children: ReactNode
  requiredPermission?: 'create-model' | 'create-post' | 'manage-content'
  fallback?: ReactNode
}

export default function PermissionGuard({ 
  children, 
  requiredPermission,
  fallback 
}: PermissionGuardProps) {
  const { user, isLoading } = useAuth()

  // 로딩 중일 때
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  // 로그인하지 않은 경우
  if (!user) {
    return fallback || <div>로그인이 필요합니다.</div>
  }

  // default 팀인 경우 권한 요청 페이지 표시
  if (requiresPermissionRequest(user)) {
    return <PermissionRequestPage />
  }

  // 특정 권한이 필요한 경우 검사
  if (requiredPermission) {
    let hasPermission = false

    switch (requiredPermission) {
      case 'create-model':
        hasPermission = canCreateModel(user)
        break
      case 'create-post':
        hasPermission = canCreatePost(user)
        break
      case 'manage-content':
        hasPermission = canManageContent(user)
        break
      default:
        hasPermission = true
    }

    if (!hasPermission) {
      return fallback || (
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">접근 권한이 없습니다</h2>
            <p className="text-gray-600">이 기능을 사용하려면 추가 권한이 필요합니다.</p>
          </div>
        </div>
      )
    }
  }

  return <>{children}</>
}

// 편의 함수들
export const ModelCreationGuard = ({ children, fallback }: { children: ReactNode, fallback?: ReactNode }) => (
  <PermissionGuard requiredPermission="create-model" fallback={fallback}>
    {children}
  </PermissionGuard>
)

export const PostCreationGuard = ({ children, fallback }: { children: ReactNode, fallback?: ReactNode }) => (
  <PermissionGuard requiredPermission="create-post" fallback={fallback}>
    {children}
  </PermissionGuard>
)

export const ContentManagementGuard = ({ children, fallback }: { children: ReactNode, fallback?: ReactNode }) => (
  <PermissionGuard requiredPermission="manage-content" fallback={fallback}>
    {children}
  </PermissionGuard>
)