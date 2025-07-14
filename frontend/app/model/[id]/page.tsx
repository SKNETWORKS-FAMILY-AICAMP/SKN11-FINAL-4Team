"use client"

import { useState, Suspense, useEffect } from "react"
import { AlertCircle } from "lucide-react"
import React from "react"
import { useParams, useSearchParams } from "next/navigation"
import Link from "next/link"
import { Navigation } from "@/components/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { tokenUtils } from "@/lib/auth"
import { ModelService } from "@/lib/services/model.service"
import {
  ArrowLeft,
  Copy,
  Eye,
  EyeOff,
  RefreshCw,
  Download,
  BarChart3,
  Info,
  FileText,
  ExternalLink,
  Calendar,
  Heart,
  MessageCircle,
  Play,
  MoreHorizontal,
  Bookmark,
  Bot,
  Clock,
  Trash2,
  Upload,
  MessageSquare,
  Instagram,
  Link2,
  Unlink,
  CheckCircle,
  Users,
} from "lucide-react"
import type { AIModel } from "@/lib/types"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { apiClient } from "@/lib/api"
import { PostCard, Post } from "@/components/ui/post-card"

// 샘플 모델 데이터
const sampleModel: AIModel = {
  id: "1",
  name: "패션 인플루언서 AI",
  description: "20대 여성 타겟의 패션 트렌드 전문 AI 인플루언서",
  personality: "친근하고 트렌디한",
  tone: "캐주얼하고 친밀한",
  status: "ready",
  createdAt: "2024-01-15",
  apiKey: "ai_inf_1234567890abcdef",
  trainingData: { textSamples: 1500, voiceSamples: 200, imageSamples: 300 },
}

// 샘플 콘텐츠 데이터
type ContentPost = Post


// 게시글 상세 이미지 apiClient 방식 컴포넌트
function PostImage({ url, alt, className }: { url: string; alt?: string; className?: string }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!url) return;
    if (!url.startsWith("/uploads/")) {
      setImageUrl(url);
      return;
    }
    apiClient.get(url, { requireAuth: false }).then((res: any) => {
      if (res.data instanceof Blob) {
        const blobUrl = URL.createObjectURL(res.data);
        setImageUrl(blobUrl);
      } else {
        setImageUrl(url);
      }
    }).catch(() => {
      setImageUrl(url);
    });
    return () => {
      if (imageUrl && imageUrl.startsWith('blob:')) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [url]);
  if (!imageUrl) return <div className="bg-gray-100 w-full h-80 flex items-center justify-center text-gray-400">이미지 불러오는 중...</div>;
  return <img src={imageUrl} alt={alt} className={className} />;
}

function ModelDetailContent() {
  const params = useParams()
  const searchParams = useSearchParams()
  const [model, setModel] = useState<any>(null)
  const [isModelLoading, setIsModelLoading] = useState(true)
  const [posts, setPosts] = useState<ContentPost[]>([])
  const [isPostsLoading, setIsPostsLoading] = useState(true)
  const [selectedPost, setSelectedPost] = useState<ContentPost | null>(null)
  const [isPostDetailModalOpen, setIsPostDetailModalOpen] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)
  const [isUpdating, setIsUpdating] = useState(false)
  const [isGeneratingApiKey, setIsGeneratingApiKey] = useState(false)
  const [apiKeyInfo, setApiKeyInfo] = useState<{
    api_key: string
    created_at: string
    updated_at: string
  } | null>(null)
  const [testMessage, setTestMessage] = useState("")
  const [testResponse, setTestResponse] = useState("")
  const [isTestingChatbot, setIsTestingChatbot] = useState(false)
  const [instagramStatus, setInstagramStatus] = useState<{
    is_connected: boolean
    connected_at?: string
    token_expires_at?: string
    token_expired?: boolean
    instagram_info?: {
      id: string
      username: string
      account_type: string
      name?: string
      biography?: string
      followers_count?: number
      follows_count?: number
      media_count?: number
      profile_picture_url?: string
      website?: string
    }
  }>({
    is_connected: false
  })
  const [isConnecting, setIsConnecting] = useState(false)
  const [analyticsData, setAnalyticsData] = useState({
    totalApiCalls: 0,
    todayApiCalls: 0,
    totalPosts: 0,
    publishedPosts: 0,
    totalLikes: 0,
    totalComments: 0
  })

  // Instagram 상태 변경 시 처리
  React.useEffect(() => {
    // Instagram 상태 업데이트 처리
  }, [instagramStatus])

  // 게시글 데이터 로드
  const loadPostsData = async () => {
    setIsPostsLoading(true)
    try {
      // 특정 인플루언서의 게시글만 조회
      const boardData = await apiClient.get<any[]>(`/api/v1/boards?influencer_id=${params.id}`)

      // 게시글 데이터 변환 (백엔드에서 제공하는 인플루언서 정보 사용)
      const transformedPosts: ContentPost[] = boardData.map((board: any) => {
        // 백엔드에서 이미 제공하는 인플루언서 정보 사용
        const influencerName = board.influencer_name || model?.name || 'AI 인플루언서'
        const influencerDescription = board.influencer_description || model?.description || ''

        const basePost = {
          id: board.board_id,
          title: board.board_topic || '제목 없음',
          content: board.board_description || '',
          platform: getPlatformName(board.board_platform),
          status: getStatusName(board.board_status),
          publishedAt: board.published_at || board.created_at || '',
          scheduledAt: board.reservation_at || '',
          hashtags: board.board_hash_tag ?
            board.board_hash_tag.split(' ').filter((tag: string) => tag.trim()).map((tag: string) =>
              tag.startsWith('#') ? tag : `#${tag}`
            ) : [],
          media: {
            type: "image" as const,
            urls: [board.image_url || "/placeholder.svg?height=400&width=400"],
            thumbnailUrl: board.image_url || "/placeholder.svg?height=400&width=400"
          },
          // 인플루언서 정보: 조회한 값 사용
          influencerId: board.influencer_id,
          influencerName: influencerName,
          influencerDescription: influencerDescription
        }

        // 인스타그램 통계 정보 추가
        const instagramStats = board.instagram_stats || {
          like_count: 0,
          comments_count: 0
        }

        return {
          ...basePost,
          engagement: {
            likes: instagramStats.like_count || 0,
            comments: instagramStats.comments_count || 0
          }
        }
      })

      setPosts(transformedPosts)
    } catch (error) {
      // 에러 시 빈 배열로 설정
      setPosts([])
    } finally {
      setIsPostsLoading(false)
    }
  }

  // 플랫폼 번호를 이름으로 변환
  const getPlatformName = (platformNumber: number) => {
    switch (platformNumber) {
      case 0: return 'Instagram'
      case 1: return 'Blog'
      case 2: return 'Facebook'
      case 3: return 'Twitter'
      case 4: return 'TikTok'
      case 5: return 'YouTube'
      default: return 'Instagram'
    }
  }

  // 상태 번호를 이름으로 변환
  const getStatusName = (statusNumber: number) => {
    switch (statusNumber) {
      case 1: return 'draft' as const     // 임시저장
      case 2: return 'scheduled' as const // 예약됨
      case 3: return 'published' as const // 발행됨
      default: return 'draft' as const
    }
  }

  // 분석 데이터 로드 - 게시글 데이터 기반으로 계산
  const loadAnalyticsData = async () => {
    try {
      // 게시글 데이터가 로드된 후 분석 데이터 계산
      const publishedPosts = posts.filter((p) => p.status === "published")
      setAnalyticsData({
        totalApiCalls: 0, // API 호출 통계는 별도 엔드포인트 필요
        todayApiCalls: 0,
        totalPosts: posts.length,
        publishedPosts: publishedPosts.length,
        totalLikes: publishedPosts.reduce((sum, p) => sum + (p.engagement?.likes || 0), 0),
        totalComments: publishedPosts.reduce((sum, p) => sum + (p.engagement?.comments || 0), 0)
      })
    } catch (error) {
      // 기본값 설정
      setAnalyticsData({
        totalApiCalls: 0,
        todayApiCalls: 0,
        totalPosts: 0,
        publishedPosts: 0,
        totalLikes: 0,
        totalComments: 0
      })
    }
  }

  // 게시글 데이터가 로드된 후 분석 데이터 업데이트
  React.useEffect(() => {
    if (posts.length >= 0) { // 빈 배열도 포함하여 초기 로드 시에도 실행
      loadAnalyticsData()
    }
  }, [posts])

  // 모델 데이터 로드
  const loadModelData = async () => {
    setIsModelLoading(true)
    try {
      console.log('🔍 모델 데이터 로드 시작 - influencer_id:', params.id)
      
      const data = await ModelService.getInfluencer(params.id as string)
      console.log('✅ 모델 데이터 로드 성공:', data)
      
      setModel({
        ...data,
        id: data.influencer_id,
        name: data.influencer_name,
        description: data.influencer_description || '',
        createdAt: data.created_at?.split('T')[0] || '',
        apiKey: sampleModel.apiKey, // API 키는 별도 조회
        trainingData: sampleModel.trainingData, // 훈련 데이터는 별도 조회
        // Instagram 연동 정보 추가
        instagram_id: data.instagram_id,
        instagram_username: data.instagram_username,
        instagram_account_type: data.instagram_account_type,
        instagram_is_active: data.instagram_is_active,
        instagram_connected_at: data.instagram_connected_at,
      })
      
      // API 키 정보 로드
      await loadApiKeyInfo()
    } catch (error) {
      // 에러 처리
      console.error('❌ 모델 데이터 로드 실패:', error)
    } finally {
      setIsModelLoading(false)
    }
  }

  // API 키 정보 로드
  const loadApiKeyInfo = async () => {
    console.log('🔍 API 키 정보 로드 시작 - influencer_id:', params.id)
    
    // 현재 로그인한 사용자 정보 확인
    const token = localStorage.getItem('access_token')
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        console.log('👤 현재 로그인한 사용자:', {
          user_id: payload.sub,
          email: payload.email,
          name: payload.name
        })
      } catch (e) {
        console.log('❌ 토큰 파싱 실패:', e)
      }
    } else {
      console.log('❌ 로그인 토큰이 없습니다')
    }
    
    try {
      const apiKeyData = await ModelService.getApiKey(params.id as string)
      console.log('✅ API 키 조회 성공:', apiKeyData)
      
      setApiKeyInfo({
        api_key: apiKeyData.api_key,
        created_at: apiKeyData.created_at,
        updated_at: apiKeyData.updated_at
      })
      // 모델 상태에 API 키 업데이트
      setModel((prev: any) => ({
        ...prev,
        apiKey: apiKeyData.api_key
      }))
    } catch (error: any) {
      console.error('❌ API 키 조회 실패:', {
        error: error,
        status: error.status,
        detail: error.data?.detail,
        message: error.message,
        influencer_id: params.id,
        stack: error.stack
      })
      
      // API 키가 없는 경우 (404)에만 자동 생성 시도
      if (error.status === 404 && error.data?.detail === "API key not found") {
        console.log('🔄 API 키가 없어서 자동 생성 시도...')
        try {
          const response = await ModelService.generateApiKey(params.id as string)
          console.log('✅ API 키 자동 생성 성공:', response)
          
          setApiKeyInfo({
            api_key: response.api_key,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          })
          // 모델 상태에 API 키 업데이트
          setModel((prev: any) => ({
            ...prev,
            apiKey: response.api_key
          }))
          console.log('API 키가 자동으로 생성되었습니다.')
        } catch (generateError: any) {
          console.error('❌ API 키 자동 생성 실패:', {
            error: generateError,
            status: generateError.status,
            detail: generateError.data?.detail,
            message: generateError.message,
            stack: generateError.stack
          })
          setApiKeyInfo(null)
        }
      } else {
        // 다른 오류 (인플루언서를 찾을 수 없음 등)는 그대로 표시
        console.error('API 키 조회 실패:', error.response?.data?.detail || error.message)
        setApiKeyInfo(null)
      }
    }
  }

  const [activeTab, setActiveTab] = useState(() => {
    // URL 파라미터에서 탭 정보 읽기
    return searchParams.get('tab') || 'analytics'
  })


  const handleUpdateModel = async () => {
    setIsUpdating(true)
    try {
      const updatedData = await ModelService.updateInfluencer(params.id as string, {
        influencer_name: model.name,
      })
      setModel((prev: any) => ({
        ...prev,
        name: updatedData.influencer_name,
        description: updatedData.influencer_description || "",
      }))
      alert("모델 정보가 성공적으로 업데이트되었습니다!")
    } catch (error) {
      alert("모델 정보 업데이트에 실패했습니다. 다시 시도해주세요.")
    } finally {
      setIsUpdating(false)
    }
  }

  const handleDeleteModel = async () => {
    // 실제로는 API 호출로 모델 삭제
    setTimeout(() => {
      // 삭제 후 대시보드로 리다이렉트
      window.location.href = "/dashboard"
    }, 1000)
  }

  const copyApiKey = () => {
    if (model.apiKey) {
      navigator.clipboard.writeText(model.apiKey)
    }
  }

  const generateNewApiKey = async () => {
    setIsGeneratingApiKey(true)
    try {
      const response = await ModelService.generateApiKey(params.id as string)
      setApiKeyInfo({
        api_key: response.api_key,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      })
      // 모델 상태에 API 키 업데이트
      setModel((prev: any) => ({ ...prev, apiKey: response.api_key }))
      alert("새로운 API 키가 성공적으로 생성되었습니다!")
    } catch (error) {
      console.error("API key generation error:", error)
      alert("API 키 생성에 실패했습니다. 다시 시도해주세요.")
    } finally {
      setIsGeneratingApiKey(false)
    }
  }

  const testChatbot = async () => {
    if (!testMessage.trim() || !model.apiKey) {
      alert("메시지를 입력하고 API 키가 있어야 합니다.")
      return
    }

    setIsTestingChatbot(true)
    try {
      const response = await ModelService.callChatbot(model.apiKey, {
        message: testMessage
      })
      setTestResponse(response.response)
    } catch (error: any) {
      console.error("Chatbot test error:", error)
      setTestResponse(`오류: ${error.response?.data?.detail || error.message || '알 수 없는 오류'}`)
    } finally {
      setIsTestingChatbot(false)
    }
  }

  // Instagram 연동 관련 함수들
  const handleInstagramConnect = async () => {
    setIsConnecting(true)

    try {
      // Instagram API with Instagram Login OAuth URL 생성
      const instagramAppId = process.env.NEXT_PUBLIC_INSTAGRAM_APP_ID
      const redirectUri = `${window.location.origin}/auth/instagram/callback`
      // Instagram API with Instagram Login 스코프 설정
      const scope = "instagram_business_basic,instagram_business_manage_messages,instagram_business_manage_comments,instagram_business_content_publish"

      const authUrl = `https://api.instagram.com/oauth/authorize` +
        `?client_id=${instagramAppId}` +
        `&redirect_uri=${encodeURIComponent(redirectUri)}` +
        `&scope=${scope}` +
        `&response_type=code` +
        `&state=${params.id}` // 모델 ID를 state로 전달

      // 팝업 창으로 Instagram OAuth 페이지 열기
      const popup = window.open(
        authUrl,
        'instagram-auth',
        'width=600,height=700,scrollbars=yes,resizable=yes'
      )

      // 팝업에서 메시지를 기다림
      const handleMessage = async (event: MessageEvent) => {
        if (event.origin !== window.location.origin) return

        const { type, code, error, state } = event.data

        if (type === 'INSTAGRAM_AUTH_SUCCESS' && code && state === params.id) {
          popup?.close()
          window.removeEventListener('message', handleMessage)

          try {
            // 백엔드에 code 전송하여 토큰 교환 및 계정 연동
            const data = await ModelService.connectInstagram(params.id as string, {
              code: code,
              redirect_uri: redirectUri
            })

            setInstagramStatus({
              is_connected: true,
              connected_at: new Date().toISOString(),
              token_expired: false,
              instagram_info: data.instagram_info || {
                id: '',
                username: '',
                account_type: '',
              },
            })
            alert('Instagram 비즈니스 계정이 성공적으로 연동되었습니다!')
          } catch (error: any) {
            alert('Instagram 연동에 실패했습니다. 다시 시도해주세요.')
          }

          setIsConnecting(false)
        } else if (type === 'INSTAGRAM_AUTH_ERROR' || error) {
          popup?.close()
          window.removeEventListener('message', handleMessage)
          setIsConnecting(false)
          alert('Instagram 연동이 취소되었거나 오류가 발생했습니다.')
        }
      }

      window.addEventListener('message', handleMessage)

      // 팝업이 닫힌 경우 처리
      const checkClosed = setInterval(() => {
        if (popup?.closed) {
          clearInterval(checkClosed)
          window.removeEventListener('message', handleMessage)
          setIsConnecting(false)
        }
      }, 1000)

    } catch (error) {
      setIsConnecting(false)
      alert('Instagram 연동 중 오류가 발생했습니다.')
    }
  }

  const handleInstagramDisconnect = async () => {
    try {
      // API 호출하여 Instagram 연동 해제
      await ModelService.disconnectInstagram(params.id as string)

      setInstagramStatus({
        is_connected: false
      })
      alert("Instagram 계정 연동이 해제되었습니다.")
    } catch (error) {
      alert("Instagram 연동 해제에 실패했습니다. 다시 시도해주세요.")
    }
  }

  // 컴포넌트 마운트 시 모델 데이터 로드
  React.useEffect(() => {
    const loadData = async () => {
      await loadModelData()
      await loadPostsData()
    }
    loadData()
  }, [params.id])

  // 모델 데이터 로드 후 Instagram 상태 확인
  React.useEffect(() => {
    if (!isModelLoading && model) {
      const checkInstagramStatus = async () => {
        try {
          // 모델 데이터에서 Instagram 정보 확인
          if (model.instagram_is_active) {
            setInstagramStatus({
              is_connected: true,
              connected_at: model.instagram_connected_at,
              instagram_info: {
                id: model.instagram_id || '',
                username: model.instagram_username || '',
                account_type: model.instagram_account_type || '',
              }
            })
          } else {
            // API로 추가 확인 (기존 방식 유지)
            try {
              const data = await ModelService.getInstagramStatus(params.id as string)
              setInstagramStatus({
                is_connected: data.connected,
                instagram_info: data.instagram_username ? {
                  id: '',
                  username: data.instagram_username,
                  account_type: data.instagram_account_type || '',
                } : undefined
              })
            } catch (error) {
              setInstagramStatus({ is_connected: false })
            }
          }
        } catch (error) {
          setInstagramStatus({ is_connected: false })
        }
      }

      checkInstagramStatus()
    }
  }, [isModelLoading, model, params.id])

  // 예약된 게시글이 있을 때 주기적으로 상태 확인 (60초마다)
  React.useEffect(() => {
    const hasScheduledPosts = posts.some(post => post.status === 'scheduled')

    if (hasScheduledPosts) {
      const interval = setInterval(() => {
        loadPostsData() // 예약된 게시글이 있으면 60초마다 새로고침
      }, 60000) // 60초

      return () => clearInterval(interval)
    }
  }, [posts])

  const getStatusBadge = (status: ContentPost["status"]) => {
    switch (status) {
      case "published":
        return <Badge className="bg-green-100 text-green-800">발행됨</Badge>
      case "scheduled":
        return <Badge className="bg-blue-100 text-blue-800">예약됨</Badge>
      case "draft":
        return <Badge className="bg-gray-100 text-gray-800">임시저장</Badge>
      default:
        return <Badge variant="secondary">알 수 없음</Badge>
    }
  }

  const getPlatformBadge = (platform: string) => {
    const colors: Record<string, string> = {
      Instagram: "bg-pink-100 text-pink-800",
      Facebook: "bg-blue-100 text-blue-800",
      Twitter: "bg-sky-100 text-sky-800",
      TikTok: "bg-purple-100 text-purple-800",
      YouTube: "bg-red-100 text-red-800",
      Blog: "bg-orange-100 text-orange-800",
    }

    return <Badge className={colors[platform] || "bg-gray-100 text-gray-800"}>{platform}</Badge>
  }

  const formatDate = (dateString: string) => {
    if (!dateString) return ""
    return new Date(dateString).toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  const formatFullDate = (dateString: string) => {
    if (!dateString) return ""
    const date = new Date(dateString)
    // 유효한 날짜인지 확인
    if (isNaN(date.getTime())) return ""

    // 한국 시간으로 변환 (UTC + 9시간)
    const koreanTime = new Date(date.getTime() + (9 * 60 * 60 * 1000))

    return koreanTime.toLocaleString("ko-KR", {
      year: "numeric",
      month: "long",
      day: "numeric",
      weekday: "long",
      hour: "2-digit",
      minute: "2-digit"
    })
  }

  // 게시글 상세 보기 핸들러
  const handleViewPostDetail = (post: ContentPost) => {
    setSelectedPost(post)
    setIsPostDetailModalOpen(true)
  }

  // 게시글 상세 모달 닫기
  const handleClosePostDetail = () => {
    setSelectedPost(null)
    setIsPostDetailModalOpen(false)
  }

  // 플랫폼별 게시글 렌더링
  const renderPlatformSpecificPost = (post: ContentPost) => {
    switch (post.platform) {
      case "Instagram":
        return (
          <div className="bg-white border rounded-lg overflow-hidden max-w-md mx-auto">
            {/* Instagram 헤더 */}
            <div className="flex items-center justify-between p-3 border-b">
              <div className="flex items-center space-x-3">
                <Avatar className="h-8 w-8">
                  <AvatarFallback className="bg-pink-500 text-white text-xs">AI</AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-semibold text-sm">{model.name}</p>
                  <p className="text-xs text-gray-500">패션 인플루언서</p>
                </div>
              </div>
              <MoreHorizontal className="h-5 w-5 text-gray-600" />
            </div>

            {/* Instagram 이미지/캐러셀 */}
            {post.media && (
              <div className="relative">
                {post.media.type === "carousel" ? (
                  <div className="flex overflow-x-auto snap-x snap-mandatory">
                    {post.media.urls.map((url, index) => (
                      <PostImage key={index} url={url || "/placeholder.svg"} alt={`Slide ${index + 1}`} className="w-full h-80 object-cover flex-shrink-0 snap-start" />
                    ))}
                  </div>
                ) : (
                  <PostImage url={post.media.urls[0] || "/placeholder.svg"} alt="Post image" className="w-full h-80 object-cover" />
                )}
                {post.media.type === "carousel" && (
                  <div className="absolute top-2 right-2 bg-black bg-opacity-50 text-white text-xs px-2 py-1 rounded">
                    1/{post.media.urls.length}
                  </div>
                )}
              </div>
            )}

            {/* Instagram 액션 버튼 */}
            <div className="p-3">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-4">
                  <Heart className="h-6 w-6" />
                  <MessageCircle className="h-6 w-6" />
                </div>
                <Bookmark className="h-6 w-6" />
              </div>

              {/* 좋아요 수 */}
              <p className="font-semibold text-sm mb-2">좋아요 {(post.engagement?.likes || 0).toLocaleString()}개</p>

              {/* 캡션 */}
              <div className="text-sm">
                <span className="font-semibold">{model.name}</span>{" "}
                <span className="whitespace-pre-wrap">{post.content}</span>
              </div>

              {/* 해시태그 */}
              <div className="mt-2">
                {post.hashtags?.map((tag, index) => (
                  <span key={index} className="text-blue-600 text-sm mr-1">
                    {tag}
                  </span>
                ))}
              </div>

              {/* 댓글 보기 */}
              <p className="text-gray-500 text-sm mt-2">댓글 {post.engagement?.comments || 0}개 모두 보기</p>
              <p className="text-gray-400 text-xs mt-1">{formatDate(post.publishedAt || '')}</p>
            </div>
          </div>
        )

      case "Facebook":
        return (
          <div className="bg-white border rounded-lg p-4 max-w-lg mx-auto">
            {/* Facebook 헤더 */}
            <div className="flex items-center space-x-3 mb-3">
              <Avatar className="h-10 w-10">
                <AvatarFallback className="bg-blue-600 text-white">AI</AvatarFallback>
              </Avatar>
              <div className="flex-1">
                <p className="font-semibold text-sm">{model.name}</p>
                <p className="text-xs text-gray-500">{formatDate(post.publishedAt || '')} · 🌍</p>
              </div>
            </div>

            {/* Facebook 텍스트 */}
            <div className="mb-3">
              <p className="text-sm whitespace-pre-wrap">{post.content}</p>
            </div>

            {/* Facebook 이미지 */}
            {post.media && (
              <div className="mb-3">
                <PostImage url={post.media.urls[0] || "/placeholder.svg"} alt="Post image" className="w-full rounded-lg" />
              </div>
            )}

            {/* Facebook 반응 */}
            <div className="border-t pt-2">
              <div className="flex items-center justify-between text-gray-500 text-sm mb-2">
                <span>👍❤️😊 {post.engagement?.likes || 0}</span>
                <span>
                  댓글 {post.engagement?.comments || 0}개
                </span>
              </div>
              <div className="flex items-center justify-around border-t pt-2">
                <button className="flex items-center space-x-1 text-gray-600 hover:bg-gray-100 px-4 py-2 rounded">
                  <Heart className="h-4 w-4" />
                  <span className="text-sm">좋아요</span>
                </button>
                <button className="flex items-center space-x-1 text-gray-600 hover:bg-gray-100 px-4 py-2 rounded">
                  <MessageCircle className="h-4 w-4" />
                  <span className="text-sm">댓글</span>
                </button>

              </div>
            </div>
          </div>
        )

      case "Twitter":
        return (
          <div className="bg-white border rounded-lg p-4 max-w-md mx-auto">
            {/* Twitter 헤더 */}
            <div className="flex items-start space-x-3">
              <Avatar className="h-10 w-10">
                <AvatarFallback className="bg-sky-500 text-white">AI</AvatarFallback>
              </Avatar>
              <div className="flex-1">
                <div className="flex items-center space-x-1">
                  <p className="font-bold text-sm">{model.name}</p>
                  <span className="text-blue-500">✓</span>
                  <p className="text-gray-500 text-sm">@{model.name.replace(/\s+/g, "").toLowerCase()}</p>
                  <span className="text-gray-500">·</span>
                  <p className="text-gray-500 text-sm">{formatDate(post.publishedAt || '')}</p>
                </div>

                {/* Twitter 텍스트 */}
                <div className="mt-2">
                  <p className="text-sm whitespace-pre-wrap">{post.content}</p>
                </div>

                {/* Twitter 이미지 */}
                {post.media && (
                  <div className="mt-3">
                    <PostImage url={post.media.urls[0] || "/placeholder.svg"} alt="Tweet image" className="w-full rounded-2xl border" />
                  </div>
                )}

                {/* Twitter 액션 */}
                <div className="flex items-center justify-between mt-3 max-w-md">
                  <button className="flex items-center space-x-1 text-gray-500 hover:text-blue-500">
                    <MessageCircle className="h-4 w-4" />
                    <span className="text-sm">{post.engagement?.comments || 0}</span>
                  </button>
                  <button className="flex items-center space-x-1 text-gray-500 hover:text-red-500">
                    <Heart className="h-4 w-4" />
                    <span className="text-sm">{post.engagement?.likes || 0}</span>
                  </button>
                  <button className="flex items-center space-x-1 text-gray-500 hover:text-blue-500">
                    <ExternalLink className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )

      case "TikTok":
        return (
          <div className="bg-black rounded-lg overflow-hidden max-w-xs mx-auto">
            {/* TikTok 비디오 영역 */}
            <div className="relative">
              <div className="aspect-[9/16] bg-gray-900 flex items-center justify-center">
                {post.media?.thumbnailUrl ? (
                  <PostImage url={post.media.thumbnailUrl || "/placeholder.svg"} alt="Video thumbnail" className="w-full h-full object-cover" />
                ) : (
                  <div className="text-white text-center">
                    <Play className="h-16 w-16 mx-auto mb-2" />
                    <p className="text-sm">비디오 콘텐츠</p>
                  </div>
                )}
              </div>

              {/* TikTok 사이드 액션 */}
              <div className="absolute right-2 bottom-20 flex flex-col space-y-4">
                <div className="text-center">
                  <div className="w-12 h-12 bg-gray-800 rounded-full flex items-center justify-center mb-1">
                    <Heart className="h-6 w-6 text-white" />
                  </div>
                  <span className="text-white text-xs">{post.engagement?.likes || 0}</span>
                </div>
                <div className="text-center">
                  <div className="w-12 h-12 bg-gray-800 rounded-full flex items-center justify-center mb-1">
                    <MessageCircle className="h-6 w-6 text-white" />
                  </div>
                  <span className="text-white text-xs">{post.engagement?.comments || 0}</span>
                </div>

              </div>

              {/* TikTok 하단 정보 */}
              <div className="absolute bottom-4 left-4 right-16 text-white">
                <p className="font-semibold text-sm mb-1">@{model.name.replace(/\s+/g, "").toLowerCase()}</p>
                <p className="text-sm mb-2">{post.content}</p>
                <div className="flex flex-wrap gap-1">
                  {post.hashtags?.slice(0, 3).map((tag, index) => (
                    <span key={index} className="text-xs">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )

      case "YouTube":
        return (
          <div className="bg-white rounded-lg overflow-hidden max-w-lg mx-auto">
            {/* YouTube 썸네일 */}
            <div className="relative">
              <PostImage url={post.media?.thumbnailUrl || "/placeholder.svg"} alt="Video thumbnail" className="w-full aspect-video object-cover" />
              <div className="absolute inset-0 bg-black bg-opacity-20 flex items-center justify-center">
                <div className="w-16 h-16 bg-red-600 rounded-full flex items-center justify-center">
                  <Play className="h-8 w-8 text-white ml-1" />
                </div>
              </div>
              <div className="absolute bottom-2 right-2 bg-black bg-opacity-80 text-white text-xs px-2 py-1 rounded">
                11:23
              </div>
            </div>

            {/* YouTube 정보 */}
            <div className="p-4">
              <h3 className="font-semibold text-sm mb-2 line-clamp-2">{post.title}</h3>
              <div className="flex items-center space-x-2 mb-2">
                <Avatar className="h-6 w-6">
                  <AvatarFallback className="bg-red-600 text-white text-xs">AI</AvatarFallback>
                </Avatar>
                <p className="text-sm text-gray-600">{model.name}</p>
                <span className="text-red-600 text-xs">✓</span>
              </div>
              <div className="flex items-center space-x-2 text-xs text-gray-500">
                <span>{formatDate(post.publishedAt || '')}</span>
              </div>
              <p className="text-sm text-gray-600 mt-2 line-clamp-2">{post.content}</p>
            </div>
          </div>
        )

      default:
        return (
          <div className="bg-white border rounded-lg p-4">
            <p className="text-sm whitespace-pre-wrap">{post.content}</p>
          </div>
        )
    }
  }

  // 플랫폼별 성과 계산 함수 추가
  const calculatePlatformStats = () => {
    // 모든 플랫폼을 기본으로 설정
    const allPlatforms = ['Instagram', 'Facebook', 'Twitter', 'TikTok', 'YouTube', 'Blog']
    const platformStats: Record<
      string,
      {
        name: string
        posts: number
        totalLikes: number
        totalComments: number
        avgEngagement: number
        color: string
      }
    > = {}

    // 모든 플랫폼을 0으로 초기화
    allPlatforms.forEach((platform) => {
      platformStats[platform] = {
        name: platform,
        posts: 0,
        totalLikes: 0,
        totalComments: 0,
        avgEngagement: 0,
        color: "",
      }
    })

    posts.forEach((post) => {
      if (post.status === "published" && post.platform) {
        if (!platformStats[post.platform]) {
          platformStats[post.platform] = {
            name: post.platform,
            posts: 0,
            totalLikes: 0,
            totalComments: 0,
            avgEngagement: 0,
            color: "",
          }
        }

        const stats = platformStats[post.platform]
        stats.posts += 1
        stats.totalLikes += post.engagement?.likes || 0
        stats.totalComments += post.engagement?.comments || 0
      }
    })

    // 평균 참여율 계산 및 색상 설정
    Object.keys(platformStats).forEach((platform) => {
      const stats = platformStats[platform]
      const totalEngagement = stats.totalLikes + stats.totalComments
      stats.avgEngagement = stats.posts > 0 ? Math.round(totalEngagement / stats.posts) : 0

      // 플랫폼별 색상 설정
      const colors: Record<string, string> = {
        Instagram: "bg-pink-500",
        Facebook: "bg-blue-600",
        Twitter: "bg-sky-500",
        TikTok: "bg-purple-600",
        YouTube: "bg-red-600",
        Blog: "bg-orange-500",
      }
      stats.color = colors[platform] || "bg-gray-500"
    })

    return platformStats
  }

  const platformStats = calculatePlatformStats()

  // model이 null이거나 로딩 중이면 로딩 메시지 표시
  if (isModelLoading || !model) {
    return (
      <div className="flex items-center justify-center min-h-[300px] text-gray-500 text-lg">로딩 중...</div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <Link href="/dashboard" className="inline-flex items-center text-blue-600 hover:text-blue-800 mb-4">
            <ArrowLeft className="h-4 w-4 mr-2" />
            대시보드로 돌아가기
          </Link>
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">{model.name}</h1>
              <p className="text-gray-600 mt-2">{model.description}</p>
              <div className="flex items-center space-x-4 mt-4">
                <Badge className={
                  model.learning_status === 1 ? "bg-green-100 text-green-800" :
                    model.learning_status === 0 ? "bg-yellow-100 text-yellow-800" :
                      "bg-red-100 text-red-800"
                }>
                  {model.learning_status === 1 ? "사용 가능" :
                    model.learning_status === 0 ? "생성 중" :
                      "오류"}
                </Badge>
                <span className="text-sm text-gray-500">생성일: {model.createdAt}</span>
              </div>
            </div>
            <div className="flex space-x-2">
              {model.learning_status === 1 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.open(`/chat/${model.id}`, '_blank')}
                >
                  <MessageSquare className="h-4 w-4 mr-2" />
                  {model.chatbot_option ? "챗봇 페이지 이동" : "챗봇 생성"}
                </Button>
              )}
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive" size="sm">
                    <Trash2 className="h-4 w-4 mr-2" />
                    모델 삭제
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>모델 삭제 확인</AlertDialogTitle>
                    <AlertDialogDescription>
                      "{model.name}" 모델을 완전히 삭제하시겠습니까?
                      <br />
                      <br />
                      <strong>이 작업은 되돌릴 수 없으며, 다음 데이터가 모두 삭제됩니다:</strong>
                      <br />• 모든 게시글 및 콘텐츠
                      <br />• API 키 및 설정
                      <br />• 학습 데이터 및 모델 정보
                      <br />• 분석 데이터 및 통계
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>취소</AlertDialogCancel>
                    <AlertDialogAction onClick={handleDeleteModel} className="bg-red-600 hover:bg-red-700">
                      영구 삭제
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="analytics" className="flex items-center space-x-2">
              <BarChart3 className="h-4 w-4" />
              <span>분석</span>
            </TabsTrigger>
            <TabsTrigger value="content" className="flex items-center space-x-2">
              <FileText className="h-4 w-4" />
              <span>콘텐츠</span>
            </TabsTrigger>
            <TabsTrigger value="api" className="flex items-center space-x-2">
              <Download className="h-4 w-4" />
              <span>API</span>
            </TabsTrigger>
            <TabsTrigger value="integrations" className="flex items-center space-x-2">
              <Link2 className="h-4 w-4" />
              <span>연동</span>
            </TabsTrigger>
            <TabsTrigger value="settings" className="flex items-center space-x-2">
              <Info className="h-4 w-4" />
              <span>정보</span>
            </TabsTrigger>
          </TabsList>

          {/* 분석 탭 */}
          <TabsContent value="analytics">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
              <Card>
                <CardContent className="p-6">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-blue-600">
                      {analyticsData.totalApiCalls.toLocaleString()}
                    </p>
                    <p className="text-sm text-gray-600">총 API 호출</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-orange-600">
                      {analyticsData.todayApiCalls.toLocaleString()}
                    </p>
                    <p className="text-sm text-gray-600">오늘 호출</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-green-600">
                      {analyticsData.publishedPosts.toLocaleString()}
                    </p>
                    <p className="text-sm text-gray-600">발행된 게시글</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-purple-600">
                      {analyticsData.totalLikes.toLocaleString()}
                    </p>
                    <p className="text-sm text-gray-600">총 좋아요</p>
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>사용량 통계</CardTitle>
                <CardDescription>최근 7일간의 API 사용량 추이입니다</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-64 flex items-center justify-center bg-gray-50 rounded-lg">
                  <p className="text-gray-500">차트 영역 (실제 구현시 차트 라이브러리 사용)</p>
                </div>
              </CardContent>
            </Card>

            <Card className="mt-6">
              <CardHeader>
                <CardTitle>플랫폼별 성과 요약</CardTitle>
                <CardDescription>각 소셜미디어 플랫폼별 게시글 성과를 확인하세요</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {Object.values(platformStats).map((stats) => (
                    <div key={stats.name} className="bg-white border rounded-lg p-4">
                      <div className="flex items-center space-x-3 mb-4">
                        <div className={`w-3 h-3 rounded-full ${stats.color}`}></div>
                        <h4 className="font-semibold text-gray-900">{stats.name}</h4>
                        {getPlatformBadge(stats.name)}
                      </div>

                      <div className="space-y-3">
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-600">게시글 수</span>
                          <span className="font-medium">{stats.posts}개</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-600">총 좋아요</span>
                          <span className="font-medium">{stats.totalLikes.toLocaleString()}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-600">총 댓글</span>
                          <span className="font-medium">{stats.totalComments.toLocaleString()}</span>
                        </div>

                        <div className="flex justify-between border-t pt-2">
                          <span className="text-sm text-gray-600">평균 참여</span>
                          <span className="font-semibold text-blue-600">{stats.avgEngagement.toLocaleString()}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>


              </CardContent>
            </Card>
          </TabsContent>

          {/* 콘텐츠 탭 */}
          <TabsContent value="content">
            <div className="space-y-6">
              <div className="flex justify-between items-center">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">최근 게시된 콘텐츠</h3>
                  <p className="text-sm text-gray-600">이 AI 모델이 생성한 게시글 목록입니다</p>
                </div>
              </div>

              {isPostsLoading ? (
                <div className="text-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
                  <p className="text-gray-500 text-lg">게시글을 불러오는 중...</p>
                </div>
              ) : (
                <>
                  <div className="grid gap-4">
                    {posts.map((post) => (
                      <PostCard
                        key={post.id}
                        post={post}
                        onView={handleViewPostDetail}
                        showActions={false}
                        showInfluencerInfo={false}
                        variant="content"
                      />
                    ))}
                  </div>

                  {posts.length === 0 && (
                    <div className="text-center py-12">
                      <FileText className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                      <p className="text-gray-500 text-lg">아직 생성된 콘텐츠가 없습니다</p>
                      <p className="text-gray-400 mt-2">첫 번째 게시글을 작성해보세요!</p>
                      <Link href="/create-post">
                        <Button className="mt-4">
                          <FileText className="h-4 w-4 mr-2" />
                          게시글 작성하기
                        </Button>
                      </Link>
                    </div>
                  )}
                </>
              )}
            </div>
          </TabsContent>

          {/* API 탭 */}
          <TabsContent value="api">
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>API 키 관리</CardTitle>
                  <CardDescription>AI 모델에 접근하기 위한 API 키를 관리합니다</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <Label htmlFor="api-key">API 키</Label>
                    <div className="flex space-x-2">
                      <Input
                        id="api-key"
                        type={showApiKey ? "text" : "password"}
                        value={model.apiKey || ""}
                        readOnly
                        className="font-mono"
                        placeholder={isGeneratingApiKey ? "생성 중..." : "API 키를 불러오는 중..."}
                      />
                      <Button variant="outline" size="icon" onClick={() => setShowApiKey(!showApiKey)}>
                        {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </Button>
                      <Button variant="outline" size="icon" onClick={copyApiKey}>
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                    {apiKeyInfo && (
                      <div className="mt-2 text-xs text-gray-500 space-y-1">
                        <div>생성일: {new Date(apiKeyInfo.created_at).toLocaleDateString('ko-KR')}</div>
                        {apiKeyInfo.updated_at !== apiKeyInfo.created_at && (
                          <div>수정일: {new Date(apiKeyInfo.updated_at).toLocaleDateString('ko-KR')}</div>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex space-x-2">
                    <Button variant="outline" onClick={generateNewApiKey} disabled={isGeneratingApiKey}>
                      {isGeneratingApiKey ? (
                        <>
                          <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                          생성 중...
                        </>
                      ) : (
                        <>
                          <RefreshCw className="h-4 w-4 mr-2" />
                          새 키 생성
                        </>
                      )}
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>API 사용법</CardTitle>
                  <CardDescription>AI 모델을 호출하는 방법을 안내합니다</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div>
                      <Label>엔드포인트</Label>
                      <div className="bg-gray-100 p-3 rounded-md font-mono text-sm">
                        POST https://api.aiinfluencer.com/v1/chat/chatbot
                      </div>
                    </div>
                    <div>
                      <Label>요청 예시</Label>
                      <pre className="bg-gray-100 p-3 rounded-md text-sm overflow-x-auto">
                        {`curl -X POST https://api.aiinfluencer.com/v1/chat/chatbot \\
    -H "Authorization: Bearer ${model.apiKey}" \\
    -H "Content-Type: application/json" \\
    -d '{
      "message": "안녕하세요! 오늘 패션 추천 부탁드려요"
    }'`}
                      </pre>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* 연동 탭 */}
          <TabsContent value="integrations">
            <div className="space-y-6">
              {/* Instagram 계정 연동 */}
              <Card className="bg-white shadow-sm border border-gray-200">
                <CardHeader className="pb-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-12 h-12 bg-pink-100 rounded-lg flex items-center justify-center">
                      <Instagram className="h-6 w-6 text-pink-600" />
                    </div>
                    <div>
                      <CardTitle className="text-lg font-medium text-gray-900">Instagram 계정 연동</CardTitle>
                      <CardDescription className="text-sm text-gray-600 mt-1">
                        비즈니스 계정을 연동하여 AI 콘텐츠 자동 포스팅, 인사이트 분석 등 다양한 기능을 활용하세요.
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-6">
                  {instagramStatus.is_connected ? (
                    <div className="space-y-6">
                      {/* 연동된 계정 정보 */}
                      <div className={`flex items-start space-x-4 p-4 rounded-lg border-2 ${instagramStatus.token_expired
                        ? 'bg-yellow-50 border-yellow-200'
                        : 'bg-green-50 border-green-200'
                        }`}>
                        <div className="w-12 h-12 bg-gradient-to-br from-pink-500 to-purple-600 rounded-full flex items-center justify-center shadow-sm">
                          {instagramStatus.instagram_info?.profile_picture_url ? (
                            <PostImage url={instagramStatus.instagram_info.profile_picture_url} alt="Profile" className="w-12 h-12 rounded-full object-cover" />
                          ) : (
                            <Instagram className="h-6 w-6 text-white" />
                          )}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-1">
                            {instagramStatus.token_expired ? (
                              <AlertCircle className="h-4 w-4 text-yellow-600" />
                            ) : (
                              <CheckCircle className="h-4 w-4 text-green-600" />
                            )}
                            <p className={`font-medium ${instagramStatus.token_expired ? 'text-yellow-900' : 'text-green-900'
                              }`}>
                              {instagramStatus.token_expired ? 'Instagram 계정 재연동 필요' : 'Instagram 계정 연동됨'}
                            </p>
                          </div>
                          <p className={`text-sm ${instagramStatus.token_expired ? 'text-yellow-700' : 'text-green-700'
                            }`}>
                            @{instagramStatus.instagram_info?.username || 'Unknown'} • {instagramStatus.instagram_info?.account_type || 'Unknown'} 계정
                          </p>
                          {instagramStatus.connected_at && (
                            <p className={`text-xs mt-1 ${instagramStatus.token_expired ? 'text-yellow-600' : 'text-green-600'
                              }`}>
                              연동일: {new Date(instagramStatus.connected_at).toLocaleDateString('ko-KR')}
                            </p>
                          )}
                        </div>
                      </div>

                      {/* Instagram 상세 정보 */}
                      {instagramStatus.instagram_info && !instagramStatus.token_expired && (
                        <div className="space-y-4">
                          {/* 통계 정보 */}
                          <div className="grid grid-cols-3 gap-4 p-4 bg-white rounded-lg border border-gray-200">
                            <div className="text-center">
                              <p className="text-lg font-semibold text-gray-900">
                                {(instagramStatus.instagram_info.followers_count || 0).toLocaleString()}
                              </p>
                              <p className="text-xs text-gray-500">팔로워</p>
                            </div>
                            <div className="text-center">
                              <p className="text-lg font-semibold text-gray-900">
                                {(instagramStatus.instagram_info.follows_count || 0).toLocaleString()}
                              </p>
                              <p className="text-xs text-gray-500">팔로잉</p>
                            </div>
                            <div className="text-center">
                              <p className="text-lg font-semibold text-gray-900">
                                {(instagramStatus.instagram_info.media_count || 0).toLocaleString()}
                              </p>
                              <p className="text-xs text-gray-500">게시물</p>
                            </div>
                          </div>

                          {/* 프로필 정보 */}
                          {(instagramStatus.instagram_info.name || instagramStatus.instagram_info.biography || instagramStatus.instagram_info.website) && (
                            <div className="p-4 bg-white rounded-lg border border-gray-200 space-y-3">
                              {instagramStatus.instagram_info.name && (
                                <div>
                                  <p className="text-xs text-gray-500 mb-1">이름</p>
                                  <p className="text-sm font-medium text-gray-900">{instagramStatus.instagram_info.name}</p>
                                </div>
                              )}

                              {instagramStatus.instagram_info.biography && (
                                <div>
                                  <p className="text-xs text-gray-500 mb-1">소개</p>
                                  <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                                    {instagramStatus.instagram_info.biography}
                                  </p>
                                </div>
                              )}

                              {instagramStatus.instagram_info.website && (
                                <div>
                                  <p className="text-xs text-gray-500 mb-1">웹사이트</p>
                                  <a
                                    href={instagramStatus.instagram_info.website}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-sm text-blue-600 hover:text-blue-800 underline"
                                  >
                                    {instagramStatus.instagram_info.website}
                                  </a>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}


                      {/* 활성화된 기능들 */}
                      <div className="space-y-3">
                        <div className="flex items-center space-x-3">
                          <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                          <span className="text-sm font-medium text-gray-900">AI 생성 콘텐츠 자동 포스팅</span>
                        </div>

                        <div className="flex items-center space-x-3">
                          <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                          <span className="text-sm font-medium text-gray-900">인사이트 및 분석 데이터 수집</span>
                        </div>

                        <div className="flex items-center space-x-3">
                          <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                          <span className="text-sm font-medium text-gray-900">광고 및 마케팅 최적화</span>
                        </div>

                        {instagramStatus.instagram_info?.account_type === 'BUSINESS' && (
                          <div className="flex items-center space-x-3">
                            <CheckCircle className="h-5 w-5 text-blue-500 flex-shrink-0" />
                            <span className="text-sm font-medium text-gray-900">비즈니스 전용 고급 인사이트</span>
                          </div>
                        )}
                      </div>


                      {/* 재연동/연동 해제 버튼 */}
                      <div className="pt-2 space-y-3">
                        {instagramStatus.token_expired && (
                          <Button
                            onClick={handleInstagramConnect}
                            disabled={isConnecting}
                            className="w-full bg-yellow-500 hover:bg-yellow-600 text-white font-medium py-2.5"
                          >
                            {isConnecting ? (
                              <>
                                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                                재연동 중...
                              </>
                            ) : (
                              <>
                                <RefreshCw className="h-4 w-4 mr-2" />
                                Instagram 계정 재연동하기
                              </>
                            )}
                          </Button>
                        )}
                        <Button
                          variant="outline"
                          onClick={handleInstagramDisconnect}
                          className="w-full text-red-600 border-red-200 hover:bg-red-50 font-medium py-2.5"
                        >
                          <Unlink className="h-4 w-4 mr-2" />
                          연동 해제
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-6">

                      {/* 기능 리스트 */}
                      <div className="space-y-3">
                        <div className="flex items-center space-x-3">
                          <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                          <span className="text-sm font-medium text-gray-900">AI 생성 콘텐츠 자동 포스팅</span>
                        </div>

                        <div className="flex items-center space-x-3">
                          <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                          <span className="text-sm font-medium text-gray-900">인사이트 및 분석 데이터 수집</span>
                        </div>

                        <div className="flex items-center space-x-3">
                          <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                          <span className="text-sm font-medium text-gray-900">광고 및 마케팅 최적화</span>
                        </div>
                      </div>


                      {/* 연동 버튼 */}
                      <Button
                        onClick={handleInstagramConnect}
                        disabled={isConnecting}
                        className="w-full bg-gradient-to-r from-pink-500 to-purple-600 hover:from-pink-600 hover:to-purple-700 text-white font-medium py-3 text-base"
                      >
                        {isConnecting ? (
                          <>
                            <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                            연동 중...
                          </>
                        ) : (
                          "Instagram 계정 연동하기"
                        )}
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>

            </div>
          </TabsContent>

          {/* 정보 탭 */}
          <TabsContent value="settings">
            <div className="space-y-6">
              {/* 기본 정보 카드 */}
              <Card className="bg-white shadow-sm border border-gray-200">
                <CardHeader className="pb-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                      <Bot className="h-6 w-6 text-blue-600" />
                    </div>
                    <div>
                      <CardTitle className="text-lg font-medium text-gray-900">기본 정보</CardTitle>
                      <CardDescription className="text-sm text-gray-600 mt-1">
                        AI 인플루언서의 프로필 이미지를 설정하고 기본 정보를 수정할 수 있습니다.
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-8">
                  {/* 프로필 이미지와 기본 정보를 가로로 배치 */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {/* 프로필 이미지 섹션 */}
                    <div className="flex flex-col items-center space-y-4">
                      {/* 대형 프로필 이미지 */}
                      <div className="relative">
                        <div className="w-36 h-36 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg">
                          <div className="w-20 h-20 bg-orange-500 rounded-lg flex items-center justify-center">
                            <Bot className="h-10 w-10 text-white" />
                          </div>
                        </div>
                      </div>

                      <div className="text-center space-y-3">
                        <p className="text-sm text-gray-500">권장 크기: 400x400px, 최대 5MB</p>
                        <div className="flex flex-col space-y-2 w-full max-w-xs">
                          <Button variant="outline" size="sm" className="w-full border-gray-300 text-gray-700 hover:bg-gray-50">
                            <Upload className="h-4 w-4 mr-2" />
                            이미지 업로드
                          </Button>
                          <Button variant="outline" size="sm" className="w-full text-red-600 border-red-200 hover:bg-red-50">
                            <Trash2 className="h-4 w-4 mr-2" />
                            제거
                          </Button>
                        </div>
                      </div>
                    </div>

                    {/* 기본 정보 입력 섹션 */}
                    <div className="space-y-6">
                      <div className="space-y-4">
                        <div>
                          <Label htmlFor="model-name" className="text-sm font-medium text-gray-700 mb-2 block">
                            모델 이름
                          </Label>
                          <Input
                            id="model-name"
                            value={isModelLoading ? "로딩 중..." : model.name}
                            onChange={(e) => setModel((prev: any) => ({ ...prev, name: e.target.value }))}
                            placeholder="AI 인플루언서 이름을 입력하세요"
                            className="border-gray-300 focus:border-blue-500 focus:ring-blue-500"
                            disabled={isModelLoading}
                          />
                        </div>
                        <div>
                          <Label htmlFor="model-description" className="text-sm font-medium text-gray-700 mb-2 block">
                            설명
                          </Label>
                          <Textarea
                            id="model-description"
                            value={isModelLoading ? "로딩 중..." : model.description}
                            onChange={(e) => setModel((prev: any) => ({ ...prev, description: e.target.value }))}
                            rows={4}
                            placeholder="AI 인플루언서에 대한 설명을 입력하세요"
                            className="border-gray-300 focus:border-blue-500 focus:ring-blue-500 resize-none"
                            disabled={isModelLoading}
                          />
                        </div>
                      </div>
                      <Button
                        onClick={handleUpdateModel}
                        disabled={isUpdating || isModelLoading}
                        className="w-full bg-gray-800 hover:bg-gray-900 text-white font-medium py-2.5"
                      >
                        {isUpdating ? "업데이트 중..." : isModelLoading ? "로딩 중..." : "정보 저장"}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

            </div>
          </TabsContent>
        </Tabs>

        {/* 게시글 상세 보기 모달 */}
        <Dialog open={isPostDetailModalOpen} onOpenChange={setIsPostDetailModalOpen}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center space-x-2">
                <Eye className="h-5 w-5" />
                <span>게시글 상세 보기</span>
              </DialogTitle>
            </DialogHeader>

            {selectedPost && (
              <div className="space-y-6">
                {/* 게시글 기본 정보 */}
                <div className="flex items-center space-x-3 pb-4 border-b">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <h3 className="font-semibold text-gray-900">{selectedPost.title}</h3>
                      {getStatusBadge(selectedPost.status)}
                      {getPlatformBadge(selectedPost.platform)}
                    </div>
                    {/* 인플루언서 정보 */}
                    <div className="flex items-center space-x-2 text-sm text-gray-500 mt-1">
                      <div className="w-5 h-5 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center">
                        <span className="text-white text-xs font-medium">AI</span>
                      </div>
                      <span className="font-medium text-gray-700">
                        {selectedPost.influencerName || (model?.name || 'AI 인플루언서')}
                      </span>
                      {selectedPost.influencerDescription && (
                        <span className="text-gray-500">
                          • {selectedPost.influencerDescription}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center space-x-2 text-sm text-gray-500 mt-1">
                      <Calendar className="h-4 w-4" />
                      {selectedPost.status === 'scheduled' && selectedPost.scheduledAt && selectedPost.scheduledAt.trim() !== '' ? (
                        <span>예약: {formatDate(selectedPost.scheduledAt || '')}</span>
                      ) : selectedPost.status === 'published' && selectedPost.publishedAt && selectedPost.publishedAt.trim() !== '' ? (
                        <span>발행: {formatDate(selectedPost.publishedAt || '')}</span>
                      ) : selectedPost.status === 'published' ? (
                        <span>발행됨 (날짜 정보 없음)</span>
                      ) : selectedPost.status === 'scheduled' ? (
                        <span>예약됨 (날짜 정보 없음)</span>
                      ) : (
                        <span>임시저장</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* 게시글 내용 */}
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-gray-900">게시글 내용</h4>
                  <div className="bg-gray-50 border rounded-lg p-4">
                    <div className="whitespace-pre-wrap text-gray-800 leading-relaxed">
                      {selectedPost.content}
                    </div>
                  </div>
                </div>

                {/* 해시태그 */}
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-gray-900">해시태그</h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedPost.hashtags?.map((tag, index) => (
                      <span key={index} className="text-sm text-blue-600 bg-blue-50 px-3 py-1 rounded-full">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                {/* 미디어 정보 */}
                {selectedPost.media && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-gray-900">미디어</h4>
                    <div className="bg-gray-50 border rounded-lg p-4">
                      <div className="flex items-center space-x-2 mb-2">
                        <span className="text-sm font-medium text-gray-700">
                          {selectedPost.media.type === "image" && "이미지"}
                          {selectedPost.media.type === "video" && "비디오"}
                          {selectedPost.media.type === "carousel" && "캐러셀"}
                        </span>
                        {selectedPost.media.type === "carousel" && (
                          <Badge variant="outline" className="text-xs">
                            {selectedPost.media.urls.length}개 파일
                          </Badge>
                        )}
                      </div>
                      {selectedPost.media.thumbnailUrl && (
                        <div className="mt-2">
                          <img
                            src={selectedPost.media.thumbnailUrl}
                            alt="미디어 썸네일"
                            className="w-32 h-32 object-cover rounded-lg border"
                          />
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 성과 지표 */}
                {selectedPost.status === "published" && selectedPost.engagement && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-gray-900">성과 지표</h4>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="text-center">
                          <div className="flex items-center justify-center space-x-2 mb-1">
                            <Heart className="h-5 w-5 text-red-500" />
                            <span className="text-lg font-bold text-gray-900">
                              {selectedPost.engagement.likes.toLocaleString()}
                            </span>
                          </div>
                          <p className="text-sm text-gray-600">좋아요</p>
                        </div>
                        <div className="text-center">
                          <div className="flex items-center justify-center space-x-2 mb-1">
                            <MessageCircle className="h-5 w-5 text-blue-500" />
                            <span className="text-lg font-bold text-gray-900">
                              {selectedPost.engagement.comments.toLocaleString()}
                            </span>
                          </div>
                          <p className="text-sm text-gray-600">댓글</p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 플랫폼별 미리보기 */}
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-gray-900">플랫폼 미리보기</h4>
                  <div className="bg-gray-50 border rounded-lg p-4">
                    {renderPlatformSpecificPost(selectedPost)}
                  </div>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}

export default function ModelDetailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <div className="max-w-6xl mx-auto p-8">
          <div className="animate-pulse">
            <div className="h-8 bg-gray-200 rounded w-64 mb-6"></div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div className="lg:col-span-2">
                <div className="h-96 bg-gray-200 rounded-lg"></div>
              </div>
              <div>
                <div className="h-64 bg-gray-200 rounded-lg"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    }>
      <ModelDetailContent />
    </Suspense>
  )
}

