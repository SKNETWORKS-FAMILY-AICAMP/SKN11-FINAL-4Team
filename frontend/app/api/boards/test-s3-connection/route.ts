import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  try {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://localhost:8000'
    
    const response = await fetch(`${backendUrl}/api/v1/boards/test-s3-connection`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    const data = await response.json()
    
    return NextResponse.json(data)
  } catch (error) {
    console.error('S3 연결 테스트 오류:', error)
    return NextResponse.json(
      { 
        status: 'error', 
        message: 'S3 연결 확인 중 오류가 발생했습니다.' 
      },
      { status: 500 }
    )
  }
} 