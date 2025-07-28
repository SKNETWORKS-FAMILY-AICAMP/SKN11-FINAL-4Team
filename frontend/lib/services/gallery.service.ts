import { apiClient } from '../api'

export interface GalleryImage {
  id: number
  storage_id: string
  s3_url: string
  team_id: number
  user_id: string
  prompt?: string
  negative_prompt?: string
  width: number
  height: number
  seed?: number
  workflow_name?: string
  model_name?: string
  extra_metadata?: Record<string, any>
  file_size?: number
  mime_type?: string
  created_at: string
  updated_at?: string
}

export interface GalleryPaginationInfo {
  page: number
  page_size: number
  total_count: number
  total_pages: number
}

export interface GalleryResponse {
  images: GalleryImage[]
  pagination: GalleryPaginationInfo
}

export interface GalleryQueryParams {
  page?: number
  page_size?: number
  team_id?: number
  user_id?: string
}

export const galleryService = {
  /**
   * 갤러리 이미지 목록 조회
   */
  async getImages(params: GalleryQueryParams): Promise<GalleryResponse> {
    const queryParams = new URLSearchParams()
    
    if (params.page) queryParams.append('page', params.page.toString())
    if (params.page_size) queryParams.append('page_size', params.page_size.toString())
    if (params.team_id) queryParams.append('team_id', params.team_id.toString())
    if (params.user_id) queryParams.append('user_id', params.user_id)
    
    const queryString = queryParams.toString()
    const endpoint = `/api/v1/gallery/images${queryString ? `?${queryString}` : ''}`
    
    return apiClient.get<GalleryResponse>(endpoint)
  },

  /**
   * 갤러리 이미지 삭제
   */
  async deleteImage(storageId: string): Promise<{ message: string }> {
    return apiClient.delete<{ message: string }>(`/api/v1/gallery/images/${storageId}`)
  }
}

export default galleryService