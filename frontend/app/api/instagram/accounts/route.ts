import { NextRequest, NextResponse } from 'next/server'
import { InstagramAPIService } from '@/lib/instagram-business-api'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const accessToken = searchParams.get('access_token')
    const userId = searchParams.get('user_id') || 'me'

    if (!accessToken) {
      return NextResponse.json(
        { error: 'Missing access_token' },
        { status: 400 }
      )
    }

    const instagramService = new InstagramAPIService(accessToken)
    const userInfo = await instagramService.getUserInfo(userId)

    return NextResponse.json({
      success: true,
      data: userInfo
    })
  } catch (error) {
    console.error('Instagram account fetch error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch Instagram account' },
      { status: 500 }
    )
  }
}