import { NextRequest, NextResponse } from 'next/server'

/**
 * 프롬프트 최적화 테스트 API
 * 사용자가 입력한 프롬프트를 OpenAI를 통해 최적화하고 결과를 미리보기로 제공
 */
export async function POST(request: NextRequest) {
  try {
    // 요청 본문 파싱
    const body = await request.json()
    const { prompt, selected_styles } = body

    // 입력 검증
    if (!prompt || typeof prompt !== 'string' || !prompt.trim()) {
      return NextResponse.json(
        { 
          success: false, 
          error: 'prompt is required and must be a non-empty string',
          message: '프롬프트를 입력해주세요.'
        },
        { status: 400 }
      )
    }

    // Authorization 헤더 확인
    const authHeader = request.headers.get('authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return NextResponse.json(
        { 
          success: false, 
          error: 'Authorization header is required',
          message: '인증이 필요합니다.'
        },
        { status: 401 }
      )
    }

    const token = authHeader.substring(7) // "Bearer " 제거

    // 백엔드 URL 설정
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
    
    console.log(`[프롬프트 테스트] 백엔드 호출: ${backendUrl}/api/v1/prompt-test/test-prompt`)
    console.log(`[프롬프트 테스트] 요청 데이터:`, {
      prompt: prompt.substring(0, 100) + (prompt.length > 100 ? '...' : ''),
      selected_styles,
      token: token.substring(0, 20) + '...'
    })

    // 백엔드 API 호출
    const response = await fetch(`${backendUrl}/api/v1/prompt-test/test-prompt`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        prompt: prompt.trim(),
        selected_styles: selected_styles || {}
      })
    })

    console.log(`[프롬프트 테스트] 백엔드 응답 상태: ${response.status}`)

    // 백엔드 응답 처리
    if (!response.ok) {
      const errorText = await response.text()
      console.error(`[프롬프트 테스트] 백엔드 오류: ${response.status} - ${errorText}`)
      
      // 인증 오류 처리
      if (response.status === 401) {
        return NextResponse.json(
          { 
            success: false, 
            error: 'Unauthorized',
            message: '인증에 실패했습니다. 다시 로그인해주세요.'
          },
          { status: 401 }
        )
      }

      // 기타 백엔드 오류 처리
      return NextResponse.json(
        { 
          success: false, 
          error: `Backend error: ${response.status}`,
          message: '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
          details: errorText
        },
        { status: response.status }
      )
    }

    // 성공 응답 처리
    const result = await response.json()
    console.log(`[프롬프트 테스트] 백엔드 응답 데이터:`, {
      success: result.success,
      original_prompt_length: result.original_prompt?.length || 0,
      optimized_prompt_length: result.optimized_prompt?.length || 0,
      character_count: result.character_count,
      estimated_tokens: result.estimated_tokens
    })

    // 응답 데이터 검증 및 포맷팅
    const responseData = {
      success: true,
      original_prompt: result.original_prompt || prompt,
      selected_styles: result.selected_styles || selected_styles || {},
      optimized_prompt: result.optimized_prompt || prompt,
      character_count: result.character_count || result.optimized_prompt?.length || prompt.length,
      estimated_tokens: result.estimated_tokens || Math.ceil((result.optimized_prompt?.length || prompt.length) / 4),
      optimization_method: result.optimization_method || 'OpenAI GPT-4',
      message: result.message || '프롬프트 최적화가 완료되었습니다.'
    }

    return NextResponse.json(responseData)

  } catch (error) {
    console.error('[프롬프트 테스트] API 오류:', error)
    
    // 네트워크 오류나 기타 예외 처리
    return NextResponse.json(
      { 
        success: false, 
        error: 'Internal server error',
        message: '프롬프트 테스트 중 오류가 발생했습니다.',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    )
  }
}

/**
 * GET 요청은 지원하지 않음 (POST만 허용)
 */
export async function GET() {
  return NextResponse.json(
    { 
      success: false, 
      error: 'Method not allowed',
      message: 'POST 요청만 지원됩니다.'
    },
    { status: 405 }
  )
}