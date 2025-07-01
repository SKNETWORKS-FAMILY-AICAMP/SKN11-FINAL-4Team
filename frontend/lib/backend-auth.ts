const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"

export interface BackendAuthResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: any
}

export class BackendAuthService {
  static async exchangeCodeForToken(provider: string, code: string, redirectUri?: string): Promise<BackendAuthResponse> {
    console.log('백엔드 API 호출:', {
      url: `${BACKEND_URL}/api/auth/social-login`,
      provider,
      code: code?.substring(0, 20) + '...',
      redirectUri
    })

    const response = await fetch(`${BACKEND_URL}/api/auth/social-login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        provider,
        code,
        redirect_uri: redirectUri
      })
    })

    console.log('백엔드 응답 상태:', response.status, response.statusText)

    if (!response.ok) {
      const errorText = await response.text()
      console.error('백엔드 에러 응답:', errorText)
      
      let error
      try {
        error = JSON.parse(errorText)
      } catch {
        error = { detail: errorText || 'Backend authentication failed' }
      }
      
      throw new Error(error.detail || 'Backend authentication failed')
    }

    const result = await response.json()
    console.log('백엔드 성공 응답:', result)
    return result
  }

  static async verifyToken(token: string): Promise<any> {
    const response = await fetch(`${BACKEND_URL}/api/auth/me`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      }
    })

    if (!response.ok) {
      throw new Error('Token verification failed')
    }

    return response.json()
  }

  static async makeAuthenticatedRequest(endpoint: string, options: RequestInit = {}, token?: string): Promise<Response> {
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    } as HeadersInit

    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    return fetch(`${BACKEND_URL}${endpoint}`, {
      ...options,
      headers,
    })
  }

  static async authenticateWithUserInfo(provider: string, userInfo: any): Promise<BackendAuthResponse> {
    const response = await fetch(`${BACKEND_URL}/api/auth/social-login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        provider,
        user_info: userInfo
      })
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Backend authentication failed')
    }

    return response.json()
  }
}