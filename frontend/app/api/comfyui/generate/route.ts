import { NextRequest, NextResponse } from 'next/server'

// SSL 검증 비활성화 (개발 환경용)
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0'

// ComfyUI 워크플로우 템플릿
const createWorkflow = (params: any) => {
  const { prompt, negative_prompt, model, width, height, steps, cfg_scale, seed } = params
  
  return {
    "3": {
      "inputs": {
        "seed": seed || Math.floor(Math.random() * 1000000),
        "steps": steps || 20,
        "cfg": cfg_scale || 7.0,
        "sampler_name": "euler",
        "scheduler": "normal",
        "denoise": 1,
        "model": ["4", 0],
        "positive": ["6", 0],
        "negative": ["7", 0],
        "latent_image": ["5", 0]
      },
      "class_type": "KSampler",
      "_meta": {
        "title": "KSampler"
      }
    },
    "4": {
      "inputs": {
        "ckpt_name": model || "sd_xl_base_1.0.safetensors"
      },
      "class_type": "CheckpointLoaderSimple",
      "_meta": {
        "title": "Load Checkpoint"
      }
    },
    "5": {
      "inputs": {
        "width": width || 512,
        "height": height || 512,
        "batch_size": 1
      },
      "class_type": "EmptyLatentImage",
      "_meta": {
        "title": "Empty Latent Image"
      }
    },
    "6": {
      "inputs": {
        "text": prompt || "beautiful scenery",
        "clip": ["4", 1]
      },
      "class_type": "CLIPTextEncode",
      "_meta": {
        "title": "CLIP Text Encode (Prompt)"
      }
    },
    "7": {
      "inputs": {
        "text": negative_prompt || "blurry, low quality",
        "clip": ["4", 1]
      },
      "class_type": "CLIPTextEncode",
      "_meta": {
        "title": "CLIP Text Encode (Negative)"
      }
    },
    "8": {
      "inputs": {
        "samples": ["3", 0],
        "vae": ["4", 2]
      },
      "class_type": "VAEDecode",
      "_meta": {
        "title": "VAE Decode"
      }
    },
    "9": {
      "inputs": {
        "filename_prefix": "ComfyUI",
        "images": ["8", 0]
      },
      "class_type": "SaveImage",
      "_meta": {
        "title": "Save Image"
      }
    }
  }
}

// ComfyUI 이미지 생성 API
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    console.log('Next.js 라우트 받은 body:', body)

    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'

    // body 전체를 가공 없이 그대로 백엔드로 전달
    const response = await fetch(`${backendUrl}/api/v1/comfyui/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body)
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Backend error:', response.status, errorText)
      throw new Error(`Backend error: ${response.status} - ${errorText}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error generating image:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to generate image' 
      },
      { status: 500 }
    )
  }
}