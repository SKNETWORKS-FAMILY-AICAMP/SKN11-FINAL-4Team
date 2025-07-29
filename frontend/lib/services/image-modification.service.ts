import { apiClient } from '../api'
import { tokenUtils } from '../auth'

export interface ImageModificationResponse {
  success: boolean
  message: string
  storage_id: string
  s3_url: string
  width: number
  height: number
  edit_instruction: string
}

export interface ModificationProgress {
  status: string
  progress: number
  message: string
}

export const imageModificationService = {
  /**
   * 단순 텍스트 설명으로 이미지 수정 (REST API)
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
  },

  /**
   * WebSocket을 통한 실시간 이미지 수정
   */
  async modifyImageWebSocket(
    imageFile: File,
    editInstruction: string,
    onProgress?: (progress: ModificationProgress) => void,
    onComplete?: (result: ImageModificationResponse) => void,
    onError?: (error: string) => void
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const token = tokenUtils.getToken()
      if (!token) {
        reject(new Error('인증 토큰이 없습니다'))
        return
      }

      // 이미지 생성 WebSocket URL 사용
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/image-generation/ws`
      
      const ws = new WebSocket(wsUrl)
      
      ws.onopen = async () => {
        // 인증 메시지 전송
        ws.send(JSON.stringify({
          type: 'auth',
          token: token
        }))
      }
      
      ws.onmessage = async (event) => {
        const message = JSON.parse(event.data)
        
        switch (message.type) {
          case 'connected':
            // 연결 성공 후 이미지 수정 요청
            const reader = new FileReader()
            reader.onload = () => {
              const base64Data = reader.result?.toString().split(',')[1]
              ws.send(JSON.stringify({
                type: 'modify_image',
                data: {
                  image: base64Data,
                  edit_instruction: editInstruction
                }
              }))
            }
            reader.readAsDataURL(imageFile)
            break
            
          case 'modification_progress':
            if (onProgress) {
              onProgress(message.data)
            }
            break
            
          case 'modification_complete':
            if (onComplete) {
              onComplete(message.data)
            }
            ws.close()
            resolve()
            break
            
          case 'error':
            if (onError) {
              onError(message.data.message)
            }
            ws.close()
            reject(new Error(message.data.message))
            break
            
          case 'pong':
            // 핑퐁 응답 무시
            break
        }
      }
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        if (onError) {
          onError('WebSocket 연결 오류')
        }
        reject(error)
      }
      
      ws.onclose = () => {
        console.log('WebSocket 연결 종료')
      }
      
      // 주기적으로 ping 메시지 전송
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        } else {
          clearInterval(pingInterval)
        }
      }, 30000) // 30초마다
    })
  }
}

export default imageModificationService