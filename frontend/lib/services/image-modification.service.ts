import { apiClient } from '../api'

export interface ImageModificationResponse {
  success: boolean
  message: string
  storage_id: string
  s3_url: string
  width: number
  height: number
  edit_instruction: string
}

export const imageModificationService = {
  /**
   * 단순 텍스트 설명으로 이미지 수정
   */
  async modifyImageSimple(
    imageFile: File,
    editInstruction: string,
    workflowId: string = 'image_modify_text_simple'
  ): Promise<ImageModificationResponse> {
    const formData = new FormData()
    formData.append('image', imageFile)
    formData.append('edit_instruction', editInstruction)
    formData.append('workflow_id', workflowId)

    return apiClient.post<ImageModificationResponse>(
      '/api/v1/image-modification/modify-simple',
      formData,
      {
        headers: {
          // FormData를 사용할 때는 Content-Type을 설정하지 않음
          // 브라우저가 자동으로 multipart/form-data와 boundary를 설정함
        } as any
      }
    )
  }
}

export default imageModificationService