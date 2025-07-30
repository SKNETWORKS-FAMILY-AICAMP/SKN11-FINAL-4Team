"use client"

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { tokenUtils, getUserFromToken, hasPermission, hasGroup, hasAnyGroup, isAdmin, canAccessModel, requiresPermissionRequest, canCreateModel, canCreatePost, canManageContent, isDefaultTeam } from '@/lib/auth'
import type { AuthState, User } from '@/lib/types'
import {BackendAuthService} from '@/lib/backend-auth'
import { setLogoutCallback } from '@/lib/api'

interface AuthContextType extends AuthState {
  login: (token: string) => void
  loginWithUserInfo: (token: string, user: any) => void
  logout: () => void
  hasPermission: (resource: string, action: string) => boolean
  hasGroup: (groupName: string) => boolean
  hasAnyGroup: (groupNames: string[]) => boolean
  isAdmin: () => boolean
  canAccessModel: (modelAllowedGroups?: string[]) => boolean
  // 팀 권한 함수들
  requiresPermissionRequest: () => boolean
  canCreateModel: () => boolean
  canCreatePost: () => boolean
  canManageContent: () => boolean
  isDefaultTeam: () => boolean
}

export const AuthContext = createContext<AuthContextType | null>(null)

interface AuthProviderProps {
  children: React.ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: true
  })
  
  const router = useRouter()

  const logout = useCallback(async () => {
    try {
      await BackendAuthService.logout()
    } catch (error) {
      // console.warn('Backend logout failed:', error)
    }
    // 로컬 토큰 및 상태 정리
    tokenUtils.removeToken()
    setAuthState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false
    })
    // 로그인 페이지로 이동
    router.push('/login')
  }, [router])

  const initializeAuth = useCallback(async () => {
    const token = tokenUtils.getToken()
    
    if (!token) {
      setAuthState(prev => ({
        ...prev,
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false
      }))
      return
    }

    if (tokenUtils.isTokenExpired(token)) {
      tokenUtils.removeToken()
      setAuthState(prev => ({
        ...prev,
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false
      }))
      return
    }

    try {
      // JWT 토큰에서 직접 사용자 정보 가져오기
      const user = getUserFromToken(token)
      if (user) {
        setAuthState(prev => ({
          ...prev,
          user,
          token,
          isAuthenticated: true,
          isLoading: false
        }))
      } else {
        // JWT 파싱 실패 시 백엔드에서 사용자 정보 가져오기
        const backendUser = await BackendAuthService.verifyToken()
        setAuthState(prev => ({
          ...prev,
          user: backendUser,
          token,
          isAuthenticated: true,
          isLoading: false
        }))
      }
    } catch (error) {
      // console.error('Failed to verify token:', error)
      // Instagram API 오류 등으로 인한 일시적 실패 시 토큰을 제거하지 않음
      // 실제 인증 실패인 경우만 토큰 제거
      const errorStatus = (error as any)?.status
      if (errorStatus === 401 || errorStatus === 403) {
        tokenUtils.removeToken()
        setAuthState(prev => ({
          ...prev,
          user: null,
          token: null,
          isAuthenticated: false,
          isLoading: false
        }))
      } else {
        // 네트워크 오류 등 일시적 문제는 토큰 유지
        setAuthState(prev => ({
          ...prev,
          user: null,
          token,
          isAuthenticated: false,
          isLoading: false
        }))
      }
    }
  }, [])

  // 초기 인증 상태 확인
  useEffect(() => {
    initializeAuth()
    
    // API 클라이언트에 로그아웃 콜백 설정
    setLogoutCallback(() => {
      logout()
    })
  }, [logout])

  // 토큰 만료 확인 (별도 effect로 분리)
  useEffect(() => {
    const checkTokenExpiry = () => {
      const token = tokenUtils.getToken()
      if (token && tokenUtils.isTokenExpired(token)) {
        logout()
      }
    }

    // 1분마다 토큰 만료 확인
    const interval = setInterval(checkTokenExpiry, 60000)

    return () => clearInterval(interval)
  }, [logout])

  const login = useCallback(async (token: string) => {
    try {
      tokenUtils.setToken(token)
      
      // JWT 토큰에서 직접 사용자 정보 가져오기
      const user = getUserFromToken(token)
      if (user) {
        setAuthState({
          user,
          token,
          isAuthenticated: true,
          isLoading: false
        })
      } else {
        // JWT 파싱 실패 시 백엔드에서 사용자 정보 가져오기
        const backendUser = await BackendAuthService.verifyToken()
        setAuthState({
          user: backendUser,
          token,
          isAuthenticated: true,
          isLoading: false
        })
      }
    } catch (error) {
      // console.error('Login failed:', error)
      // 로그인 실패 시에만 토큰 제거
      const errorStatus = (error as any)?.status
      if (errorStatus === 401 || errorStatus === 403) {
        tokenUtils.removeToken()
      }
      throw error
    }
  }, [])

  const loginWithUserInfo = useCallback(async (token: string, user: any) => {
    try {
      tokenUtils.setToken(token)
      
      // JWT 토큰에서 팀 정보를 가져와서 사용자 정보 업데이트
      const userWithTeams = getUserFromToken(token)
      
      setAuthState({
        user: userWithTeams || user, // 팀 정보가 있으면 사용, 없으면 원본 사용
        token,
        isAuthenticated: true,
        isLoading: false
      })
    } catch (error) {
      // console.error('Login with user info failed:', error)
      // 로그인 실패 시에만 토큰 제거
      const errorStatus = (error as any)?.status
      if (errorStatus === 401 || errorStatus === 403) {
        tokenUtils.removeToken()
      }
      throw error
    }
  }, [])

  const contextValue: AuthContextType = {
    ...authState,
    login,
    loginWithUserInfo,
    logout,
    hasPermission: (resource: string, action: string) => hasPermission(authState.user, resource, action),
    hasGroup: (groupName: string) => hasGroup(authState.user, groupName),
    hasAnyGroup: (groupNames: string[]) => hasAnyGroup(authState.user, groupNames),
    isAdmin: () => isAdmin(authState.user),
    canAccessModel: (modelAllowedGroups?: string[]) => canAccessModel(authState.user, modelAllowedGroups),
    // 팀 권한 함수들
    requiresPermissionRequest: () => requiresPermissionRequest(authState.user),
    canCreateModel: () => canCreateModel(authState.user),
    canCreatePost: () => canCreatePost(authState.user),
    canManageContent: () => canManageContent(authState.user),
    isDefaultTeam: () => isDefaultTeam(authState.user)
  }

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}