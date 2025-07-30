import { tokenUtils } from './auth'

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

// 로그아웃 콜백 함수를 저장할 변수
let logoutCallback: (() => void) | null = null

// 로그아웃 콜백 설정 함수
export const setLogoutCallback = (callback: () => void) => {
  logoutCallback = callback
}

export class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: any
  ) {
    super(message)
    this.name = 'APIError'
  }
}

interface RequestOptions extends RequestInit {
  requireAuth?: boolean
  timeout?: number
}

class APIClient {
  private baseURL: string

  constructor(baseURL: string) {
    this.baseURL = baseURL
  }

  private async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const {
      requireAuth = true,
      timeout = 300000,
      headers: customHeaders = {},
      ...fetchOptions
    } = options

    const url = `${this.baseURL}${endpoint}`
    // 에러는 catch 블록에서만 남김

    const headers: Record<string, string> = {
      ...(customHeaders as Record<string, string>)
    }
    
    // FormData가 아닌 경우에만 Content-Type 설정
    if (!(fetchOptions.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json'
    }

    // 인증이 필요한 경우 토큰 추가
    if (requireAuth) {
      const token = tokenUtils.getToken()
      if (!token) {
        console.error('❌ 인증 토큰이 없습니다')
        throw new APIError('No authentication token found', 401)
      }
      headers.Authorization = `Bearer ${token}`
      console.log('🔑 인증 토큰 추가됨:', token.substring(0, 20) + '...')
    }

    // 타임아웃 설정
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    try {
      const response = await fetch(url, {
        ...fetchOptions,
        headers,
        signal: controller.signal
      })

      clearTimeout(timeoutId)

      let data
      const contentType = response.headers.get('content-type')

      if (contentType?.includes('application/json')) {
        data = await response.json()
      } else {
        data = await response.text()
      }

      if (!response.ok) {
        console.error('❌ API 오류 응답:', { 
          status: response.status, 
          statusText: response.statusText,
          contentType: response.headers.get('content-type'),
          data: data,
          url: response.url
        })
        
        // 401/403 에러 시 자동 로그아웃 처리
        if ((response.status === 401 || response.status === 403) && logoutCallback) {
          console.log('🔐 토큰 검증 실패로 인한 자동 로그아웃 처리')
          tokenUtils.removeToken()
          logoutCallback()
        }
        
        // 오류 메시지 추출
        let errorMessage = `HTTP ${response.status}`
        if (data) {
          if (typeof data === 'string') {
            errorMessage = data
          } else if (data.detail) {
            errorMessage = data.detail
          } else if (data.message) {
            errorMessage = data.message
          } else {
            errorMessage = JSON.stringify(data)
          }
        }
        
        throw new APIError(errorMessage, response.status, data)
      }

      return data
    } catch (error) {
      clearTimeout(timeoutId)

      if (error instanceof APIError) {
        throw error
      }

      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new APIError('Request timeout', 408)
      }

      throw new APIError(
        error instanceof Error ? error.message : 'Network error',
        0
      )
    }
  }

  async get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET' })
  }

  async post<T>(
    endpoint: string,
    data?: any,
    options?: RequestOptions
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: data instanceof FormData ? data : (data ? JSON.stringify(data) : undefined)
    })
  }

  async put<T>(
    endpoint: string,
    data?: any,
    options?: RequestOptions
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined
    })
  }

  async patch<T>(
    endpoint: string,
    data?: any,
    options?: RequestOptions
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined
    })
  }

  async delete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' })
  }

  // 이미지 다운로드용 메서드 (Blob 반환)
  async downloadImage(endpoint: string, options?: RequestOptions): Promise<Blob> {
    const {
      requireAuth = true,
      timeout = 30000,
      headers: customHeaders = {},
      ...fetchOptions
    } = options || {}

    const url = `${this.baseURL}${endpoint}`
    
    const headers: Record<string, string> = {
      ...(customHeaders as Record<string, string>)
    }

    if (requireAuth) {
      const token = tokenUtils.getToken()
      if (!token) {
        throw new APIError('No authentication token found', 401)
      }
      headers.Authorization = `Bearer ${token}`
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    try {
      const response = await fetch(url, {
        ...fetchOptions,
        headers,
        signal: controller.signal
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        // 401/403 에러 시 자동 로그아웃 처리
        if ((response.status === 401 || response.status === 403) && logoutCallback) {
          console.log('🔐 이미지 다운로드 시 토큰 검증 실패로 인한 자동 로그아웃 처리')
          tokenUtils.removeToken()
          logoutCallback()
        }
        
        throw new APIError(`HTTP ${response.status}`, response.status)
      }

      return await response.blob()
    } catch (error) {
      clearTimeout(timeoutId)

      if (error instanceof APIError) {
        throw error
      }

      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new APIError('Request timeout', 408)
      }

      throw new APIError(
        error instanceof Error ? error.message : 'Network error',
        0
      )
    }
  }

  // 파일 업로드용 메서드 (개선된 버전)
  async uploadFiles<T>(
    endpoint: string,
    files: FileList | File[],
    additionalData?: Record<string, string>,
    options?: Omit<RequestOptions, 'headers'>
  ): Promise<T> {
    const formData = new FormData()

    // 파일 배열을 FormData에 추가
    const fileArray = Array.from(files)
    fileArray.forEach((file, index) => {
      formData.append('files', file)
    })

    if (additionalData) {
      Object.entries(additionalData).forEach(([key, value]) => {
        formData.append(key, value)
      })
    }

    const { requireAuth = true, ...fetchOptions } = options || {}

    const headers: HeadersInit = {}

    if (requireAuth) {
      const token = tokenUtils.getToken()
      if (!token) {
        throw new APIError('No authentication token found', 401)
      }
      headers.Authorization = `Bearer ${token}`
    }

    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...fetchOptions,
      method: 'POST',
      headers,
      body: formData
    })

    let data
    const contentType = response.headers.get('content-type')

    if (contentType?.includes('application/json')) {
      data = await response.json()
    } else {
      data = await response.text()
    }

    if (!response.ok) {
      // 401/403 에러 시 자동 로그아웃 처리
      if ((response.status === 401 || response.status === 403) && logoutCallback) {
        console.log('🔐 파일 업로드 시 토큰 검증 실패로 인한 자동 로그아웃 처리')
        tokenUtils.removeToken()
        logoutCallback()
      }
      
      throw new APIError(
        data?.detail || data?.message || `HTTP ${response.status}`,
        response.status,
        data
      )
    }

    return data
  }
}

export const apiClient = new APIClient(API_BASE_URL)

// 인플루언서 말투 변환 API 함수
export const influencerToneAPI = {
  async transformWithInfluencerTone(influencerId: string, content: string, platform: string = "instagram") {
    return apiClient.post('/api/v1/content-enhancement/influencer-tone', {
      influencer_id: influencerId,
      content: content,
      platform: platform
    }, { timeout: 300000 })
  }
}

export default apiClient