import { NextRequest, NextResponse } from 'next/server'

// SSL 검증 비활성화 (개발 환경용)
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0'

// 워크플로우 목록 조회
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const category = searchParams.get('category')

    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
    const url = new URL('/api/v1/workflows', backendUrl)
    
    if (category) {
      url.searchParams.set('category', category)
    }

    const response = await fetch(url.toString(), {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    })

    let workflows = []
    
    if (response.ok) {
      workflows = await response.json()
    } else {
    }
    
    return NextResponse.json({
      success: true,
      workflows
    })
  } catch (error) {
    console.error('Error fetching workflows:', error)
    
    // 커스텀 템플릿만 사용 - 기본 워크플로우 제거
    const mockWorkflows: any[] = [
      // 커스텀 템플릿만 표시되도록 기본 워크플로우 제거
      // 사용자가 정의한 커스텀 템플릿들만 여기에 표시됩니다
    ]
    
    return NextResponse.json({
      success: true,
      workflows: mockWorkflows
    })
  }
}

// 새 워크플로우 저장
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { name, description, category, workflow_json, input_parameters, tags } = body

    if (!name || !workflow_json) {
      return NextResponse.json(
        { success: false, error: 'Name and workflow_json are required' },
        { status: 400 }
      )
    }

    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
    const response = await fetch(`${backendUrl}/api/v1/workflows`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
        description,
        category,
        workflow_json,
        input_parameters,
        tags,
        created_by: 'user'
      })
    })

    if (!response.ok) {
      throw new Error('Failed to save workflow')
    }

    const result = await response.json()
    
    return NextResponse.json({
      success: true,
      workflow_id: result.workflow_id,
      message: 'Workflow saved successfully'
    })
  } catch (error) {
    console.error('Error saving workflow:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to save workflow' 
      },
      { status: 500 }
    )
  }
}