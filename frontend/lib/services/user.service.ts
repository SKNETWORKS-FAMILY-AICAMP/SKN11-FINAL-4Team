import apiClient from '../api'
import { User } from '../types'

export interface UserResponse {
  user: User
  message?: string
}

export interface UpdateUserRequest {
  name?: string
  company?: string
  profileImage?: string
}

export interface ChangePasswordRequest {
  currentPassword: string
  newPassword: string
  confirmPassword: string
}

export class UserService {
  /**
   * 현재 사용자 정보 조회
   */
  static async getCurrentUser(): Promise<User> {
    const response = await apiClient.get<UserResponse>('/api/v1/auth/me')
    return response.user
  }

  /**
   * 향상된 사용자 정보 조회 (소셜 로그인 정보 포함)
   */
  static async getCurrentUserEnhanced(): Promise<User> {
    const response = await apiClient.get<UserResponse>('/api/v1/auth/me/enhanced')
    return response.user
  }

  /**
   * 사용자 정보 업데이트
   */
  static async updateUser(data: UpdateUserRequest): Promise<User> {
    const response = await apiClient.patch<UserResponse>('/api/v1/users/me', data)
    return response.user
  }

  /**
   * 프로필 이미지 업로드
   */
  static async uploadProfileImage(file: File): Promise<User> {
    const response = await apiClient.uploadFile<UserResponse>(
      '/api/v1/users/me/profile-image',
      file
    )
    return response.user
  }

  /**
   * 비밀번호 변경
   */
  static async changePassword(data: ChangePasswordRequest): Promise<void> {
    await apiClient.post('/api/v1/users/me/change-password', data)
  }

  /**
   * 계정 삭제
   */
  static async deleteAccount(): Promise<void> {
    await apiClient.delete('/api/v1/users/me')
  }

  /**
   * 사용자 통계 조회
   */
  static async getUserStats(): Promise<{
    totalModels: number
    totalPosts: number
    totalViews: number
    joinedAt: string
  }> {
    return await apiClient.get('/api/v1/users/me/stats')
  }

  /**
   * 팀 정보 조회
   */
  static async getTeamInfo(): Promise<{
    id: string
    name: string
    description: string
    isDefault: boolean
    memberCount: number
    createdAt: string
  }> {
    return await apiClient.get('/api/v1/users/me/team')
  }

  /**
   * 팀 변경 요청
   */
  static async requestTeamChange(teamId: string, reason: string): Promise<void> {
    await apiClient.post('/api/v1/users/me/team-change-request', {
      teamId,
      reason
    })
  }
}

export default UserService