import apiClient from '../api'
import { Post, Comment } from '../types'

export interface CreatePostRequest {
  title: string
  content: string
  excerpt?: string
  modelId?: string
  tags?: string[]
  categories?: string[]
  featuredImage?: string
  status?: 'draft' | 'published'
}

export interface UpdatePostRequest {
  title?: string
  content?: string
  excerpt?: string
  modelId?: string
  tags?: string[]
  categories?: string[]
  featuredImage?: string
  status?: 'draft' | 'published' | 'archived'
}

export interface PostListResponse {
  posts: Post[]
  total: number
  page: number
  limit: number
  totalPages: number
}

export interface PostResponse {
  post: Post
  message?: string
}

export interface CreateCommentRequest {
  content: string
  parentId?: string
}

export interface CommentListResponse {
  comments: Comment[]
  total: number
  page: number
  limit: number
}

export class PostService {
  /**
   * 게시글 목록 조회
   */
  static async getPosts(params?: {
    page?: number
    limit?: number
    search?: string
    status?: 'draft' | 'published' | 'archived'
    authorId?: string
    modelId?: string
    tags?: string[]
    categories?: string[]
    sortBy?: 'createdAt' | 'publishedAt' | 'viewCount' | 'likeCount'
    sortOrder?: 'asc' | 'desc'
  }): Promise<PostListResponse> {
    const searchParams = new URLSearchParams()
    
    if (params?.page) searchParams.set('page', params.page.toString())
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.search) searchParams.set('search', params.search)
    if (params?.status) searchParams.set('status', params.status)
    if (params?.authorId) searchParams.set('author_id', params.authorId)
    if (params?.modelId) searchParams.set('model_id', params.modelId)
    if (params?.tags) searchParams.set('tags', params.tags.join(','))
    if (params?.categories) searchParams.set('categories', params.categories.join(','))
    if (params?.sortBy) searchParams.set('sort_by', params.sortBy)
    if (params?.sortOrder) searchParams.set('sort_order', params.sortOrder)

    const query = searchParams.toString()
    const endpoint = `/api/v1/posts${query ? `?${query}` : ''}`
    
    return await apiClient.get<PostListResponse>(endpoint)
  }

  /**
   * 내 게시글 목록 조회
   */
  static async getMyPosts(params?: {
    page?: number
    limit?: number
    search?: string
    status?: 'draft' | 'published' | 'archived'
  }): Promise<PostListResponse> {
    const searchParams = new URLSearchParams()
    
    if (params?.page) searchParams.set('page', params.page.toString())
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.search) searchParams.set('search', params.search)
    if (params?.status) searchParams.set('status', params.status)

    const query = searchParams.toString()
    const endpoint = `/api/v1/posts/my${query ? `?${query}` : ''}`
    
    return await apiClient.get<PostListResponse>(endpoint)
  }

  /**
   * 특정 게시글 조회
   */
  static async getPost(postId: string): Promise<Post> {
    const response = await apiClient.get<PostResponse>(`/api/v1/posts/${postId}`)
    return response.post
  }

  /**
   * 게시글 생성
   */
  static async createPost(data: CreatePostRequest): Promise<Post> {
    const response = await apiClient.post<PostResponse>('/api/v1/posts', data)
    return response.post
  }

  /**
   * 게시글 업데이트
   */
  static async updatePost(postId: string, data: UpdatePostRequest): Promise<Post> {
    const response = await apiClient.patch<PostResponse>(`/api/v1/posts/${postId}`, data)
    return response.post
  }

  /**
   * 게시글 삭제
   */
  static async deletePost(postId: string): Promise<void> {
    await apiClient.delete(`/api/v1/posts/${postId}`)
  }

  /**
   * 게시글 발행
   */
  static async publishPost(postId: string): Promise<Post> {
    const response = await apiClient.patch<PostResponse>(`/api/v1/posts/${postId}/publish`)
    return response.post
  }

  /**
   * 게시글 보관
   */
  static async archivePost(postId: string): Promise<Post> {
    const response = await apiClient.patch<PostResponse>(`/api/v1/posts/${postId}/archive`)
    return response.post
  }

  /**
   * 게시글 좋아요
   */
  static async likePost(postId: string): Promise<{ liked: boolean; likeCount: number }> {
    return await apiClient.post(`/api/v1/posts/${postId}/like`)
  }

  /**
   * 게시글 북마크
   */
  static async bookmarkPost(postId: string): Promise<{ bookmarked: boolean }> {
    return await apiClient.post(`/api/v1/posts/${postId}/bookmark`)
  }

  /**
   * 게시글 조회수 증가
   */
  static async incrementViewCount(postId: string): Promise<{ viewCount: number }> {
    return await apiClient.post(`/api/v1/posts/${postId}/view`)
  }

  /**
   * 게시글 댓글 목록 조회
   */
  static async getComments(postId: string, params?: {
    page?: number
    limit?: number
    sortBy?: 'createdAt' | 'likeCount'
    sortOrder?: 'asc' | 'desc'
  }): Promise<CommentListResponse> {
    const searchParams = new URLSearchParams()
    
    if (params?.page) searchParams.set('page', params.page.toString())
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.sortBy) searchParams.set('sort_by', params.sortBy)
    if (params?.sortOrder) searchParams.set('sort_order', params.sortOrder)

    const query = searchParams.toString()
    const endpoint = `/api/v1/posts/${postId}/comments${query ? `?${query}` : ''}`
    
    return await apiClient.get<CommentListResponse>(endpoint)
  }

  /**
   * 댓글 작성
   */
  static async createComment(postId: string, data: CreateCommentRequest): Promise<Comment> {
    return await apiClient.post(`/api/v1/posts/${postId}/comments`, data)
  }

  /**
   * 댓글 수정
   */
  static async updateComment(commentId: string, content: string): Promise<Comment> {
    return await apiClient.patch(`/api/v1/comments/${commentId}`, { content })
  }

  /**
   * 댓글 삭제
   */
  static async deleteComment(commentId: string): Promise<void> {
    await apiClient.delete(`/api/v1/comments/${commentId}`)
  }

  /**
   * 댓글 좋아요
   */
  static async likeComment(commentId: string): Promise<{ liked: boolean; likeCount: number }> {
    return await apiClient.post(`/api/v1/comments/${commentId}/like`)
  }

  /**
   * 인기 게시글 조회
   */
  static async getTrendingPosts(period: '24h' | '7d' | '30d' = '7d'): Promise<Post[]> {
    return await apiClient.get(`/api/v1/posts/trending?period=${period}`)
  }

  /**
   * 추천 게시글 조회
   */
  static async getRecommendedPosts(limit: number = 10): Promise<Post[]> {
    return await apiClient.get(`/api/v1/posts/recommended?limit=${limit}`)
  }

  /**
   * 태그 목록 조회
   */
  static async getTags(search?: string): Promise<string[]> {
    const endpoint = `/api/v1/posts/tags${search ? `?search=${search}` : ''}`
    return await apiClient.get(endpoint)
  }

  /**
   * 카테고리 목록 조회
   */
  static async getCategories(): Promise<string[]> {
    return await apiClient.get('/api/v1/posts/categories')
  }

  /**
   * 게시글 통계 조회
   */
  static async getPostStats(postId: string): Promise<{
    viewCount: number
    likeCount: number
    commentCount: number
    shareCount: number
    dailyViews: Array<{
      date: string
      views: number
    }>
  }> {
    return await apiClient.get(`/api/v1/posts/${postId}/stats`)
  }

  /**
   * 이미지 업로드
   */
  static async uploadImage(file: File): Promise<{ url: string }> {
    return await apiClient.uploadFile('/api/v1/posts/upload-image', file)
  }
}

export default PostService