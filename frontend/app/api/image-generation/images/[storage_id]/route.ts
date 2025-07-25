import { NextRequest, NextResponse } from 'next/server'

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ storage_id: string }> }
) {
  try {
    const { storage_id } = await params
    
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
    const authHeader = request.headers.get('Authorization')
    if (!authHeader) {
      return NextResponse.json(
        { success: false, message: 'Authorization header is required' },
        { status: 401 }
      )
    }

    const response = await fetch(`${backendUrl}/api/v1/image-generation/images/${storage_id}`, {
      method: 'DELETE',
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    })
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(`HTTP error! status: ${response.status}, message: ${errorData.detail || 'Unknown error'}`)
    }
    
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Failed to delete image:', error)
    return NextResponse.json(
      { success: false, message: 'Failed to delete image', error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
} 