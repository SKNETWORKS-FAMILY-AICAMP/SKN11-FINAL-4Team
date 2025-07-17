import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData()
    
    // 백엔드 URL 가져오기
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
    
    // Authorization 헤더 가져오기
    const authorization = request.headers.get('authorization')
    
    // 백엔드로 요청 전송 (FormData는 Content-Type 헤더를 설정하지 않음)
    const response = await fetch(`${backendUrl}/api/v1/influencers/upload-image`, {
      method: 'POST',
      headers: {
        ...(authorization && { 'Authorization': authorization }),
        // FormData를 사용할 때는 Content-Type을 설정하지 않음
        // 브라우저가 자동으로 multipart/form-data로 설정함
      },
      body: formData,
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      return NextResponse.json(
        { error: errorData.detail || '이미지 업로드에 실패했습니다.' },
        { status: response.status }
      )
    }

    const result = await response.json()
    return NextResponse.json(result)
    
  } catch (error) {
    console.error('이미지 업로드 프록시 오류:', error)
    return NextResponse.json(
      { error: '이미지 업로드 중 오류가 발생했습니다.' },
      { status: 500 }
    )
  }
} 