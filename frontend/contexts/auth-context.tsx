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

  const logout = useCallback(() => {
    tokenUtils.removeToken()
    setAuthState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false
    })
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