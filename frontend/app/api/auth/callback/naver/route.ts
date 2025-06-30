import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const code = searchParams.get('code')
  const state = searchParams.get('state')
  const error = searchParams.get('error')

  if (error) {
    return new NextResponse(`
      <script>
        window.opener.postMessage({
          type: 'NAVER_AUTH_ERROR',
          error: '${error}'
        }, '${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'}');
        window.close();
      </script>
    `, {
      headers: { 'Content-Type': 'text/html' }
    })
  }

  if (!code) {
    return new NextResponse(`
      <script>
        window.opener.postMessage({
          type: 'NAVER_AUTH_ERROR',
          error: 'No authorization code received'
        }, '${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'}');
        window.close();
      </script>
    `, {
      headers: { 'Content-Type': 'text/html' }
    })
  }

  try {
    // 액세스 토큰 교환
    const tokenResponse = await fetch('https://nid.naver.com/oauth2.0/token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        client_id: process.env.NAVER_CLIENT_ID || '',
        client_secret: process.env.NAVER_CLIENT_SECRET || '',
        code: code,
        state: state || '',
      }),
    })

    const tokenData = await tokenResponse.json()

    if (!tokenResponse.ok || tokenData.error) {
      throw new Error(tokenData.error_description || 'Token exchange failed')
    }

    // 사용자 정보 가져오기
    const userResponse = await fetch('https://openapi.naver.com/v1/nid/me', {
      headers: {
        'Authorization': `Bearer ${tokenData.access_token}`,
      },
    })

    const userData = await userResponse.json()

    if (!userResponse.ok || userData.resultcode !== '00') {
      throw new Error(userData.message || 'Failed to fetch user data')
    }

    const user = userData.response

    return new NextResponse(`
      <script>
        window.opener.postMessage({
          type: 'NAVER_AUTH_SUCCESS',
          user: {
            id: '${user.id}',
            email: '${user.email}',
            name: '${user.name}',
            profile_image: '${user.profile_image || ''}'
          }
        }, '${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'}');
        window.close();
      </script>
    `, {
      headers: { 'Content-Type': 'text/html' }
    })
  } catch (error) {
    console.error('Naver auth error:', error)
    
    return new NextResponse(`
      <script>
        window.opener.postMessage({
          type: 'NAVER_AUTH_ERROR',
          error: '${error instanceof Error ? error.message : 'Authentication failed'}'
        }, '${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'}');
        window.close();
      </script>
    `, {
      headers: { 'Content-Type': 'text/html' }
    })
  }
}