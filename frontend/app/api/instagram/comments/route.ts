import { NextRequest, NextResponse } from 'next/server'
import { InstagramAPIService } from '@/lib/instagram-business-api'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const accessToken = searchParams.get('access_token')
    const mediaId = searchParams.get('media_id')

    if (!accessToken || !mediaId) {
      return NextResponse.json(
        { error: 'Missing access_token or media_id' },
        { status: 400 }
      )
    }

    const instagramService = new InstagramAPIService(accessToken)
    const comments = await instagramService.getMediaComments(mediaId)

    return NextResponse.json({
      success: true,
      data: comments
    })
  } catch (error) {
    console.error('Instagram comments fetch error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch Instagram comments' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { accessToken, commentId, message } = body

    if (!accessToken || !commentId || !message) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      )
    }

    const instagramService = new InstagramAPIService(accessToken)
    const reply = await instagramService.replyToComment(commentId, message)

    return NextResponse.json({
      success: true,
      data: reply
    })
  } catch (error) {
    console.error('Instagram comment reply error:', error)
    return NextResponse.json(
      { error: 'Failed to reply to comment' },
      { status: 500 }
    )
  }
}