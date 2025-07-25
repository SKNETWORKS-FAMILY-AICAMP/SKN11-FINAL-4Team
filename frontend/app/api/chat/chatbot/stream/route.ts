import { NextRequest } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    // Authorization 헤더에서 Bearer 토큰 추출
    const authorization = request.headers.get('Authorization');
    if (!authorization) {
      return new Response(
        JSON.stringify({ error: 'Authorization header missing' }),
        { 
          status: 401,
          headers: {
            'Content-Type': 'application/json',
          }
        }
      );
    }

    // Bearer 토큰 형식 확인
    if (!authorization.startsWith('Bearer ')) {
      return new Response(
        JSON.stringify({ error: 'Invalid authorization header format' }),
        { 
          status: 401,
          headers: {
            'Content-Type': 'application/json',
          }
        }
      );
    }

    const apiKey = authorization.substring(7); // "Bearer " 제거

    // 백엔드로 스트리밍 요청 전달
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
    const backendResponse = await fetch(`${backendUrl}/api/v1/chat/chatbot/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify(body),
    });

    if (!backendResponse.ok) {
      const errorData = await backendResponse.json().catch(() => ({}));
      return new Response(
        JSON.stringify({ error: errorData.detail || 'Backend request failed' }),
        { 
          status: backendResponse.status,
          headers: {
            'Content-Type': 'application/json',
          }
        }
      );
    }

    // 스트리밍 응답을 그대로 전달
    return new Response(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        ...Object.fromEntries(backendResponse.headers.entries())
      }
    });
  } catch (error) {
    console.error('Chatbot streaming error:', error);
    return new Response(
      JSON.stringify({ error: 'Internal server error' }),
      { 
        status: 500,
        headers: {
          'Content-Type': 'application/json',
        }
      }
    );
  }
} 