import { NextRequest, NextResponse } from 'next/server'

// 테스트용 placeholder 이미지 API
export async function GET(request: NextRequest) {
  try {
    // 더 보기 좋은 SVG placeholder 이미지 생성
    const svg = `
      <svg width="512" height="512" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#4F46E5;stop-opacity:1" />
            <stop offset="100%" style="stop-color:#7C3AED;stop-opacity:1" />
          </linearGradient>
        </defs>
        <rect width="100%" height="100%" fill="url(#grad1)"/>
        <circle cx="256" cy="200" r="80" fill="rgba(255,255,255,0.2)"/>
        <rect x="156" y="300" width="200" height="60" rx="30" fill="rgba(255,255,255,0.3)"/>
        <text x="50%" y="45%" text-anchor="middle" dy=".3em" font-family="Arial, sans-serif" font-size="24" fill="white" font-weight="bold">
          AI Generated Image
        </text>
        <text x="50%" y="55%" text-anchor="middle" dy=".3em" font-family="Arial, sans-serif" font-size="16" fill="rgba(255,255,255,0.8)">
          (Test Mode)
        </text>
        <text x="50%" y="85%" text-anchor="middle" dy=".3em" font-family="Arial, sans-serif" font-size="10" fill="rgba(255,255,255,0.6)">
          ${new Date().toLocaleString()}
        </text>
      </svg>
    `

    return new NextResponse(svg, {
      headers: {
        'Content-Type': 'image/svg+xml',
        'Cache-Control': 'no-cache',
      },
    })
  } catch (error) {
    console.error('Error generating placeholder image:', error)
    return NextResponse.json(
      { success: false, error: 'Failed to generate placeholder image' },
      { status: 500 }
    )
  }
}