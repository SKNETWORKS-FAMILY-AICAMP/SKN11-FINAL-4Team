import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    // Authorization 헤더에서 Bearer 토큰 추출
    const authorization = request.headers.get('Authorization');
    if (!authorization) {
      return NextResponse.json(
        { error: 'Authorization header missing' },
        { status: 401 }
      );
    }

    // Bearer 토큰 형식 확인
    if (!authorization.startsWith('Bearer ')) {
      return NextResponse.json(
        { error: 'Invalid authorization header format' },
        { status: 401 }
      );
    }

    const apiKey = authorization.substring(7); // "Bearer " 제거

    // 백엔드로 요청 전달
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
    const backendResponse = await fetch(`${backendUrl}/api/v1/chat/chatbot`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify(body),
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || 'Backend request failed' },
        { status: backendResponse.status }
      );
    }

    const data = await backendResponse.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Chatbot error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
} 