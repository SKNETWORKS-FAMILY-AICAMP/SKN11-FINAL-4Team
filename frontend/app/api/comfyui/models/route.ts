import { NextRequest, NextResponse } from 'next/server'

// ComfyUI 모델 목록을 가져오는 API
export async function GET(request: NextRequest) {
  try {
    // 현재는 ComfyUI 서버가 연결되지 않았으므로 기본 모델 목록 반환
    const defaultModels = [
      { 
        id: 'sd_xl_base_1.0.safetensors', 
        name: 'Stable Diffusion XL Base 1.0', 
        type: 'checkpoint', 
        description: 'High-quality SDXL base model for general image generation',
        category: 'Base Model'
      },
      { 
        id: 'sd_v1-5-pruned-emaonly.safetensors', 
        name: 'Stable Diffusion v1.5', 
        type: 'checkpoint', 
        description: 'Classic SD 1.5 model, reliable for various styles',
        category: 'Base Model'
      },
      { 
        id: 'dreamshaper_8.safetensors', 
        name: 'DreamShaper v8', 
        type: 'checkpoint', 
        description: 'Popular fine-tuned model for artistic and fantasy images',
        category: 'Fine-tuned'
      },
      { 
        id: 'realvisxl_v4.0.safetensors', 
        name: 'RealVisXL v4.0', 
        type: 'checkpoint', 
        description: 'Specialized for photorealistic image generation',
        category: 'Realistic'
      }
    ]
    
    return NextResponse.json({
      success: true,
      models: defaultModels,
      message: 'Default models loaded successfully'
    })
  } catch (error) {
    console.error('Error fetching ComfyUI models:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to fetch models',
        models: []
      },
      { status: 500 }
    )
  }
}