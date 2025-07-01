import apiClient from '../api'

export interface PermissionRequest {
  id: string
  userId: string
  userEmail: string
  userName: string
  requestedTeamId?: string
  reason: string
  contactEmail: string
  status: 'pending' | 'approved' | 'rejected'
  reviewedBy?: string
  reviewedAt?: string
  reviewComment?: string
  createdAt: string
  updatedAt: string
}

export interface CreatePermissionRequestData {
  reason: string
  contactEmail: string
  requestedTeamId?: string
}

export interface ReviewPermissionRequestData {
  status: 'approved' | 'rejected'
  reviewComment?: string
  assignedTeamId?: string
}

export interface PermissionRequestListResponse {
  requests: PermissionRequest[]
  total: number
  page: number
  limit: number
  totalPages: number
}

export interface PermissionRequestResponse {
  request: PermissionRequest
  message?: string
}

export interface Team {
  id: string
  name: string
  description: string
  isDefault: boolean
  memberCount: number
  permissions: string[]
  createdAt: string
}

export interface TeamListResponse {
  teams: Team[]
  total: number
}

export class PermissionService {
  /**
   * 권한 요청 생성
   */
  static async createPermissionRequest(data: CreatePermissionRequestData): Promise<PermissionRequest> {
    const response = await apiClient.post<PermissionRequestResponse>('/api/v1/permission-requests', data)
    return response.request
  }

  /**
   * 내 권한 요청 목록 조회
   */
  static async getMyPermissionRequests(params?: {
    page?: number
    limit?: number
    status?: 'pending' | 'approved' | 'rejected'
  }): Promise<PermissionRequestListResponse> {
    const searchParams = new URLSearchParams()
    
    if (params?.page) searchParams.set('page', params.page.toString())
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.status) searchParams.set('status', params.status)

    const query = searchParams.toString()
    const endpoint = `/api/v1/permission-requests/my${query ? `?${query}` : ''}`
    
    return await apiClient.get<PermissionRequestListResponse>(endpoint)
  }

  /**
   * 모든 권한 요청 목록 조회 (관리자용)
   */
  static async getAllPermissionRequests(params?: {
    page?: number
    limit?: number
    status?: 'pending' | 'approved' | 'rejected'
    search?: string
  }): Promise<PermissionRequestListResponse> {
    const searchParams = new URLSearchParams()
    
    if (params?.page) searchParams.set('page', params.page.toString())
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.status) searchParams.set('status', params.status)
    if (params?.search) searchParams.set('search', params.search)

    const query = searchParams.toString()
    const endpoint = `/api/v1/permission-requests${query ? `?${query}` : ''}`
    
    return await apiClient.get<PermissionRequestListResponse>(endpoint)
  }

  /**
   * 특정 권한 요청 조회
   */
  static async getPermissionRequest(requestId: string): Promise<PermissionRequest> {
    const response = await apiClient.get<PermissionRequestResponse>(`/api/v1/permission-requests/${requestId}`)
    return response.request
  }

  /**
   * 권한 요청 검토 (관리자용)
   */
  static async reviewPermissionRequest(
    requestId: string, 
    data: ReviewPermissionRequestData
  ): Promise<PermissionRequest> {
    const response = await apiClient.patch<PermissionRequestResponse>(
      `/api/v1/permission-requests/${requestId}/review`, 
      data
    )
    return response.request
  }

  /**
   * 권한 요청 취소
   */
  static async cancelPermissionRequest(requestId: string): Promise<void> {
    await apiClient.delete(`/api/v1/permission-requests/${requestId}`)
  }

  /**
   * 사용 가능한 팀 목록 조회
   */
  static async getAvailableTeams(): Promise<Team[]> {
    const response = await apiClient.get<TeamListResponse>('/api/v1/teams/available')
    return response.teams
  }

  /**
   * 모든 팀 목록 조회 (관리자용)
   */
  static async getAllTeams(): Promise<Team[]> {
    const response = await apiClient.get<TeamListResponse>('/api/v1/teams')
    return response.teams
  }

  /**
   * 팀 정보 조회
   */
  static async getTeam(teamId: string): Promise<Team> {
    return await apiClient.get<Team>(`/api/v1/teams/${teamId}`)
  }

  /**
   * 사용자의 팀 변경 (관리자용)
   */
  static async assignUserToTeam(userId: string, teamId: string): Promise<void> {
    await apiClient.post(`/api/v1/users/${userId}/assign-team`, {
      teamId
    })
  }

  /**
   * 권한 요청 통계 조회 (관리자용)
   */
  static async getPermissionRequestStats(): Promise<{
    totalRequests: number
    pendingRequests: number
    approvedRequests: number
    rejectedRequests: number
    dailyStats: Array<{
      date: string
      requests: number
      approved: number
      rejected: number
    }>
  }> {
    return await apiClient.get('/api/v1/permission-requests/stats')
  }

  /**
   * 권한 요청 알림 설정 조회
   */
  static async getNotificationSettings(): Promise<{
    emailNotifications: boolean
    slackNotifications: boolean
    webhookUrl?: string
  }> {
    return await apiClient.get('/api/v1/permission-requests/notifications')
  }

  /**
   * 권한 요청 알림 설정 업데이트 (관리자용)
   */
  static async updateNotificationSettings(settings: {
    emailNotifications?: boolean
    slackNotifications?: boolean
    webhookUrl?: string
  }): Promise<void> {
    await apiClient.patch('/api/v1/permission-requests/notifications', settings)
  }

  /**
   * 대량 권한 요청 처리 (관리자용)
   */
  static async bulkReviewRequests(requests: Array<{
    requestId: string
    status: 'approved' | 'rejected'
    reviewComment?: string
    assignedTeamId?: string
  }>): Promise<void> {
    await apiClient.post('/api/v1/permission-requests/bulk-review', {
      requests
    })
  }
}

export default PermissionService