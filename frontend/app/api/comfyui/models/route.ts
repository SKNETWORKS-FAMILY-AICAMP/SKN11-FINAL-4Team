import { NextRequest, NextResponse } from 'next/server'

// ComfyUI 모델 목록을 가져오는 API
export async function GET(request: NextRequest) {
  try {
    // ComfyUI 서버 URL (환경변수로 관리)
    const comfyUIUrl = process.env.COMFYUI_URL || 'http://localhost:8188'
    
    // ComfyUI의 모델 목록 API 호출
    const response = await fetch(`${comfyUIUrl}/object_info`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    })

    if (!response.ok) {
      throw new Error('Failed to fetch models from ComfyUI')
    }

    const data = await response.json()
    
    // 체크포인트 모델 목록 추출
    const checkpointModels = data.CheckpointLoaderSimple?.input?.required?.ckpt_name?.[0] || []
    
    // 모델 목록을 프론트엔드에서 사용하기 쉬운 형태로 변환
    const models = checkpointModels.map((modelName: string, index: number) => ({
      id: modelName,
      name: modelName.replace(/\.(ckpt|safetensors)$/, ''), // 확장자 제거
      type: 'checkpoint',
      description: `Checkpoint model: ${modelName}`
    }))

    return NextResponse.json({
      success: true,
      models: models
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