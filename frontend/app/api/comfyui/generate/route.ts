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
    const { 
      prompt, 
      negative_prompt, 
      model, 
      style, 
      width, 
      height, 
      steps, 
      cfg_scale, 
      seed,
      workflow_id,
      custom_parameters 
    } = body

    if (!prompt) {
      return NextResponse.json(
        { success: false, error: 'Prompt is required' },
        { status: 400 }
      )
    }

    // 백엔드 API를 통해 커스텀 워크플로우로 이미지 생성
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
    
    // 스타일에 따른 프롬프트 수정
    let enhancedPrompt = prompt
    let enhancedNegativePrompt = negative_prompt || ''
    
    switch (style) {
      case 'realistic':
        enhancedPrompt = `${prompt}, photorealistic, high quality, detailed, 8k`
        enhancedNegativePrompt = `${enhancedNegativePrompt}, cartoon, anime, painting, drawing, abstract`.trim()
        break
      case 'artistic':
        enhancedPrompt = `${prompt}, artistic, painting style, masterpiece, fine art`
        enhancedNegativePrompt = `${enhancedNegativePrompt}, photorealistic, photograph`.trim()
        break
      case 'anime':
        enhancedPrompt = `${prompt}, anime style, manga, illustration, colorful`
        enhancedNegativePrompt = `${enhancedNegativePrompt}, photorealistic, real person`.trim()
        break
      case 'portrait':
        enhancedPrompt = `${prompt}, portrait, face focus, high quality, detailed face`
        enhancedNegativePrompt = `${enhancedNegativePrompt}, full body, landscape`.trim()
        break
      case 'landscape':
        enhancedPrompt = `${prompt}, landscape, scenic, wide angle, beautiful scenery`
        enhancedNegativePrompt = `${enhancedNegativePrompt}, portrait, close up, people`.trim()
        break
      case 'abstract':
        enhancedPrompt = `${prompt}, abstract art, creative, unique, artistic`
        enhancedNegativePrompt = `${enhancedNegativePrompt}, realistic, photographic`.trim()
        break
    }

    // 백엔드로 이미지 생성 요청 (RunPod 사용)
    const response = await fetch(`${backendUrl}/api/v1/comfyui/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prompt: enhancedPrompt,
        negative_prompt: enhancedNegativePrompt,
        width: width || 1024,
        height: height || 1024,
        steps: steps || 20,
        cfg_scale: cfg_scale || 7.0,
        seed: seed,
        style: style,
        workflow_id: workflow_id || 'basic_txt2img',
        custom_parameters: custom_parameters || {},
        use_runpod: true  // RunPod 사용 활성화
      })
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Backend error:', response.status, errorText)
      throw new Error(`Backend error: ${response.status} - ${errorText}`)
    }

    const data = await response.json()
    
    // 백엔드 응답에서 job_id 또는 prompt_id 찾기
    const jobId = data.job_id || data.prompt_id || data.id
    
    // 백엔드에서 즉시 완료된 이미지를 반환하는 경우 처리
    if (data.status === 'completed' && data.images && data.images.length > 0) {
      return NextResponse.json({
        success: true,
        job_id: jobId,
        status: 'completed',
        image_url: data.images[0], // base64 이미지 URL
        message: 'Image generation completed immediately',
        backend_response: data
      })
    }
    
    if (!jobId) {
      console.error('No job ID in backend response:', data)
      throw new Error('No job ID received from backend')
    }
    
    return NextResponse.json({
      success: true,
      job_id: jobId,
      message: 'Image generation started',
      backend_response: data
    })
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