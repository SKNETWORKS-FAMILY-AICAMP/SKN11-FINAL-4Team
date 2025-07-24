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

export const getUserFromToken = async (token: string): Promise<User | null> => {
  try {
    const payload = parseJWT(token)
    
    console.log('🔍 JWT Payload:', payload) // 디버깅용 로그
    
    // JWT 토큰에 teams 정보가 있으면 실제 팀 정보를 가져오기
    let teams: any[] = []
    if (payload.teams && payload.teams.length > 0) {
      try {
        const { BackendAuthService } = await import('./backend-auth')
        const response = await BackendAuthService.getTeamsByNames(payload.teams)
        teams = response.teams
        console.log('🏢 실제 팀 정보 조회 완료:', teams)
      } catch (error) {
        console.warn('팀 정보 조회 실패, JWT 정보 사용:', error)
        // 실패시 JWT의 팀 이름을 그대로 사용
        teams = payload.teams.map((teamName: string) => ({
          group_id: 0, // 실제 ID를 알 수 없으므로 0 사용
          group_name: teamName,
          group_description: undefined
        }))
      }
    }
    
    const user = {
      user_id: payload.sub,
      provider_id: payload.sub, // JWT에서는 sub가 provider_id 역할을 함
      provider: payload.provider,
      user_name: payload.name || '',
      email: payload.email || '',
      created_at: undefined,
      updated_at: undefined,
      teams: teams
    }
    
    console.log('👤 최종 사용자 정보:', user) // 디버깅용 로그
    
    return user
  } catch (error) {
    console.error('Error parsing JWT token:', error)
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
  return user.teams.some(team => team.group_id === 1)
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