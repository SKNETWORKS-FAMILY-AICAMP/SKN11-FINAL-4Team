import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const code = searchParams.get('code')
  const error = searchParams.get('error')

  if (error) {
    return new NextResponse(`
      <script>
        window.opener.postMessage({
          type: 'INSTAGRAM_AUTH_ERROR',
          error: '${error}'
        }, '*');
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
          type: 'INSTAGRAM_AUTH_ERROR',
          error: 'No authorization code received'
        }, '*');
        window.close();
      </script>
    `, {
      headers: { 'Content-Type': 'text/html' }
    })
  }

  // Instagram Authorization code를 받아서 프론트엔드로 전달
  try {
    return new NextResponse(`
      <script>
        console.log('Sending Instagram auth code to parent window');
        window.opener.postMessage({
          type: 'INSTAGRAM_AUTH_SUCCESS',
          code: '${code}'
        }, '*');
        window.close();
      </script>
    `, {
      headers: { 'Content-Type': 'text/html' }
    })
  } catch (error) {
    console.error('Instagram auth error:', error)
    
    return new NextResponse(`
      <script>
        console.log('Sending error message to parent window');
        window.opener.postMessage({
          type: 'INSTAGRAM_AUTH_ERROR',
          error: '${error instanceof Error ? error.message : 'Authentication failed'}'
        }, '*');
        window.close();
      </script>
    `, {
      headers: { 'Content-Type': 'text/html' }
    })
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    
    // 웹훅 검증
    if (body.object === 'instagram') {
      for (const entry of body.entry) {
        // 인스타그램 웹훅 이벤트 처리
        console.log('Instagram webhook received:', entry)
      }
    }
    
    return NextResponse.json({ received: true })
  } catch (error) {
    console.error('Webhook error:', error)
    return NextResponse.json({ error: 'Webhook processing failed' }, { status: 500 })
  }
}