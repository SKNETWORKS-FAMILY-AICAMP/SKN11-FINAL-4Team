import { NextRequest, NextResponse } from 'next/server'

// 특정 이미지 삭제
export async function DELETE(
  request: NextRequest,
  { params }: { params: { imageId: string } }
) {
  try {
    const imageId = params.imageId
    
    if (!imageId) {
      return NextResponse.json(
        { success: false, error: 'Image ID is required' },
        { status: 400 }
      )
    }

    // 실제 구현에서는 데이터베이스에서 이미지 정보 삭제
    // await deleteImageFromDatabase(imageId)
    
    // ComfyUI 서버에서 이미지 파일 삭제 (선택사항)
    // const comfyUIUrl = process.env.COMFYUI_URL || 'http://localhost:8188'
    // await fetch(`${comfyUIUrl}/delete/${imageId}`, { method: 'DELETE' })

    return NextResponse.json({
      success: true,
      message: 'Image deleted successfully'
    })
  } catch (error) {
    console.error('Error deleting image:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to delete image' 
      },
      { status: 500 }
    )
  }
}

// 특정 이미지 정보 가져오기
export async function GET(
  request: NextRequest,
  { params }: { params: { imageId: string } }
) {
  try {
    const imageId = params.imageId
    
    if (!imageId) {
      return NextResponse.json(
        { success: false, error: 'Image ID is required' },
        { status: 400 }
      )
    }

    // 실제 구현에서는 데이터베이스에서 이미지 정보 가져옴
    // const image = await getImageFromDatabase(imageId)
    
    // 임시 데이터
    const image = {
      id: imageId,
      prompt: 'sample image',
      negative_prompt: '',
      model: 'sd_xl_base_1.0',
      width: 512,
      height: 512,
      steps: 20,
      cfg_scale: 7,
      seed: 123456,
      image_url: `/api/placeholder/512/512`,
      created_at: new Date().toISOString(),
      status: 'completed'
    }

    return NextResponse.json({
      success: true,
      image: image
    })
  } catch (error) {
    console.error('Error fetching image:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to fetch image' 
      },
      { status: 500 }
    )
  }
}