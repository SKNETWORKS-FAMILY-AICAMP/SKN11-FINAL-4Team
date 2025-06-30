import { NextRequest, NextResponse } from 'next/server'
import { InstagramAPIService } from '@/lib/instagram-business-api'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const accessToken = searchParams.get('access_token')
    const accountId = searchParams.get('account_id')
    const mediaId = searchParams.get('media_id')
    const metrics = searchParams.get('metrics')?.split(',') || ['impressions', 'reach', 'profile_views']

    if (!accessToken || (!accountId && !mediaId)) {
      return NextResponse.json(
        { error: 'Missing access_token and account_id or media_id' },
        { status: 400 }
      )
    }

    const instagramService = new InstagramAPIService(accessToken)
    let insights

    if (mediaId) {
      // 미디어 인사이트 조회
      insights = await instagramService.getMediaInsights(mediaId, ['impressions', 'reach', 'engagement'])
    } else if (accountId) {
      // 계정 인사이트 조회
      insights = await instagramService.getAccountInsights(accountId, metrics)
    }

    return NextResponse.json({
      success: true,
      data: insights
    })
  } catch (error) {
    console.error('Instagram insights fetch error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch Instagram insights' },
      { status: 500 }
    )
  }
}