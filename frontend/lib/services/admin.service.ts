import apiClient from '../api'
import { User, Team } from '../types'

export interface AdminUser {
  user_id: string
  provider_id: string
  provider: string
  user_name: string
  email: string
  created_at?: string
  updated_at?: string
}

export interface AdminTeam {
  group_id: number
  group_name: string
  group_description?: string
  users: AdminUser[]
}

export interface CreateTeamRequest {
  group_name: string
  group_description?: string
}

export interface UpdateTeamRequest {
  group_name?: string
  group_description?: string
}

export interface BulkUserOperation {
  user_ids: string[]
}

// HF Token 관련 인터페이스
export interface AdminHFToken {
  hf_manage_id: string
  group_id?: number | null
  hf_token_nickname: string
  hf_user_name: string
  hf_token_masked?: string
  created_at?: string
  updated_at?: string
}

export interface AdminCreateHFTokenRequest {
  hf_token_value: string
  hf_token_nickname: string
  hf_user_name: string
  assign_to_team_id?: number | null
}

export interface AdminHFTokenTestRequest {
  hf_token_value: string
}

export interface AdminHFTokenTestResponse {
  is_valid: boolean
  username?: string
  error_message?: string
  permissions?: string[]
}

export interface AdminStatsResponse {
  total_users: number
  total_teams: number
  total_hf_tokens: number
  unassigned_tokens: number
  active_influencers: number
}

export interface AdminTeamInfo {
  group_id: number
  group_name: string
  group_description?: string
  token_count: number
  user_count: number
  created_at?: string
  updated_at?: string
}

export class AdminService {
  /**
   * 모든 팀 목록 조회 (관리자만)
   */
  static async getTeams(params?: {
    skip?: number
    limit?: number
  }): Promise<AdminTeam[]> {
    const searchParams = new URLSearchParams()
    
    if (params?.skip) searchParams.set('skip', params.skip.toString())
    if (params?.limit) searchParams.set('limit', params.limit.toString())

    const query = searchParams.toString()
    const endpoint = `/api/v1/teams${query ? `?${query}` : ''}`
    
    return await apiClient.get<AdminTeam[]>(endpoint)
  }

  /**
   * 특정 팀 조회 (사용자 목록 포함)
   */
  static async getTeam(groupId: number): Promise<AdminTeam> {
    return await apiClient.get<AdminTeam>(`/api/v1/teams/${groupId}`)
  }

  /**
   * 팀 생성 (관리자만)
   */
  static async createTeam(data: CreateTeamRequest): Promise<AdminTeam> {
    return await apiClient.post<AdminTeam>('/api/v1/teams', data)
  }

  /**
   * 팀 정보 수정 (관리자만)
   */
  static async updateTeam(groupId: number, data: UpdateTeamRequest): Promise<AdminTeam> {
    return await apiClient.put<AdminTeam>(`/api/v1/teams/${groupId}`, data)
  }

  /**
   * 팀 삭제 (관리자만)
   */
  static async deleteTeam(groupId: number): Promise<void> {
    await apiClient.delete(`/api/v1/teams/${groupId}`)
  }

  /**
   * 팀에 사용자 추가 (관리자만)
   */
  static async addUserToTeam(groupId: number, userId: string): Promise<void> {
    await apiClient.post(`/api/v1/teams/${groupId}/users/${userId}`)
  }

  /**
   * 팀에 여러 사용자 일괄 추가 (관리자만)
   */
  static async bulkAddUsersToTeam(groupId: number, userIds: string[]): Promise<{
    message: string
    added_users: string[]
    already_in_team: string[]
    not_found_users: string[]
  }> {
    return await apiClient.post(`/api/v1/teams/${groupId}/users/bulk-add`, {
      user_ids: userIds
    })
  }

  /**
   * 팀에서 사용자 제거 (관리자만)
   */
  static async removeUserFromTeam(groupId: number, userId: string): Promise<void> {
    await apiClient.delete(`/api/v1/teams/${groupId}/users/${userId}`)
  }

  /**
   * 팀에서 여러 사용자 일괄 제거 (관리자만)
   */
  static async bulkRemoveUsersFromTeam(groupId: number, userIds: string[]): Promise<{
    message: string
    removed_users: string[]
    not_in_team: string[]
    not_found_users: string[]
  }> {
    return await apiClient.post(`/api/v1/teams/${groupId}/users/bulk-remove`, {
      user_ids: userIds
    })
  }

  /**
   * 팀의 사용자 목록 조회
   */
  static async getTeamUsers(groupId: number, params?: {
    skip?: number
    limit?: number
  }): Promise<AdminUser[]> {
    const searchParams = new URLSearchParams()
    
    if (params?.skip) searchParams.set('skip', params.skip.toString())
    if (params?.limit) searchParams.set('limit', params.limit.toString())

    const query = searchParams.toString()
    const endpoint = `/api/v1/teams/${groupId}/users${query ? `?${query}` : ''}`
    
    return await apiClient.get<AdminUser[]>(endpoint)
  }

  /**
   * 모든 사용자 목록 조회
   */
  static async getUsers(params?: {
    skip?: number
    limit?: number
  }): Promise<AdminUser[]> {
    const searchParams = new URLSearchParams()
    
    if (params?.skip) searchParams.set('skip', params.skip.toString())
    if (params?.limit) searchParams.set('limit', params.limit.toString())

    const query = searchParams.toString()
    const endpoint = `/api/v1/users${query ? `?${query}` : ''}`
    
    return await apiClient.get<AdminUser[]>(endpoint)
  }

  /**
   * 특정 사용자 조회
   */
  static async getUser(userId: string): Promise<AdminUser> {
    return await apiClient.get<AdminUser>(`/api/v1/users/${userId}`)
  }

  /**
   * 사용자 삭제 (관리자만)
   */
  static async deleteUser(userId: string): Promise<void> {
    await apiClient.delete(`/api/v1/users/${userId}`)
  }

  /**
   * 특정 사용자의 팀 목록 조회 (관리자만)
   */
  static async getUserTeams(userId: string): Promise<{
    group_id: number
    group_name: string
    group_description?: string
  }[]> {
    return await apiClient.get(`/api/v1/users/${userId}/teams`)
  }

  // ===========================================
  // HF Token 관리 메서드들 (관리자 전용)
  // ===========================================

  /**
   * 관리자 대시보드 통계 조회
   */
  static async getAdminStats(): Promise<AdminStatsResponse> {
    return await apiClient.get<AdminStatsResponse>('/api/v1/admin/stats')
  }

  /**
   * 허깅페이스 토큰 생성 (관리자만)
   */
  static async createHFToken(data: AdminCreateHFTokenRequest): Promise<AdminHFToken> {
    return await apiClient.post<AdminHFToken>('/api/v1/admin/hf-tokens', data)
  }

  /**
   * 모든 허깅페이스 토큰 목록 조회 (관리자만)
   */
  static async getHFTokens(params?: {
    include_assigned?: boolean
    team_id?: number
    skip?: number
    limit?: number
  }): Promise<AdminHFToken[]> {
    const searchParams = new URLSearchParams()
    
    if (params?.include_assigned !== undefined) {
      searchParams.set('include_assigned', params.include_assigned.toString())
    }
    if (params?.team_id) searchParams.set('team_id', params.team_id.toString())
    if (params?.skip) searchParams.set('skip', params.skip.toString())
    if (params?.limit) searchParams.set('limit', params.limit.toString())

    const query = searchParams.toString()
    const endpoint = `/api/v1/admin/hf-tokens${query ? `?${query}` : ''}`
    
    return await apiClient.get<AdminHFToken[]>(endpoint)
  }

  /**
   * 토큰을 특정 팀에 할당 (관리자만)
   */
  static async assignTokenToTeam(tokenId: string, teamId: number): Promise<{
    message: string
    token_id: string
    team_id: number
    team_name: string
  }> {
    return await apiClient.post(`/api/v1/admin/hf-tokens/${tokenId}/assign-team/${teamId}`)
  }

  /**
   * 토큰 할당 해제 (관리자만)
   */
  static async unassignToken(tokenId: string): Promise<{
    message: string
    token_id: string
    previous_team_id?: number
    previous_team_name?: string
  }> {
    return await apiClient.post(`/api/v1/admin/hf-tokens/${tokenId}/unassign`)
  }

  /**
   * 허깅페이스 토큰 삭제 (관리자만)
   */
  static async deleteHFToken(tokenId: string): Promise<{ message: string }> {
    return await apiClient.delete(`/api/v1/admin/hf-tokens/${tokenId}`)
  }

  /**
   * 허깅페이스 토큰 유효성 검증 (관리자만)
   */
  static async testHFToken(data: AdminHFTokenTestRequest): Promise<AdminHFTokenTestResponse> {
    return await apiClient.post<AdminHFTokenTestResponse>('/api/v1/admin/hf-tokens/test', data)
  }

  /**
   * 관리자용 팀 목록 조회 (토큰 할당용, 추가 정보 포함)
   */
  static async getAdminTeams(): Promise<AdminTeamInfo[]> {
    return await apiClient.get<AdminTeamInfo[]>('/api/v1/admin/teams')
  }
}

export default AdminService