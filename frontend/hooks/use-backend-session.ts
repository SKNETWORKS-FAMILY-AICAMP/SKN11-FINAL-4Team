import { useSession } from "next-auth/react"
import { BackendAuthService } from "@/lib/backend-auth"

export function useBackendSession() {
  const { data: session, status } = useSession()

  const makeAuthenticatedRequest = async (endpoint: string, options: RequestInit = {}) => {
    if (!session?.backendJWT) {
      throw new Error('No backend authentication token available')
    }

    // 직접 fetch를 사용하여 인증된 요청 구현
    const authHeaders = {
      'Authorization': `Bearer ${session.backendJWT}`,
      'Content-Type': 'application/json',
      ...options.headers
    }

    return fetch(endpoint, {
      ...options,
      headers: authHeaders
    })
  }

  const verifyBackendToken = async () => {
    if (!session?.backendJWT) {
      return null
    }

    try {
      return await BackendAuthService.verifyToken()
    } catch (error) {
      console.error('Backend token verification failed:', error)
      return null
    }
  }

  return {
    session,
    status,
    backendJWT: session?.backendJWT,
    backendUser: session?.backendUser,
    makeAuthenticatedRequest,
    verifyBackendToken,
    isAuthenticated: !!session?.backendJWT,
  }
}