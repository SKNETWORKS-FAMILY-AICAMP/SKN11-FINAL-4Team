import { NextRequest, NextResponse } from 'next/server'

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
    const { prompt, negative_prompt, model, style, width, height, steps, cfg_scale, seed } = body

    if (!prompt) {
      return NextResponse.json(
        { success: false, error: 'Prompt is required' },
        { status: 400 }
      )
    }

    const comfyUIUrl = process.env.COMFYUI_URL || 'http://localhost:8188'
    
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

    // ComfyUI 워크플로우 생성
    const workflow = createWorkflow({
      prompt: enhancedPrompt,
      negative_prompt: enhancedNegativePrompt,
      model,
      width,
      height,
      steps,
      cfg_scale,
      seed
    })

    // ComfyUI로 워크플로우 전송
    const response = await fetch(`${comfyUIUrl}/prompt`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prompt: workflow,
        client_id: 'nextjs-frontend'
      })
    })

    if (!response.ok) {
      throw new Error('Failed to submit workflow to ComfyUI')
    }

    const data = await response.json()
    
    return NextResponse.json({
      success: true,
      job_id: data.prompt_id,
      message: 'Image generation started'
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