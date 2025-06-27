export interface AIModel {
  id: string
  name: string
  description: string
  personality: string
  tone: string
  status: "training" | "ready" | "error"
  createdAt: string
  apiKey?: string
  trainingData?: {
    textSamples: number
    voiceSamples: number
    imageSamples: number
  }
  allowedGroups?: string[]
  ownerId?: string
}

export interface User {
  id: string
  email: string
  company: string
  name: string
  profileImage?: string
  groups: Group[]
  permissions: Permission[]
}

export interface Group {
  id: string
  name: string
  description: string
  permissions: Permission[]
  createdAt: string
  updatedAt: string
}

export interface Permission {
  id: string
  name: string
  description: string
  resource: string
  action: string
}

export interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
}

export interface JWTPayload {
  sub: string
  email: string
  name: string
  company: string
  groups: string[]
  permissions: string[]
  iat: number
  exp: number
}
