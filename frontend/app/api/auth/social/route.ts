import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    const { provider, accessToken, userData } = await request.json()
    
    // 소셜 로그인 성공 후 사용자 데이터 처리
    const user = {
      id: userData.id || userData.sub,
      email: userData.email,
      name: userData.name || userData.given_name + ' ' + userData.family_name,
      provider: provider,
      avatar: userData.picture || userData.profile_image_url,
      // Instagram 비즈니스 정보 추가
      ...(provider === 'instagram' && {
        username: userData.username,
        accountType: userData.accountType,
        mediaCount: userData.mediaCount,
        accessToken: userData.accessToken
      })
    }

    // Instagram 비즈니스 계정 검증
    if (provider === 'instagram') {
      const businessVerification = await verifyInstagramBusiness(userData)
      user.isBusinessVerified = businessVerification.isVerified
      user.businessFeatures = businessVerification.features
    }

    // JWT 토큰 생성 (실제 환경에서는 서버에서 생성)
    const mockToken = generateMockToken(user)
    
    return NextResponse.json({
      success: true,
      token: mockToken,
      user: user
    })
  } catch (error) {
    console.error('Social login error:', error)
    return NextResponse.json(
      { success: false, error: 'Authentication failed' },
      { status: 500 }
    )
  }
}

async function verifyInstagramBusiness(userData: any) {
  try {
    // Instagram Business 계정 타입 확인
    const accountType = userData.accountType || 'PERSONAL'
    const isBusinessAccount = ['BUSINESS', 'CREATOR'].includes(accountType)
    
    // 비즈니스 계정 권한 확인
    const businessFeatures = {
      insights: isBusinessAccount,
      contentPublishing: isBusinessAccount,
      messageManagement: isBusinessAccount,
      commentManagement: true // 모든 계정 타입에서 가능
    }
    
    return {
      isVerified: isBusinessAccount,
      features: businessFeatures,
      accountType: accountType,
      recommendations: isBusinessAccount ? [] : [
        '비즈니스 계정으로 전환하면 인사이트 분석이 가능합니다',
        '크리에이터 계정에서도 고급 기능을 이용할 수 있습니다'
      ]
    }
  } catch (error) {
    console.error('Instagram business verification error:', error)
    return {
      isVerified: false,
      features: {},
      accountType: 'UNKNOWN',
      recommendations: ['계정 정보를 다시 확인해주세요']
    }
  }
}

function generateMockToken(user: any) {
  // 실제 환경에서는 JWT 라이브러리를 사용하여 토큰 생성
  const payload = {
    sub: user.id,
    email: user.email,
    name: user.name,
    provider: user.provider,
    company: user.provider === 'instagram' ? "Instagram Business User" : "Social Login User",
    groups: user.isBusinessVerified ? ["business", "user"] : ["user"],
    permissions: user.isBusinessVerified 
      ? ["post:read", "post:write", "model:read", "model:write", "insights:read", "business:manage"]
      : ["post:read", "model:read"],
    instagram: user.provider === 'instagram' ? {
      username: user.username,
      accountType: user.accountType,
      isBusinessVerified: user.isBusinessVerified,
      businessFeatures: user.businessFeatures
    } : undefined,
    exp: Math.floor(Date.now() / 1000) + (60 * 60 * 24 * 7) // 7일
  }
  
  // 간단한 base64 인코딩 (실제로는 서명된 JWT 사용)
  return 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.' + 
         btoa(JSON.stringify(payload)) + 
         '.mock_signature'
}