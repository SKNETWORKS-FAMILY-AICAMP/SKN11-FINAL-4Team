import type { JWTPayload, User, Group, Permission } from './types'

const TOKEN_KEY = 'access_token'
const USER_KEY = 'user'
const LOGGED_OUT_KEY = 'logged_out'

export const tokenUtils = {
  setToken: (token: string): void => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(TOKEN_KEY, token)
      localStorage.removeItem(LOGGED_OUT_KEY)
    }
  },

  getToken: (): string | null => {
    if (typeof window !== 'undefined') {
      const isLoggedOut = localStorage.getItem(LOGGED_OUT_KEY)
      if (isLoggedOut) {
        return null
      }
      return localStorage.getItem(TOKEN_KEY)
    }
    return null
  },

  removeToken: (): void => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      localStorage.setItem(LOGGED_OUT_KEY, 'true')
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
    
    return {
      user_id: payload.sub,
      provider_id: payload.sub, // JWT에서는 sub가 provider_id 역할을 함
      provider: payload.provider,
      user_name: payload.name || '',
      email: payload.email || '',
      created_at: undefined,
      updated_at: undefined,
      teams: [] // JWT에서는 groups가 string[]이므로 빈 배열로 초기화
    }
  } catch (error) {
    console.error('Error parsing user from token:', error)
    return null
  }
}

// 실제 팀 정보를 가져오는 함수
export const fetchUserWithTeams = async (token: string): Promise<User | null> => {
  try {
    const response = await fetch('http://localhost:8000/api/v1/auth/me', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    })
    
    if (!response.ok) {
      throw new Error('Failed to fetch user data')
    }
    
    const userData = await response.json()
    return userData
  } catch (error) {
    console.error('Error fetching user with teams:', error)
    return null
  }
}

export const hasPermission = (
  user: User | null,
  resource: string,
  action: string
): boolean => {
  if (!user || !user.teams) return false
  // 팀 정보가 있으면 권한이 있다고 가정 (간단한 구현)
  return user.teams.length > 0
}

export const hasGroup = (user: User | null, groupName: string): boolean => {
  if (!user || !user.teams) return false
  return user.teams.some(team => team.group_id.toString() === groupName || team.group_name === groupName)
}

export const hasAnyGroup = (user: User | null, groupNames: string[]): boolean => {
  if (!user || !user.teams || !groupNames.length) return false
  return groupNames.some(groupName => hasGroup(user, groupName))
}

export const isAdmin = (user: User | null): boolean => {
  if (!user || !user.teams) return false
  console.log('isAdmin check:', { user_id: user.user_id, teams: user.teams })
  const isAdminUser = user.teams.some(team => team.group_id === 1)
  console.log('isAdmin result:', isAdminUser)
  return isAdminUser
}

export const canAccessModel = (user: User | null, modelAllowedGroups?: string[]): boolean => {
  if (!user || !user.teams) return false
  if (!modelAllowedGroups || modelAllowedGroups.length === 0) return true
  
  return hasAnyGroup(user, modelAllowedGroups) || isAdmin(user)
}

// 팀 기반 권한 검사 함수들
export const isDefaultTeam = (user: User | null): boolean => {
  if (!user || !user.teams) return true
  return user.teams.length === 0
}

export const hasTeamPermission = (user: User | null, resource: string, action: string): boolean => {
  if (!user || !user.teams) return false
  return user.teams.length > 0
}

export const canCreateModel = (user: User | null): boolean => {
  return hasTeamPermission(user, 'model', 'create')
}

export const canCreatePost = (user: User | null): boolean => {
  return hasTeamPermission(user, 'post', 'create')
}

export const canManageContent = (user: User | null): boolean => {
  return hasTeamPermission(user, 'content', 'manage')
}

export const requiresPermissionRequest = (user: User | null): boolean => {
  return isDefaultTeam(user)
}