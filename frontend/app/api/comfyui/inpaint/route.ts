import { NextRequest, NextResponse } from 'next/server'

// ComfyUI 인페인팅 워크플로우 템플릿
const createInpaintWorkflow = (params: any) => {
  const { prompt, negative_prompt, model, steps, cfg_scale, seed } = params
  
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
        "latent_image": ["10", 0]
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
        "image": "input_image.png",
        "upload": "image"
      },
      "class_type": "LoadImage",
      "_meta": {
        "title": "Load Image"
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
        "filename_prefix": "inpaint",
        "images": ["8", 0]
      },
      "class_type": "SaveImage",
      "_meta": {
        "title": "Save Image"
      }
    },
    "10": {
      "inputs": {
        "pixels": ["5", 0],
        "mask": ["11", 0],
        "vae": ["4", 2]
      },
      "class_type": "VAEEncodeForInpaint",
      "_meta": {
        "title": "VAE Encode For Inpaint"
      }
    },
    "11": {
      "inputs": {
        "image": "mask.png",
        "upload": "mask",
        "channel": "red"
      },
      "class_type": "LoadImageMask",
      "_meta": {
        "title": "Load Image Mask"
      }
    }
  }
}

// Base64 이미지를 파일로 변환하는 헬퍼 함수
const base64ToFile = (base64String: string, filename: string) => {
  const arr = base64String.split(',')
  const mime = arr[0].match(/:(.*?);/)![1]
  const bstr = atob(arr[1])
  let n = bstr.length
  const u8arr = new Uint8Array(n)
  
  while (n--) {
    u8arr[n] = bstr.charCodeAt(n)
  }
  
  return new File([u8arr], filename, { type: mime })
}

// ComfyUI 인페인팅 API
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { image, mask, prompt, negative_prompt, model, steps, cfg_scale, seed } = body

    if (!image || !mask || !prompt) {
      return NextResponse.json(
        { success: false, error: 'Image, mask, and prompt are required' },
        { status: 400 }
      )
    }

    const comfyUIUrl = process.env.COMFYUI_URL || 'http://localhost:8188'
    
    // Base64 이미지를 파일로 변환
    const imageFile = base64ToFile(image, 'input_image.png')
    const maskFile = base64ToFile(mask, 'mask.png')
    
    // 이미지와 마스크를 ComfyUI에 업로드
    const imageFormData = new FormData()
    imageFormData.append('image', imageFile)
    imageFormData.append('type', 'input')
    imageFormData.append('subfolder', '')
    
    const maskFormData = new FormData()
    maskFormData.append('image', maskFile)
    maskFormData.append('type', 'input')
    maskFormData.append('subfolder', '')
    
    // 이미지 업로드
    const imageUploadResponse = await fetch(`${comfyUIUrl}/upload/image`, {
      method: 'POST',
      body: imageFormData
    })
    
    if (!imageUploadResponse.ok) {
      throw new Error('Failed to upload image to ComfyUI')
    }
    
    // 마스크 업로드
    const maskUploadResponse = await fetch(`${comfyUIUrl}/upload/image`, {
      method: 'POST',
      body: maskFormData
    })
    
    if (!maskUploadResponse.ok) {
      throw new Error('Failed to upload mask to ComfyUI')
    }
    
    // 인페인팅 워크플로우 생성
    const workflow = createInpaintWorkflow({
      prompt,
      negative_prompt,
      model,
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
        client_id: 'nextjs-inpaint'
      })
    })

    if (!response.ok) {
      throw new Error('Failed to submit inpainting workflow to ComfyUI')
    }

    const data = await response.json()
    
    return NextResponse.json({
      success: true,
      job_id: data.prompt_id,
      message: 'Inpainting started successfully'
    })
  } catch (error) {
    console.error('Error starting inpainting:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to start inpainting' 
      },
      { status: 500 }
    )
  }
}