"use client"

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { tokenUtils, getUserFromToken, hasPermission, hasGroup, hasAnyGroup, isAdmin, canAccessModel } from '@/lib/auth'
import type { AuthState, User } from '@/lib/types'

interface AuthContextType extends AuthState {
  login: (token: string) => void
  logout: () => void
  hasPermission: (resource: string, action: string) => boolean
  hasGroup: (groupName: string) => boolean
  hasAnyGroup: (groupNames: string[]) => boolean
  isAdmin: () => boolean
  canAccessModel: (modelAllowedGroups?: string[]) => boolean
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

  const initializeAuth = useCallback(() => {
    const token = tokenUtils.getToken()
    
    if (!token) {
      setAuthState({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false
      })
      return
    }

    if (tokenUtils.isTokenExpired(token)) {
      tokenUtils.removeToken()
      setAuthState({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false
      })
      return
    }

    const user = getUserFromToken(token)
    if (user) {
      setAuthState({
        user,
        token,
        isAuthenticated: true,
        isLoading: false
      })
    } else {
      tokenUtils.removeToken()
      setAuthState({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false
      })
    }
  }, [])

  useEffect(() => {
    initializeAuth()
    
    const interval = setInterval(() => {
      const token = tokenUtils.getToken()
      if (token && tokenUtils.isTokenExpired(token)) {
        console.log('Token expired, logging out...')
        logout()
      }
    }, 60000)

    return () => clearInterval(interval)
  }, [initializeAuth])

  const login = useCallback((token: string) => {
    try {
      const user = getUserFromToken(token)
      if (!user) {
        throw new Error('Invalid token')
      }

      tokenUtils.setToken(token)
      setAuthState({
        user,
        token,
        isAuthenticated: true,
        isLoading: false
      })
    } catch (error) {
      console.error('Login failed:', error)
      throw error
    }
  }, [])

  const logout = useCallback(async () => {
    try {
      // 소셜 로그인 세션도 정리 (NextAuth)
      if (typeof window !== 'undefined') {
        const { signOut } = await import('next-auth/react')
        await signOut({ redirect: false })
      }
    } catch (error) {
      console.warn('NextAuth signout failed:', error)
    }

    // 로컬 토큰 및 상태 정리
    tokenUtils.removeToken()
    setAuthState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false
    })

    // 로그인 페이지로 리다이렉트
    router.push('/login')
  }, [router])

  const contextValue: AuthContextType = {
    ...authState,
    login,
    logout,
    hasPermission: (resource: string, action: string) => hasPermission(authState.user, resource, action),
    hasGroup: (groupName: string) => hasGroup(authState.user, groupName),
    hasAnyGroup: (groupNames: string[]) => hasAnyGroup(authState.user, groupNames),
    isAdmin: () => isAdmin(authState.user),
    canAccessModel: (modelAllowedGroups?: string[]) => canAccessModel(authState.user, modelAllowedGroups)
  }

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  )
}