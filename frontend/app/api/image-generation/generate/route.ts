import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
    const authHeader = request.headers.get('Authorization')
    if (!authHeader) {
      return NextResponse.json(
        { success: false, message: 'Authorization header is required' },
        { status: 401 }
      )
    }

    console.log('Sending request to backend:', {
      url: `${backendUrl}/api/v1/image-generation/generate`,
      body: body,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': authHeader ? 'Bearer ***' : 'None',
      }
    })

    const response = await fetch(`${backendUrl}/api/v1/image-generation/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': authHeader,
      },
      body: JSON.stringify(body),
      cache: 'no-store',
    })
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      console.error('Backend error response:', errorData)
      throw new Error(`HTTP error! status: ${response.status}, message: ${errorData.detail || errorData.message || 'Unknown error'}`)
    }
    
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Failed to generate image:', error)
    return NextResponse.json(
      { success: false, message: 'Failed to generate image', error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
} 