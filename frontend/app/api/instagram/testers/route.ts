import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    const { instagramUserId, accessToken } = await request.json()

    if (!instagramUserId || !accessToken) {
      return NextResponse.json({ 
        error: 'Instagram User ID와 Access Token이 필요합니다' 
      }, { status: 400 })
    }

    // Facebook Graph API를 사용해 테스터 등록
    const response = await fetch(
      `https://graph.facebook.com/v18.0/${process.env.INSTAGRAM_APP_ID}/roles`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user: instagramUserId,
          role: 'testers',
          access_token: accessToken
        })
      }
    )

    const result = await response.json()

    if (!response.ok) {
      throw new Error(result.error?.message || '테스터 등록 실패')
    }

    return NextResponse.json({ 
      success: true, 
      message: '테스터로 등록되었습니다',
      data: result 
    })

  } catch (error) {
    console.error('테스터 등록 오류:', error)
    return NextResponse.json({ 
      error: error instanceof Error ? error.message : '테스터 등록 중 오류가 발생했습니다' 
    }, { status: 500 })
  }
}

export async function GET() {
  try {
    // 현재 테스터 목록 조회
    const response = await fetch(
      `https://graph.facebook.com/v18.0/${process.env.INSTAGRAM_APP_ID}/roles?access_token=${process.env.INSTAGRAM_APP_SECRET}`,
      { method: 'GET' }
    )

    const result = await response.json()

    if (!response.ok) {
      throw new Error(result.error?.message || '테스터 목록 조회 실패')
    }

    return NextResponse.json(result)

  } catch (error) {
    console.error('테스터 목록 조회 오류:', error)
    return NextResponse.json({ 
      error: error instanceof Error ? error.message : '테스터 목록 조회 중 오류가 발생했습니다' 
    }, { status: 500 })
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const userId = searchParams.get('userId')
    const accessToken = searchParams.get('accessToken')

    if (!userId || !accessToken) {
      return NextResponse.json({ 
        error: 'User ID와 Access Token이 필요합니다' 
      }, { status: 400 })
    }

    // 테스터에서 제거
    const response = await fetch(
      `https://graph.facebook.com/v18.0/${process.env.INSTAGRAM_APP_ID}/roles`,
      {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user: userId,
          role: 'testers',
          access_token: accessToken
        })
      }
    )

    const result = await response.json()

    if (!response.ok) {
      throw new Error(result.error?.message || '테스터 제거 실패')
    }

    return NextResponse.json({ 
      success: true, 
      message: '테스터에서 제거되었습니다' 
    })

  } catch (error) {
    console.error('테스터 제거 오류:', error)
    return NextResponse.json({ 
      error: error instanceof Error ? error.message : '테스터 제거 중 오류가 발생했습니다' 
    }, { status: 500 })
  }
}