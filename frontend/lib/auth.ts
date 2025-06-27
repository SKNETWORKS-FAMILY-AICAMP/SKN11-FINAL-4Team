import type { JWTPayload, User, Group, Permission } from './types'

const TOKEN_KEY = 'auth_token'
const USER_KEY = 'user_data'

const MOCK_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJ0ZXN0QGdtYWlsLmNvbSIsIm5hbWUiOiJUZXN0IFVzZXIiLCJjb21wYW55IjoiVGVzdCBDb21wYW55IiwiZ3JvdXBzIjpbImFkbWluIiwidXNlciJdLCJwZXJtaXNzaW9ucyI6WyIqOioiXSwiZXhwIjoxNzU2NjQ2ODAwfQ.qMgTUwDXMXJkAxNVKkvOcECH8Ys8HYY8C9r8bLu5XQo'

export const tokenUtils = {
  setToken: (token: string): void => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(TOKEN_KEY, token)
    }
  },

  getToken: (): string | null => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(TOKEN_KEY) || MOCK_TOKEN
    }
    return MOCK_TOKEN
  },

  removeToken: (): void => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    }
  },

  isTokenExpired: (token: string): boolean => {
    try {
      const payload = parseJWT(token)
      return Date.now() >= payload.exp * 1000
    } catch {
      return true
    }
  },

  isTokenValid: (): boolean => {
    const token = tokenUtils.getToken()
    if (!token) return false
    return !tokenUtils.isTokenExpired(token)
  }
}

export const parseJWT = (token: string): JWTPayload => {
  try {
    const base64Url = token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(jsonPayload)
  } catch (error) {
    throw new Error('Invalid JWT token')
  }
}

export const getUserFromToken = (token: string): User | null => {
  try {
    const payload = parseJWT(token)
    
    const groups: Group[] = payload.groups?.map(groupId => ({
      id: groupId,
      name: groupId,
      description: '',
      permissions: [],
      createdAt: '',
      updatedAt: ''
    })) || []

    const permissions: Permission[] = payload.permissions?.map(permissionId => ({
      id: permissionId,
      name: permissionId,
      description: '',
      resource: permissionId.split(':')[0] || '',
      action: permissionId.split(':')[1] || ''
    })) || []

    return {
      id: payload.sub,
      email: payload.email,
      name: payload.name,
      company: payload.company,
      groups,
      permissions
    }
  } catch (error) {
    console.error('Error parsing user from token:', error)
    return null
  }
}

export const hasPermission = (
  user: User | null,
  resource: string,
  action: string
): boolean => {
  if (!user) return false
  
  const permissionKey = `${resource}:${action}`
  return user.permissions.some(permission => 
    permission.id === permissionKey || 
    permission.id === `${resource}:*` ||
    permission.id === '*:*'
  )
}

export const hasGroup = (user: User | null, groupName: string): boolean => {
  if (!user) return false
  return user.groups.some(group => group.id === groupName || group.name === groupName)
}

export const hasAnyGroup = (user: User | null, groupNames: string[]): boolean => {
  if (!user || !groupNames.length) return false
  return groupNames.some(groupName => hasGroup(user, groupName))
}

export const isAdmin = (user: User | null): boolean => {
  return hasGroup(user, 'admin') || hasPermission(user, '*', '*')
}

export const canAccessModel = (user: User | null, modelAllowedGroups?: string[]): boolean => {
  if (!user) return false
  if (!modelAllowedGroups || modelAllowedGroups.length === 0) return true
  
  return hasAnyGroup(user, modelAllowedGroups) || isAdmin(user)
}