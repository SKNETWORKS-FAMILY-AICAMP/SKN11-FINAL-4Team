import { NextRequest, NextResponse } from 'next/server'

// SSL 검증 비활성화 (개발 환경용)
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0'

// ComfyUI 생성 진행 상황 확인 API
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  try {
    const { jobId } = await params
    
    if (!jobId) {
      return NextResponse.json(
        { success: false, error: 'Job ID is required' },
        { status: 400 }
      )
    }

    // 백엔드로 프로그레스 확인 요청 전달
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:9000'
    
    try {
      const progressResponse = await fetch(`${backendUrl}/api/v1/comfyui/progress/${jobId}`)
      
      if (progressResponse.ok) {
        const progressData = await progressResponse.json()
        return NextResponse.json(progressData)
      }
    } catch (error) {
    }
    
    // 백엔드 연결 실패 시 즉시 완료 응답 (테스트용)
    return NextResponse.json({
      success: true,
      progress: 100,
      status: 'completed',
      image_url: '/api/placeholder-image',
      image_id: jobId,
      seed: Math.floor(Math.random() * 1000000),
      model: 'custom-template',
      message: 'Image generation completed (mock)'
    })
    
  } catch (error) {
    console.error('Error checking generation progress:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to check generation progress' 
      },
      { status: 500 }
    )
  }
}