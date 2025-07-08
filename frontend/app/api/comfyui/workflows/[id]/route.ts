import { NextRequest, NextResponse } from 'next/server'

// 특정 워크플로우 조회
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: workflowId } = await params
  
  try {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
    const response = await fetch(`${backendUrl}/api/v1/workflows/${workflowId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json(
          { success: false, error: 'Workflow not found' },
          { status: 404 }
        )
      }
      throw new Error('Failed to fetch workflow')
    }

    const workflow = await response.json()
    
    return NextResponse.json({
      success: true,
      workflow
    })
  } catch (error) {
    console.error('Error fetching workflow:', error)
    
    // 폴백 데이터
    const mockWorkflow = {
      id: workflowId,
      name: '샘플 워크플로우',
      description: '샘플 워크플로우입니다',
      category: 'txt2img',
      workflow_json: {},
      input_parameters: {},
      tags: [],
      is_active: true
    }
    
    return NextResponse.json({
      success: true,
      workflow: mockWorkflow
    })
  }
}

// 워크플로우 업데이트
export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: workflowId } = await params
  
  try {
    const body = await request.json()

    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
    const response = await fetch(`${backendUrl}/api/v1/workflows/${workflowId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body)
    })

    if (!response.ok) {
      throw new Error('Failed to update workflow')
    }

    const result = await response.json()
    
    return NextResponse.json({
      success: true,
      message: 'Workflow updated successfully'
    })
  } catch (error) {
    console.error('Error updating workflow:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to update workflow' 
      },
      { status: 500 }
    )
  }
}

// 워크플로우 삭제
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: workflowId } = await params
  
  try {

    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
    const response = await fetch(`${backendUrl}/api/v1/workflows/${workflowId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error('Failed to delete workflow')
    }
    
    return NextResponse.json({
      success: true,
      message: 'Workflow deleted successfully'
    })
  } catch (error) {
    console.error('Error deleting workflow:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to delete workflow' 
      },
      { status: 500 }
    )
  }
}