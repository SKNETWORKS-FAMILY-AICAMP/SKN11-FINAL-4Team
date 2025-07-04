import { NextRequest, NextResponse } from 'next/server'

// 생성된 이미지 목록 가져오기 (임시 데이터)
export async function GET(request: NextRequest) {
  try {
    // 실제 구현에서는 데이터베이스에서 이미지 목록을 가져옴
    // 현재는 임시 데이터로 대체
    const images = [
      {
        id: 'example-1',
        prompt: 'beautiful sunset over mountains, photorealistic, 8k',
        negative_prompt: 'blurry, low quality',
        model: 'sd_xl_base_1.0',
        width: 1024,
        height: 768,
        steps: 20,
        cfg_scale: 7,
        seed: 123456,
        image_url: '/api/placeholder/1024/768',
        created_at: new Date().toISOString(),
        status: 'completed'
      },
      {
        id: 'example-2',
        prompt: 'anime girl, colorful, illustration style',
        negative_prompt: 'photorealistic, real person',
        model: 'sd_xl_base_1.0',
        width: 512,
        height: 512,
        steps: 25,
        cfg_scale: 8,
        seed: 789012,
        image_url: '/api/placeholder/512/512',
        created_at: new Date(Date.now() - 3600000).toISOString(),
        status: 'completed'
      }
    ]

    return NextResponse.json({
      success: true,
      images: images
    })
  } catch (error) {
    console.error('Error fetching images:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to fetch images' 
      },
      { status: 500 }
    )
  }
}

// 새 이미지 저장 (생성 완료 후)
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { 
      prompt, 
      negative_prompt, 
      model, 
      width, 
      height, 
      steps, 
      cfg_scale, 
      seed,
      image_url,
      job_id
    } = body

    // 실제 구현에서는 데이터베이스에 이미지 정보 저장
    const newImage = {
      id: job_id || `img_${Date.now()}`,
      prompt,
      negative_prompt,
      model,
      width,
      height,
      steps,
      cfg_scale,
      seed,
      image_url,
      created_at: new Date().toISOString(),
      status: 'completed'
    }

    // 여기서 데이터베이스에 저장하는 로직 구현
    // await saveImageToDatabase(newImage)

    return NextResponse.json({
      success: true,
      image: newImage
    })
  } catch (error) {
    console.error('Error saving image:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to save image' 
      },
      { status: 500 }
    )
  }
}