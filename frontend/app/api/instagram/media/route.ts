import { NextRequest, NextResponse } from 'next/server'
import { InstagramAPIService } from '@/lib/instagram-business-api'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const accessToken = searchParams.get('access_token')
    const accountId = searchParams.get('account_id')
    const limit = parseInt(searchParams.get('limit') || '25')

    if (!accessToken || !accountId) {
      return NextResponse.json(
        { error: 'Missing access_token or account_id' },
        { status: 400 }
      )
    }

    const instagramService = new InstagramAPIService(accessToken)
    const media = await instagramService.getMedia(accountId, limit)

    return NextResponse.json({
      success: true,
      data: media
    })
  } catch (error) {
    console.error('Instagram media fetch error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch Instagram media' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { accessToken, accountId, imageUrl, caption } = body

    if (!accessToken || !accountId || !imageUrl) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      )
    }

    const instagramService = new InstagramAPIService(accessToken)
    
    // 미디어 컨테이너 생성
    const container = await instagramService.createMediaContainer(accountId, imageUrl, caption)
    
    // 미디어 게시
    const publishResult = await instagramService.publishMedia(accountId, container.id)

    return NextResponse.json({
      success: true,
      data: {
        containerId: container.id,
        mediaId: publishResult.id
      }
    })
  } catch (error) {
    console.error('Instagram media post error:', error)
    return NextResponse.json(
      { error: 'Failed to post Instagram media' },
      { status: 500 }
    )
  }
}