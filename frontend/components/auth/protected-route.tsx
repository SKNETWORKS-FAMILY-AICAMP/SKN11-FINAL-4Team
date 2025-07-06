"use client"

import React from 'react'
import { useAuth, usePermission } from '@/hooks/use-auth'
import { redirect } from 'next/navigation'

interface ProtectedRouteProps {
  children: React.ReactNode
  requireAuth?: boolean
  requirePermission?: {
    resource: string
    action: string
  }
  requireGroup?: string
  requireAnyGroup?: string[]
  requireAdmin?: boolean
  blockGroup?: number
  fallbackUrl?: string
  renderFallback?: () => React.ReactNode
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requireAuth = true,
  requirePermission,
  requireGroup,
  requireAnyGroup,
  requireAdmin = false,
  blockGroup,
  fallbackUrl = '/login',
  renderFallback
}) => {
  const { isAuthenticated, isLoading, user } = useAuth()
  const { hasGroup, hasAnyGroup, isAdmin } = usePermission()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (requireAuth && !isAuthenticated) {
    redirect(fallbackUrl)
  }

  if (blockGroup && user?.teams?.some(team => team.group_id === blockGroup)) {
    if (renderFallback) {
      return renderFallback()
    }
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">접근 권한이 없습니다</h2>
          <p className="text-gray-600">해당 그룹의 사용자는 이 페이지에 접근할 수 없습니다.</p>
        </div>
      </div>
    )
  }

  if (requireAdmin && !user?.teams?.some(team => team.group_id === 1)) {
    if (renderFallback) {
      return renderFallback()
    }
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">접근 권한이 없습니다</h2>
          <p className="text-gray-600">관리자 권한이 필요합니다. (group_id: 1)</p>
        </div>
      </div>
    )
  }
  if (requireGroup && !hasGroup(requireGroup)) {
    if (renderFallback) {
      return renderFallback()
    }
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">접근 권한이 없습니다</h2>
          <p className="text-gray-600">필요한 그룹: {requireGroup}</p>
        </div>
      </div>
    )
  }

  if (requireAnyGroup && !hasAnyGroup(requireAnyGroup)) {
    if (renderFallback) {
      return renderFallback()
    }
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">접근 권한이 없습니다</h2>
          <p className="text-gray-600">필요한 그룹 중 하나: {requireAnyGroup.join(', ')}</p>
        </div>
      </div>
    )
  }

  return <>{children}</>
}

interface RequireAuthProps {
  children: React.ReactNode
  fallbackUrl?: string
  blockGroup?: number
}

export const RequireAuth: React.FC<RequireAuthProps> = ({ children, fallbackUrl = '/login', blockGroup }) => {
  return (
    <ProtectedRoute requireAuth={true} fallbackUrl={fallbackUrl} blockGroup={blockGroup}>
      {children}
    </ProtectedRoute>
  )
}

interface RequirePermissionProps {
  children: React.ReactNode
  resource: string
  action: string
  renderFallback?: () => React.ReactNode
}

export const RequirePermission: React.FC<RequirePermissionProps> = ({
  children,
  resource,
  action,
  renderFallback
}) => {
  return (
    <ProtectedRoute
      requirePermission={{ resource, action }}
      renderFallback={renderFallback}
    >
      {children}
    </ProtectedRoute>
  )
}

interface RequireGroupProps {
  children: React.ReactNode
  group: string
  renderFallback?: () => React.ReactNode
}

export const RequireGroup: React.FC<RequireGroupProps> = ({
  children,
  group,
  renderFallback
}) => {
  return (
    <ProtectedRoute requireGroup={group} renderFallback={renderFallback}>
      {children}
    </ProtectedRoute>
  )
}

interface RequireAdminProps {
  children: React.ReactNode
  renderFallback?: () => React.ReactNode
}

export const RequireAdmin: React.FC<RequireAdminProps> = ({
  children,
  renderFallback
}) => {
  return (
    <ProtectedRoute requireAdmin={true} renderFallback={renderFallback}>
      {children}
    </ProtectedRoute>
  )
}