const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"

export interface BackendAuthResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: any
}

export class BackendAuthService {
  static async exchangeCodeForToken(provider: string, code: string, redirectUri?: string): Promise<BackendAuthResponse> {
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

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Backend authentication failed')
    }

    return response.json()
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