import { NextRequest, NextResponse } from 'next/server'

// 플레이스홀더 이미지 생성 API
export async function GET(
  request: NextRequest,
  { params }: { params: { width: string; height: string } }
) {
  try {
    const width = parseInt(params.width) || 512
    const height = parseInt(params.height) || 512
    
    // 간단한 SVG 플레이스홀더 이미지 생성
    const svg = `
      <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="#f3f4f6"/>
        <text x="50%" y="50%" text-anchor="middle" dy="0.35em" font-family="Arial, sans-serif" font-size="16" fill="#6b7280">
          ${width} × ${height}
        </text>
        <text x="50%" y="50%" text-anchor="middle" dy="1.8em" font-family="Arial, sans-serif" font-size="12" fill="#9ca3af">
          Placeholder Image
        </text>
      </svg>
    `
    
    return new NextResponse(svg, {
      headers: {
        'Content-Type': 'image/svg+xml',
        'Cache-Control': 'public, max-age=31536000, immutable'
      }
    })
  } catch (error) {
    console.error('Error generating placeholder image:', error)
    return NextResponse.json(
      { success: false, error: 'Failed to generate placeholder image' },
      { status: 500 }
    )
  }
}