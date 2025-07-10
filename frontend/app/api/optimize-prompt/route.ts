import { NextRequest, NextResponse } from 'next/server'

// 프롬프트 최적화 API
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { 
      originalPrompt, 
      style = 'realistic', 
      qualityLevel = 'high',
      aspectRatio = '1:1',
      additionalTags 
    } = body

    if (!originalPrompt) {
      return NextResponse.json(
        { success: false, error: 'Original prompt is required' },
        { status: 400 }
      )
    }

    const backendUrl = process.env.BACKEND_URL || 'http://localhost:9000'
    
    const response = await fetch(`${backendUrl}/api/v1/comfyui/optimize-prompt`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        original_prompt: originalPrompt,
        style: style,
        quality_level: qualityLevel,
        aspect_ratio: aspectRatio,
        additional_tags: additionalTags,
        user_id: null, // 추후 인증 시 사용자 ID 추가
        session_id: `session_${Date.now()}`
      })
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Backend optimization error:', response.status, errorText)
      throw new Error(`Backend error: ${response.status} - ${errorText}`)
    }

    const optimizationResult = await response.json()
    
    return NextResponse.json({
      success: true,
      ...optimizationResult
    })
  } catch (error) {
    console.error('Error optimizing prompt:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to optimize prompt',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    )
  }
}