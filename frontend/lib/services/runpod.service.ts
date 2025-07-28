/**
 * RunPod 서비스
 * RunPod 비용 조회 및 관리
 */

import { apiClient } from '@/lib/api'

export interface RunPodCredits {
  remaining_credits: number
  last_updated: string
}

export interface RunPodApiResponse<T> {
  success: boolean
  data: T
  message: string
}

export class RunPodService {
  /**
   * RunPod 남은 크레딧 조회
   */
  static async getCredits(): Promise<RunPodCredits> {
    const response = await apiClient.get<RunPodApiResponse<RunPodCredits>>('/api/v1/runpod/credits')
    return response.data
  }




} 