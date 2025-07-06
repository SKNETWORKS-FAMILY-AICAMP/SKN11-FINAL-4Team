import apiClient from './api'
import { User } from './types'

export interface BackendAuthResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface SocialLoginRequest {
  provider: string
  code?: string
  redirect_uri?: string
  user_info?: any
}

export class BackendAuthService {
  static async exchangeCodeForToken(provider: string, code: string, redirectUri?: string): Promise<BackendAuthResponse> {
    const data: SocialLoginRequest = {
      provider,
      code,
      redirect_uri: redirectUri
    }

    const result = await apiClient.post<BackendAuthResponse>('/api/v1/auth/social-login', data, {
      requireAuth: false
    })

    return result
  }

  static async verifyToken(): Promise<User> {
    return await apiClient.get<User>('/api/v1/auth/me')
  }

  static async authenticateWithUserInfo(provider: string, userInfo: any): Promise<BackendAuthResponse> {
    const data: SocialLoginRequest = {
      provider,
      user_info: userInfo
    }

    return await apiClient.post<BackendAuthResponse>('/api/v1/auth/social-login', data, {
      requireAuth: false
    })
  }

  static async refreshToken(refreshToken: string): Promise<BackendAuthResponse> {
    return await apiClient.post<BackendAuthResponse>('/api/v1/auth/refresh', {
      refresh_token: refreshToken
    }, {
      requireAuth: false
    })
  }

  static async logout(): Promise<void> {
    try {
      await apiClient.post('/api/v1/auth/logout', {}, {
        timeout: 5000 // 짧은 타임아웃
      })
    } catch (error) {
      // 로그아웃은 실패해도 로컬 토큰을 제거해야 함
      console.warn('Logout API failed:', error)
      // 에러를 다시 던지지 않음 - 로컬 정리는 계속 진행되어야 함
    }
  }
}