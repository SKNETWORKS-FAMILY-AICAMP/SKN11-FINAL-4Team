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

export interface Post {
  id: string
  title: string
  content: string
  excerpt?: string
  status: "draft" | "published" | "archived"
  author: {
    id: string
    name: string
    email: string
    profileImage?: string
  }
  modelId?: string
  model?: AIModel
  tags: string[]
  categories: string[]
  featuredImage?: string
  viewCount: number
  likeCount: number
  commentCount: number
  isLiked?: boolean
  isBookmarked?: boolean
  publishedAt?: string
  createdAt: string
  updatedAt: string
}

export interface Comment {
  id: string
  content: string
  author: {
    id: string
    name: string
    email: string
    profileImage?: string
  }
  postId: string
  parentId?: string
  replies?: Comment[]
  likeCount: number
  isLiked?: boolean
  createdAt: string
  updatedAt: string
}

export interface User {
  user_id: string
  provider_id: string
  provider: string
  user_name: string
  name?: string
  email: string
  company?: string
  profileImage?: string
  created_at?: string
  updated_at?: string
  teams: Team[]
  permissions?: Permission[]
}

export interface Team {
  group_id: number
  group_name: string
  group_description?: string
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
  email?: string
  name?: string
  provider: string
  company?: string
  groups: string[]
  permissions: string[]
  instagram?: {
    username?: string
    account_type?: string
    is_business_verified?: boolean
    business_features?: {
      insights?: boolean
      content_publishing?: boolean
      message_management?: boolean
      comment_management?: boolean
    }
  }
  iat: number
  exp: number
}
