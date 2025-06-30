import { useSession } from "next-auth/react"
import { BackendAuthService } from "@/lib/backend-auth"

export function useBackendSession() {
  const { data: session, status } = useSession()

  const makeAuthenticatedRequest = async (endpoint: string, options: RequestInit = {}) => {
    if (!session?.backendJWT) {
      throw new Error('No backend authentication token available')
    }

    return BackendAuthService.makeAuthenticatedRequest(
      endpoint,
      options,
      session.backendJWT
    )
  }

  const verifyBackendToken = async () => {
    if (!session?.backendJWT) {
      return null
    }

    try {
      return await BackendAuthService.verifyToken(session.backendJWT)
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