import { useContext } from 'react'
import { AuthContext } from '@/contexts/auth-context'

export function useAuth() {
  const context = useContext(AuthContext)
  
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  
  return context
}

// 권한 관련 훅들을 별도로 제공
export function usePermission() {
  const context = useContext(AuthContext)
  
  if (!context) {
    throw new Error('usePermission must be used within an AuthProvider')
  }
  
  return {
    user: context.user,
    hasPermission: context.hasPermission,
    hasGroup: context.hasGroup,
    hasAnyGroup: context.hasAnyGroup,
    isAdmin: context.isAdmin,
    canAccessModel: context.canAccessModel,
    requiresPermissionRequest: context.requiresPermissionRequest,
    canCreateModel: context.canCreateModel,
    canCreatePost: context.canCreatePost,
    canManageContent: context.canManageContent,
    isDefaultTeam: context.isDefaultTeam
  }
}
