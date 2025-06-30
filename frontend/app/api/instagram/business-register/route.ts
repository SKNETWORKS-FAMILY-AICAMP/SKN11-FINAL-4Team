import { NextRequest, NextResponse } from 'next/server'

interface BusinessRegistrationData {
  businessName: string;
  businessCategory: string;
  businessDescription: string;
  contactEmail: string;
  website: string;
  phoneNumber: string;
  businessType: string;
  targetAudience: string;
}

interface InstagramAccountData {
  accessToken: string;
  user: {
    id: string;
    username: string;
    accountType: string;
    name: string;
    email?: string;
    isBusinessVerified?: boolean;
  };
}

export async function POST(request: NextRequest) {
  try {
    const { instagramData, businessInfo }: {
      instagramData: InstagramAccountData;
      businessInfo: BusinessRegistrationData;
    } = await request.json()

    // 필수 필드 검증
    if (!businessInfo.businessName || !businessInfo.businessCategory || !businessInfo.contactEmail) {
      return NextResponse.json(
        { success: false, error: '필수 필드가 누락되었습니다.' },
        { status: 400 }
      )
    }

    if (!instagramData?.user?.id) {
      return NextResponse.json(
        { success: false, error: 'Instagram 계정 정보가 유효하지 않습니다.' },
        { status: 400 }
      )
    }

    // Instagram Business API를 통한 추가 정보 가져오기
    const instagramBusinessData = await getInstagramBusinessInfo(instagramData.accessToken, instagramData.user.id)

    // 데이터베이스에 저장 (현재는 시뮬레이션)
    const registrationResult = await saveBusinessRegistration({
      instagramUserId: instagramData.user.id,
      instagramUsername: instagramData.user.username,
      instagramAccessToken: instagramData.accessToken,
      businessInfo,
      instagramBusinessData,
      registeredAt: new Date().toISOString()
    })

    // 등록 성공 시 추가 권한 및 기능 설정
    const enhancedPermissions = generateEnhancedPermissions(businessInfo, instagramData.user.accountType)

    return NextResponse.json({
      success: true,
      data: {
        registrationId: registrationResult.id,
        businessInfo,
        instagramBusinessData,
        permissions: enhancedPermissions,
        features: getAvailableFeatures(businessInfo.businessCategory, instagramData.user.accountType),
        message: '비즈니스 계정이 성공적으로 등록되었습니다.'
      }
    })

  } catch (error) {
    console.error('Business registration error:', error)
    return NextResponse.json(
      { success: false, error: '비즈니스 등록 중 오류가 발생했습니다.' },
      { status: 500 }
    )
  }
}

async function getInstagramBusinessInfo(accessToken: string, userId: string) {
  try {
    // Instagram Graph API를 사용하여 비즈니스 정보 조회
    const response = await fetch(
      `https://graph.instagram.com/v23.0/${userId}?fields=id,username,name,biography,followers_count,follows_count,media_count,profile_picture_url,website,account_type&access_token=${accessToken}`
    )
    
    const data = await response.json()
    
    if (data.error) {
      console.warn('Instagram Graph API error:', data.error)
      return null
    }

    // 추가 비즈니스 인사이트 정보 (비즈니스 계정만 가능)
    let insightsData = null
    if (data.account_type === 'BUSINESS') {
      try {
        const insightsResponse = await fetch(
          `https://graph.instagram.com/v23.0/${userId}/insights?metric=impressions,reach,profile_views&period=day&access_token=${accessToken}`
        )
        const insights = await insightsResponse.json()
        if (!insights.error) {
          insightsData = insights.data
        }
      } catch (insightsError) {
        console.warn('Failed to fetch insights:', insightsError)
      }
    }

    return {
      followersCount: data.followers_count || 0,
      followingCount: data.follows_count || 0,
      mediaCount: data.media_count || 0,
      biography: data.biography || '',
      profilePictureUrl: data.profile_picture_url,
      websiteUrl: data.website,
      accountType: data.account_type,
      insights: insightsData,
      // Instagram Business API 특화 정보
      businessDiscovery: {
        isBusinessAccount: data.account_type === 'BUSINESS',
        hasBusinessFeatures: ['BUSINESS', 'CREATOR'].includes(data.account_type)
      }
    }
  } catch (error) {
    console.error('Error fetching Instagram business info:', error)
    return null
  }
}

async function saveBusinessRegistration(registrationData: any) {
  // 실제 환경에서는 데이터베이스에 저장
  // 현재는 시뮬레이션으로 고유 ID 반환
  const mockId = `biz_reg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  
  console.log('Business registration saved:', {
    id: mockId,
    ...registrationData
  })

  // 시뮬레이션: 데이터베이스 저장 성공
  return {
    id: mockId,
    status: 'registered',
    createdAt: new Date().toISOString()
  }
}

function generateEnhancedPermissions(businessInfo: BusinessRegistrationData, accountType: string) {
  const basePermissions = ['post:read', 'model:read']
  const businessPermissions = [
    'post:write',
    'model:write', 
    'insights:read',
    'business:manage',
    'comments:manage',
    'messages:manage'
  ]

  // 비즈니스 카테고리별 추가 권한
  const categoryPermissions: { [key: string]: string[] } = {
    'influencer': ['analytics:advanced', 'collaboration:manage'],
    'agency': ['client:manage', 'campaign:create'],
    'brand': ['brand:manage', 'product:showcase'],
    'retail': ['ecommerce:manage', 'inventory:track']
  }

  let permissions = [...basePermissions, ...businessPermissions]

  // 계정 타입이 BUSINESS 또는 CREATOR인 경우 추가 권한
  if (['BUSINESS', 'CREATOR'].includes(accountType)) {
    permissions.push('insights:advanced', 'api:extended')
  }

  // 비즈니스 유형별 권한 추가
  if (categoryPermissions[businessInfo.businessType]) {
    permissions.push(...categoryPermissions[businessInfo.businessType])
  }

  return [...new Set(permissions)] // 중복 제거
}

function getAvailableFeatures(businessCategory: string, accountType: string) {
  const baseFeatures = [
    'content_management',
    'basic_analytics',
    'comment_moderation'
  ]

  const businessFeatures = [
    'advanced_analytics',
    'automated_responses',
    'hashtag_suggestions',
    'competitor_analysis',
    'scheduling',
    'bulk_upload'
  ]

  const premiumFeatures = [
    'ai_content_generation',
    'custom_reports',
    'api_access',
    'white_label'
  ]

  let features = [...baseFeatures]

  // Instagram 비즈니스/크리에이터 계정인 경우
  if (['BUSINESS', 'CREATOR'].includes(accountType)) {
    features.push(...businessFeatures)
  }

  // 특정 비즈니스 카테고리별 추가 기능
  const categoryFeatures: { [key: string]: string[] } = {
    'influencer': ['collaboration_tools', 'brand_partnership'],
    'agency': ['client_dashboard', 'multi_account_management'],
    'brand': ['product_tagging', 'shopping_integration'],
    'ecommerce': ['sales_tracking', 'conversion_analytics']
  }

  if (categoryFeatures[businessCategory]) {
    features.push(...categoryFeatures[businessCategory])
  }

  return features
}

// 등록된 비즈니스 정보 조회
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const instagramUserId = searchParams.get('instagram_user_id')

    if (!instagramUserId) {
      return NextResponse.json(
        { success: false, error: 'Instagram 사용자 ID가 필요합니다.' },
        { status: 400 }
      )
    }

    // 실제 환경에서는 데이터베이스에서 조회
    // 현재는 시뮬레이션
    const mockBusinessData = {
      id: `biz_reg_${instagramUserId}`,
      instagramUserId,
      isRegistered: true,
      registeredAt: new Date().toISOString(),
      businessInfo: {
        businessName: 'Sample Business',
        businessCategory: 'fashion',
        businessType: 'retail'
      }
    }

    return NextResponse.json({
      success: true,
      data: mockBusinessData
    })

  } catch (error) {
    console.error('Error fetching business registration:', error)
    return NextResponse.json(
      { success: false, error: '비즈니스 등록 정보 조회 중 오류가 발생했습니다.' },
      { status: 500 }
    )
  }
}