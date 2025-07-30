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
        console.log('[Auth] 사용자가 로그아웃 상태입니다.')
        return null
      }
      const token = localStorage.getItem(TOKEN_KEY)
      if (token) {
        console.log(`[Auth] 토큰 발견: ${token.substring(0, 20)}...`)
        console.log(`[Auth] 토큰 길이: ${token.length}`)
        console.log(`[Auth] 토큰 만료 여부: ${tokenUtils.isTokenExpired(token) ? '만료됨' : '유효함'}`)
      } else {
        console.log('[Auth] 저장된 토큰이 없습니다.')
      }
      return token
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
    
    // JWT 토큰의 teams 정보를 User.teams 형태로 변환
    const teams = payload.teams ? payload.teams.map((teamName: string, index: number) => ({
      group_id: index + 1, // 임시 ID (실제 ID는 나중에 필요시 조회)
      group_name: teamName,
      group_description: undefined
    })) : []
    
    const user = {
      user_id: payload.sub,
      provider_id: payload.sub,
      provider: payload.provider,
      user_name: payload.name || '',
      email: payload.email || '',
      created_at: undefined,
      updated_at: undefined,
      teams: teams
    }
    
    return user
  } catch (error) {
    console.error('Error parsing JWT token:', error)
    return null
  }
}

// 실제 팀 ID가 필요한 경우에만 호출하는 함수
export const getRealTeamIds = async (teamNames: string[]): Promise<{[key: string]: number}> => {
  try {
    if (teamNames.length === 0) return {}
    
    const { BackendAuthService } = await import('./backend-auth')
    const response = await BackendAuthService.getTeamsByNames(teamNames)
    
    const teamIdMap: {[key: string]: number} = {}
    response.teams.forEach(team => {
      teamIdMap[team.group_name] = team.group_id
    })
    
    return teamIdMap
  } catch (error) {
    console.warn('실제 팀 ID 조회 실패:', error)
    return {}
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

// 실제 팀 ID로 권한 체크가 필요한 경우 사용
export const hasGroupWithRealId = async (user: User | null, groupId: number): Promise<boolean> => {
  if (!user || !user.teams) return false
  
  // 이미 실제 ID가 있는지 확인
  const hasRealId = user.teams.some(team => team.group_id === groupId)
  if (hasRealId) return true
  
  // 실제 ID가 없으면 API로 조회
  const teamNames = user.teams.map(team => team.group_name)
  const teamIdMap = await getRealTeamIds(teamNames)
  
  return Object.values(teamIdMap).includes(groupId)
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