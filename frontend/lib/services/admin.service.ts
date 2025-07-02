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
}

export default AdminService