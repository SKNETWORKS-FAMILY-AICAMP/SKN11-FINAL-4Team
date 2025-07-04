import { NextRequest, NextResponse } from 'next/server'

// ComfyUI 모델 목록을 가져오는 API
export async function GET(request: NextRequest) {
  try {
    // Backend API를 통해 ComfyUI 모델 정보 가져오기
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
    
    // Backend의 ComfyUI 모델 목록 엔드포인트 호출
    const response = await fetch(`${backendUrl}/api/v1/boards/comfyui/models`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    })

    if (!response.ok) {
      throw new Error('Failed to fetch models from backend')
    }

    const data = await response.json()
    
    return NextResponse.json({
      success: data.success,
      models: data.models
    })
  } catch (error) {
    console.error('Error fetching ComfyUI models:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to fetch models from ComfyUI',
        models: [
          // 기본 모델들 (ComfyUI가 연결되지 않은 경우)
          { id: 'sd_xl_base_1.0', name: 'Stable Diffusion XL Base', type: 'checkpoint', description: 'Base SDXL model' },
          { id: 'sd_v1-5', name: 'Stable Diffusion v1.5', type: 'checkpoint', description: 'SD 1.5 model' }
        ]
      },
      { status: 500 }
    )
  }
}