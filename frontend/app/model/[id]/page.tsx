"use client"

import { useState, Suspense, useEffect, useRef } from "react"
import { AlertCircle } from "lucide-react"
import React from "react"
import { useParams, useSearchParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Navigation } from "@/components/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

import { tokenUtils } from "@/lib/auth"
import { ModelService } from "@/lib/services/model.service"
import { useToast } from "@/hooks/use-toast"
import { Toaster } from "@/components/ui/toaster"
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
  Edit,
  User,
  Settings,
  Mic,
  Volume2,
  PlayCircle,
  PauseCircle,
  Loader2,
  ImageIcon,
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
  const router = useRouter()
  const { toast } = useToast()
  const [model, setModel] = useState<any>(null)
  const [isModelLoading, setIsModelLoading] = useState(true)
  const [posts, setPosts] = useState<ContentPost[]>([])
  const [isPostsLoading, setIsPostsLoading] = useState(true)
  const [selectedPost, setSelectedPost] = useState<ContentPost | null>(null)
  const [isPostDetailModalOpen, setIsPostDetailModalOpen] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [isUploadingImage, setIsUploadingImage] = useState(false)
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [editHashtags, setEditHashtags] = useState("");
  const [editScheduledAt, setEditScheduledAt] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const [uploadedImage, setUploadedImage] = useState<File | null>(null)
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
  
  // 음성 관련 상태
  const [voiceText, setVoiceText] = useState("")
  const [isGeneratingVoice, setIsGeneratingVoice] = useState(false)
  const [voiceHistory, setVoiceHistory] = useState<Array<{
    id: string
    text: string
    url: string
    s3_url?: string
    duration?: number
    createdAt: string
    status?: string  // pending, completed, failed
  }>>([])
  const [isLoadingVoiceHistory, setIsLoadingVoiceHistory] = useState(false)
  const previousVoiceStatusRef = useRef<Map<string, string>>(new Map())
  const [playingVoiceUrl, setPlayingVoiceUrl] = useState<string | null>(null)
  const [baseVoiceFile, setBaseVoiceFile] = useState<File | null>(null)
  const [baseVoiceUrl, setBaseVoiceUrl] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [isUploadingBaseVoice, setIsUploadingBaseVoice] = useState(false)
  const [hasBaseVoice, setHasBaseVoice] = useState(false)
  const [isImageModalOpen, setIsImageModalOpen] = useState(false)
  const [isGalleryModalOpen, setIsGalleryModalOpen] = useState(false)
  const [galleryImages, setGalleryImages] = useState<string[]>([])
  const [isLoadingGallery, setIsLoadingGallery] = useState(false)
  const [hasImageChanges, setHasImageChanges] = useState(false)
  const [voiceToDelete, setVoiceToDelete] = useState<string | null>(null)
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

  // 7일간 API 호출수 차트 데이터
  const [weeklyChartData, setWeeklyChartData] = useState<Array<{
    date: string;
    calls: number;
  }>>([])

  // 7일간 API 호출수 데이터 로드
  const loadWeeklyChartData = async () => {
    try {
      const apiUsageResponse = await apiClient.get(`/api/v1/analytics/api-calls/`) as any

      // 특정 인플루언서의 API 호출 데이터 필터링
      const influencerApiCalls = apiUsageResponse.filter((call: any) =>
        call.influencer_id === params.id?.toString()
      )

      // 최근 7일간 데이터 생성
      const last7Days = []
      for (let i = 6; i >= 0; i--) {
        const date = new Date()
        date.setDate(date.getDate() - i)
        const dateStr = date.toISOString().split('T')[0]

        // 해당 날짜의 API 호출수 찾기
        const dayCalls = influencerApiCalls
          .filter((call: any) => call.created_at?.startsWith(dateStr))
          .reduce((sum: number, call: any) => sum + (call.daily_call_count || 0), 0)

        last7Days.push({
          date: dateStr,
          calls: dayCalls
        })
      }

      setWeeklyChartData(last7Days)
    } catch (error) {
      console.error('7일간 차트 데이터 로드 실패:', error)
      setWeeklyChartData([])
    }
  }

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
          influencerDescription: influencerDescription,
          // Instagram 링크 추가
          instagram_link: board.instagram_link || undefined
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

      // API 사용량 데이터 가져오기
      let apiUsageData = {
        totalApiCalls: 0,
        todayApiCalls: 0
      }

      try {
        // 올바른 analytics API 호출
        const apiUsageResponse = await apiClient.get(`/api/v1/analytics/api-calls/`) as any


        // 특정 인플루언서의 API 호출 데이터 필터링
        const influencerApiCalls = apiUsageResponse.filter((call: any) =>
          call.influencer_id === params.id?.toString()
        )


        // 총 API 호출 수와 오늘 호출 수 계산
        const totalCalls = influencerApiCalls.reduce((sum: number, call: any) =>
          sum + (call.daily_call_count || 0), 0
        )

        // 오늘 날짜의 호출 수 계산
        const today = new Date().toISOString().split('T')[0]
        const todayCalls = influencerApiCalls
          .filter((call: any) => call.created_at?.startsWith(today))
          .reduce((sum: number, call: any) => sum + (call.daily_call_count || 0), 0)

        apiUsageData = {
          totalApiCalls: totalCalls,
          todayApiCalls: todayCalls
        }

      } catch (error) {
        // 오류 발생 시 기본값 사용
        apiUsageData = {
          totalApiCalls: 0,
          todayApiCalls: 0
        }
      }

      setAnalyticsData({
        ...apiUsageData,
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
      loadWeeklyChartData() // 7일간 차트 데이터도 함께 로드
    }
  }, [posts])

  // 모델 데이터 로드
  const loadModelData = async () => {
    setIsModelLoading(true)
    try {

      const data = await ModelService.getInfluencer(params.id as string)

      // 이미지 URL 처리: S3 키인 경우 URL로 변환
      let processedImageUrl = data.image_url
      if (data.image_url && !data.image_url.startsWith('http')) {
        // S3 키인 경우 직접 URL 생성
        processedImageUrl = `https://aimex-influencers.s3.ap-northeast-2.amazonaws.com/${data.image_url}`
      } else if (data.image_url && data.image_url.startsWith('http')) {
        // 이미 URL인 경우 그대로 사용
        processedImageUrl = data.image_url
      } else {
      }

      setModel({
        ...data,
        id: data.influencer_id,
        name: data.influencer_name,
        description: data.influencer_description || '',
        image_url: processedImageUrl, // 처리된 이미지 URL
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

    // 현재 로그인한 사용자 정보 확인
    const token = localStorage.getItem('access_token')
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        
      } catch (e) {
      }
    } else {
    }

    try {
      const apiKeyData = await ModelService.getApiKey(params.id as string)

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
        try {
          const response = await ModelService.generateApiKey(params.id as string)

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
        } catch (generateError: any) {
          
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


  // 이미지 파일 처리 공통 함수
  const processImageFile = async (file: File) => {
    // 이미지 파일 검증
    if (!file.type.startsWith('image/')) {
      toast({
        title: "파일 형식 오류",
        description: "이미지 파일만 업로드할 수 있습니다.",
        variant: "destructive",
      })
      return
    }

    // 파일 크기 제한 (5MB)
    if (file.size > 5 * 1024 * 1024) {
      toast({
        title: "파일 크기 오류",
        description: "이미지 파일 크기는 5MB 이하여야 합니다.",
        variant: "destructive",
      })
      return
    }

    try {
      setUploadedImage(file)

      // 이미지 미리보기 생성
      const reader = new FileReader()
      reader.onload = (e) => {
        setImagePreview(e.target?.result as string)
        setHasImageChanges(true) // 이미지 변경 감지
      }
      reader.readAsDataURL(file)
    } catch (error) {
      toast({
        title: "이미지 처리 오류",
        description: "이미지 처리 중 오류가 발생했습니다.",
        variant: "destructive",
      })
      console.error('Image processing error:', error)
    }
  }

  // 이미지 업로드 처리
  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      await processImageFile(file)
    }
  }

  // 드래그 앤 드롭 이벤트 처리
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)

    const files = e.dataTransfer.files
    if (files && files[0]) {
      await processImageFile(files[0])
    }
  }

  // 이미지 제거
  const removeImage = () => {
    setUploadedImage(null)
    setImagePreview(null)
    setHasImageChanges(false) // 이미지 제거 시 변경 상태 초기화
    
    // 파일 입력 초기화
    const fileInput = document.getElementById('modal-image-upload') as HTMLInputElement
    if (fileInput) {
      fileInput.value = ''
    }
  }

  const openImageModal = () => {
    setIsImageModalOpen(true)
  }

  const openGalleryModal = async () => {
    setIsGalleryModalOpen(true)
    await loadGalleryImages()
  }

  const loadGalleryImages = async () => {
    setIsLoadingGallery(true)
    try {
      // S3에서 이미지 목록을 가져오는 API 호출
      const response = await apiClient.get('/api/v1/gallery/images')
      setGalleryImages(Array.isArray(response) ? response : [])
    } catch (error) {
      console.error('갤러리 이미지 로드 실패:', error)
      toast({
        title: "갤러리 로드 실패",
        description: "이미지 목록을 불러오는데 실패했습니다.",
        variant: "destructive",
      })
    } finally {
      setIsLoadingGallery(false)
    }
  }

  const selectGalleryImage = (imageUrl: string) => {
    // 선택된 이미지를 프로필 이미지로 설정
    setModel((prev: any) => ({
      ...prev,
      image_url: imageUrl
    }))
    setHasImageChanges(true) // 이미지 변경 감지
    setIsGalleryModalOpen(false)
    toast({
      title: "이미지 선택 완료",
      description: "갤러리에서 이미지를 선택했습니다.",
      variant: "default",
    })
  }

  const handleUpdateModel = async () => {
    setIsUpdating(true)
    try {
      let imageUrl = null

      // 이미지가 업로드된 경우 S3에 업로드
      if (uploadedImage) {
        setIsUploadingImage(true)
        try {
          const formData = new FormData()
          formData.append('file', uploadedImage)
          formData.append('influencer_id', params.id?.toString() ?? '')

          const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
          const response = await fetch(`${backendUrl}/api/v1/influencers/upload-image`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: formData
          })

          if (response.ok) {
            const result = await response.json()
            imageUrl = result.file_url
          } else {
          }
        } catch (error) {
        } finally {
          setIsUploadingImage(false)
        }
      }

      // 인플루언서 정보 업데이트
      const updateData: any = {
        influencer_name: model.name,
        influencer_description: model.description
      }

      // 이미지 URL이 있는 경우 추가
      if (imageUrl) {
        updateData.image_url = imageUrl
      }

      const updatedData = await ModelService.updateInfluencer(params.id?.toString() ?? '', updateData)
      setModel((prev: any) => ({
        ...prev,
        name: updatedData.influencer_name,
        description: updatedData.influencer_description || "",
        image_url: updatedData.image_url || prev.image_url
      }))

      // 이미지 업로드 후 상태 초기화
      if (uploadedImage) {
        setUploadedImage(null)
        setImagePreview(null)
      }
      setHasImageChanges(false) // 변경 상태 초기화

      // 모델 데이터 다시 로드하여 변경사항 반영
      await loadModelData()

      // 성공 토스트 표시
      toast({
        title: "성공",
        description: "모델 정보가 성공적으로 업데이트되었습니다!",
        variant: "default",
      })

      // 페이지 새로고침 없이 UI 업데이트
      setModel((prev: any) => ({
        ...prev,
        name: updatedData.influencer_name,
        description: updatedData.influencer_description || "",
        image_url: updatedData.image_url || prev.image_url
      }))

      // 현재 페이지로 리다이렉트 (새로고침)
      let influencerId: string | undefined;
      if (typeof params.id === 'string') {
        influencerId = params.id;
      } else if (Array.isArray(params.id)) {
        influencerId = params.id[0];
      }
      router.replace(influencerId ? `/model/${influencerId}` : '/dashboard');
    } catch (error) {
      // 실패 토스트 표시
      toast({
        title: "오류",
        description: "모델 정보 업데이트에 실패했습니다. 다시 시도해주세요.",
        variant: "destructive",
      })
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

  const copyApiKey = async () => {
    if (!model.apiKey) {
      toast({
        title: "API 키 없음",
        description: "복사할 API 키가 없습니다.",
        variant: "destructive",
      })
      return
    }

    try {
      await navigator.clipboard.writeText(model.apiKey)
      toast({
        title: "API 키 복사 완료",
        description: "API 키가 클립보드에 복사되었습니다!",
        variant: "default",
      })
    } catch (error) {
      console.error("API key copy error:", error)
      toast({
        title: "복사 실패",
        description: "API 키 복사에 실패했습니다. 수동으로 복사해주세요.",
        variant: "destructive",
      })
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
      toast({
        title: "API 키 생성 완료",
        description: "새로운 API 키가 성공적으로 생성되었습니다!",
        variant: "default",
      })
    } catch (error) {
      console.error("API key generation error:", error)
      toast({
        title: "API 키 생성 실패",
        description: "API 키 생성에 실패했습니다. 다시 시도해주세요.",
        variant: "destructive",
      })
    } finally {
      setIsGeneratingApiKey(false)
    }
  }

  const testChatbot = async () => {
    if (!testMessage.trim() || !model.apiKey) {
      toast({
        title: "입력 오류",
        description: "메시지를 입력하고 API 키가 있어야 합니다.",
        variant: "destructive",
      })
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

  const handleChatbotToggle = async () => {
    try {
      // 챗봇 옵션 토글 (true -> false, false -> true)
      const newChatbotOption = !model.chatbot_option
      
      // 백엔드 API 호출하여 chatbot_option 업데이트
      await ModelService.updateInfluencer(params.id as string, {
        chatbot_option: newChatbotOption
      })
      
      // 로컬 상태 업데이트
      setModel((prev: any) => ({
        ...prev,
        chatbot_option: newChatbotOption
      }))
      
      if (newChatbotOption) {
        toast({
          title: "챗봇 활성화",
          description: "챗봇이 활성화되었습니다!",
          variant: "default",
        })
      } else {
        toast({
          title: "챗봇 비활성화",
          description: "챗봇이 비활성화되었습니다.",
          variant: "default",
        })
      }
    } catch (error: any) {
      console.error("Chatbot toggle error:", error)
      toast({
        title: "오류",
        description: "챗봇 상태 변경에 실패했습니다.",
        variant: "destructive",
      })
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
            toast({
              title: "Instagram 연동 완료",
              description: "Instagram 비즈니스 계정이 성공적으로 연동되었습니다!",
              variant: "default",
            })
          } catch (error: any) {
            toast({
              title: "Instagram 연동 실패",
              description: "Instagram 연동에 실패했습니다. 다시 시도해주세요.",
              variant: "destructive",
            })
          }

          setIsConnecting(false)
        } else if (type === 'INSTAGRAM_AUTH_ERROR' || error) {
          popup?.close()
          window.removeEventListener('message', handleMessage)
          setIsConnecting(false)
          toast({
            title: "Instagram 연동 취소",
            description: "Instagram 연동이 취소되었거나 오류가 발생했습니다.",
            variant: "destructive",
          })
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
      toast({
        title: "Instagram 연동 오류",
        description: "Instagram 연동 중 오류가 발생했습니다.",
        variant: "destructive",
      })
    }
  }

  const handleInstagramDisconnect = async () => {
    try {
      // API 호출하여 Instagram 연동 해제
      await ModelService.disconnectInstagram(params.id as string)

      setInstagramStatus({
        is_connected: false
      })
      toast({
        title: "Instagram 연동 해제",
        description: "Instagram 계정 연동이 해제되었습니다.",
        variant: "default",
      })
    } catch (error) {
      toast({
        title: "Instagram 연동 해제 실패",
        description: "Instagram 연동 해제에 실패했습니다. 다시 시도해주세요.",
        variant: "destructive",
      })
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
  // 컴포넌트 언마운트 시 오디오 정리
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
    }
  }, [])

  React.useEffect(() => {
    if (!isModelLoading && model) {
      // 베이스 음성 확인
      checkBaseVoice()
      
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

  // 예약된 게시글이 있을 때 주기적으로 상태 확인 (30초마다)
  // 음성 탭이 선택되었을 때 음성 히스토리 로드
  React.useEffect(() => {
    if (activeTab === 'voice' && !isLoadingVoiceHistory) {
      loadVoiceHistory()
    }
  }, [activeTab])

  // pending 상태의 음성이 있을 때 주기적으로 상태 확인 (3초마다)
  React.useEffect(() => {
    // 현재 상태를 ref에 저장
    voiceHistory.forEach(voice => {
      if (voice.id && voice.status) {
        previousVoiceStatusRef.current.set(voice.id, voice.status)
      }
    })
    
    const hasPendingVoices = voiceHistory.some(voice => voice.status === 'pending')
    
    if (hasPendingVoices && activeTab === 'voice') {
      const interval = setInterval(async () => {
        
        // 음성 목록 다시 로드
        const response = await apiClient.get<any[]>(`/api/v1/influencers/${params.id}/voices`)
        
        if (Array.isArray(response)) {
          const updatedVoices = response.map((voice: any) => ({
            id: voice.id,
            text: voice.text,
            url: voice.url || voice.s3_url,
            duration: voice.duration,
            createdAt: voice.createdAt || voice.created_at,
            status: voice.status || 'completed',
            task_id: voice.task_id
          }))
          
          // 새로 완료된 음성 찾기
          const newlyCompletedVoices = updatedVoices.filter(voice => {
            const previousStatus = previousVoiceStatusRef.current.get(voice.id)
            return previousStatus === 'pending' && voice.status === 'completed'
          })
          
          // 새로 실패한 음성 찾기
          const newlyFailedVoices = updatedVoices.filter(voice => {
            const previousStatus = previousVoiceStatusRef.current.get(voice.id)
            return previousStatus === 'pending' && voice.status === 'failed'
          })
          
          // 상태 업데이트
          setVoiceHistory(updatedVoices)
          
          // 알림 표시
          if (newlyCompletedVoices.length > 0) {
            toast({
              title: "음성 생성 완료",
              description: `${newlyCompletedVoices.length}개의 음성이 성공적으로 생성되었습니다.`,
            })
            
            // 첫 번째 완료된 음성 자동 재생 (선택사항)
            if (newlyCompletedVoices[0]?.url) {
              handlePlayVoice(newlyCompletedVoices[0].url)
            }
          }
          
          if (newlyFailedVoices.length > 0) {
            toast({
              title: "음성 생성 실패",
              description: `${newlyFailedVoices.length}개의 음성 생성에 실패했습니다.`,
              variant: "destructive",
            })
          }
        }
      }, 3000) // 3초마다 확인
      
      return () => clearInterval(interval)
    }
  }, [voiceHistory, activeTab, params.id])

  React.useEffect(() => {
    const hasScheduledPosts = posts.some(post => post.status === 'scheduled')

    if (hasScheduledPosts) {
      const interval = setInterval(async () => {
        await loadPostsData() // 예약된 게시글이 있으면 30초마다 새로고침

        // 상태 변경 감지
        const updatedPosts = await apiClient.get<any[]>(`/api/v1/boards?influencer_id=${params.id}`)
        const transformedPosts: ContentPost[] = updatedPosts.map((board: any) => {
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
            influencerId: board.influencer_id,
            influencerName: influencerName,
            influencerDescription: influencerDescription,
            instagram_link: board.instagram_link || undefined
          }

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

        // 상태 변경 감지 및 로그
        const currentPostIds = new Set(posts.map(p => p.id))
        const updatedPostIds = new Set(transformedPosts.map(p => p.id))

        // 새로 발행된 게시글 감지
        const newlyPublished = transformedPosts.filter(post =>
          post.status === 'published' &&
          posts.find(p => p.id === post.id)?.status === 'scheduled'
        )

        if (newlyPublished.length > 0) {
          setPosts(transformedPosts)
          await loadAnalyticsData() // 분석 데이터도 갱신

          // 사용자에게 알림 (선택사항)
          if (newlyPublished.length === 1) {
          } else {
          }
        }

      }, 30000) // 30초로 단축

      return () => clearInterval(interval)
    }
  }, [posts, params.id, model])

  const getStatusBadge = (status: ContentPost["status"]) => {
    switch (status) {
      case "published":
        return <Badge className="bg-green-100 text-green-800 whitespace-nowrap">발행됨</Badge>
      case "scheduled":
        return <Badge className="bg-blue-100 text-blue-800 whitespace-nowrap">예약됨</Badge>
      case "draft":
        return <Badge className="bg-gray-100 text-gray-800 whitespace-nowrap">임시저장</Badge>
      default:
        return <Badge variant="secondary" className="whitespace-nowrap">알 수 없음</Badge>
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

    return <Badge className={`${colors[platform] || "bg-gray-100 text-gray-800"} whitespace-nowrap`}>{platform}</Badge>
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
    setIsEditing(false)
    setEditTitle(post.title || "")
    setEditContent(post.content || "")
    setEditHashtags((post.hashtags || []).join(" "))
    setEditScheduledAt(post.scheduledAt || "")
  }

  // 게시글 상세 모달 닫기
  const handleClosePostDetail = () => {
    setSelectedPost(null)
    setIsPostDetailModalOpen(false)
  }

  // 게시글 수정 저장
  const handleEditSave = async () => {
    if (!selectedPost || isSaving) return;

    const originalTitle = selectedPost.title || "게시글"
    const hasChanges = editTitle !== originalTitle ||
      editContent !== (selectedPost.content || "") ||
      editHashtags !== (selectedPost.hashtags?.join(" ") || "") ||
      editScheduledAt !== (selectedPost.scheduledAt ? selectedPost.scheduledAt.slice(0, 16) : "")

    if (!hasChanges) {
      setIsEditing(false)
      return
    }

    setIsSaving(true);
    try {
      // 백엔드 API 호출하여 게시글 수정
      const boardId = selectedPost.id;
      const updateData = {
        board_topic: editTitle,
        board_description: editContent,
        board_hash_tag: editHashtags,
        ...(editScheduledAt && { reservation_at: `${editScheduledAt}:00` })
      };

      await apiClient.put(`/api/v1/boards/${boardId}`, updateData);

      // 성공 시 프론트엔드 상태 업데이트
      setPosts(posts => {
        const newPosts = posts.map(post => {
          if (post.id !== selectedPost.id) return post;

          return {
            ...post,
            title: editTitle,
            content: editContent,
            hashtags: editHashtags.split(" ").filter(tag => tag.startsWith("#")),
            status: post.status,
            scheduledAt: post.scheduledAt,
          };
        });
        // 최신 selectedPost로 갱신
        const updated = newPosts.find(p => p.id === selectedPost.id);
        if (updated) setSelectedPost(updated);
        return newPosts;
      });

      // 분석 데이터도 갱신
      await loadAnalyticsData()

      setIsEditing(false);
      setIsPostDetailModalOpen(false);

    } catch (error) {
    } finally {
      setIsSaving(false);
    }
  };

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

  // 음성 관련 함수들
  const handleBaseVoiceFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // 파일 크기 체크 (10MB)
    if (file.size > 10 * 1024 * 1024) {
      toast({
        title: "파일 크기 초과",
        description: "음성 파일은 10MB 이하여야 합니다.",
        variant: "destructive",
      })
      return
    }

    // 오디오 파일 타입 체크
    if (!file.type.startsWith('audio/')) {
      toast({
        title: "파일 형식 오류",
        description: "오디오 파일만 업로드할 수 있습니다.",
        variant: "destructive",
      })
      return
    }

    setBaseVoiceFile(file)
  }

  const handleUploadBaseVoice = async () => {
    if (!baseVoiceFile) return

    setIsUploadingBaseVoice(true)
    try {
      // 파일을 Base64로 변환
      const reader = new FileReader()
      const fileData = await new Promise<string>((resolve, reject) => {
        reader.onload = () => {
          const base64 = reader.result as string
          // data:audio/mp3;base64, 부분을 제거하고 base64 데이터만 추출
          const base64Data = base64.split(',')[1]
          resolve(base64Data)
        }
        reader.onerror = reject
        reader.readAsDataURL(baseVoiceFile)
      })

      // JSON으로 전송
      const requestData = {
        file_data: fileData,
        file_name: baseVoiceFile.name,
        file_type: baseVoiceFile.type
      }

      // 베이스 음성 업로드 API 호출
      const response = await apiClient.post<{
        s3_url: string, 
        file_name: string, 
        file_size: number, 
        message: string,
        original_filename?: string
      }>(`/api/v1/influencers/${params.id}/voice/base`, requestData)
      
      if (response?.s3_url) {
        setBaseVoiceUrl(response.s3_url)
        setHasBaseVoice(true)
        setBaseVoiceFile(null)
        
        // 원본 파일명이 있으면 WAV로 변환되었음을 알림
        const description = response.original_filename 
          ? `베이스 음성이 WAV 형식으로 변환되어 업로드되었습니다. (원본: ${response.original_filename})`
          : "베이스 음성이 성공적으로 업로드되었습니다."
        
        toast({
          title: "업로드 완료",
          description,
        })
      } else {
        throw new Error('응답에 s3_url이 없습니다')
      }
    } catch (error: any) {
      console.error('베이스 음성 업로드 실패:', error)
      toast({
        title: "업로드 실패",
        description: error.response?.data?.detail || "베이스 음성 업로드 중 오류가 발생했습니다.",
        variant: "destructive",
      })
    } finally {
      setIsUploadingBaseVoice(false)
    }
  }

  const handleChangeBaseVoice = () => {
    setHasBaseVoice(false)
    setBaseVoiceUrl(null)
    setBaseVoiceFile(null)
  }

  const handleGenerateVoice = async () => {
    if (!voiceText.trim() || isGeneratingVoice || !hasBaseVoice) return

    setIsGeneratingVoice(true)
    try {
      const response = await apiClient.post<{
        status?: string;
        task_id?: string;
        audio_url?: string;
        s3_url?: string;
        duration?: number;
      }>('/api/v1/tts/generate_voice', {
        text: voiceText,
        influencer_id: params.id,
        base_voice_url: baseVoiceUrl
      })

      if (response) {
        if (response.status === 'pending' && response.task_id) {
          // 비동기 작업인 경우
          toast({
            title: "음성 생성 시작",
            description: "음성 생성 작업이 시작되었습니다. 잠시 후 목록에 표시됩니다.",
          })
          
          // 입력 필드 초기화
          setVoiceText("")
          
          // 잠시 후 음성 목록 새로고침
          setTimeout(() => {
            loadVoiceHistory()
          }, 5000)
        } else if (response.s3_url) {
          // 동기 작업인 경우 (즉시 완료)
          const newVoice = {
            id: Date.now().toString(),
            text: voiceText,
            url: response.url || response.s3_url,
            duration: response.duration,
            createdAt: new Date().toISOString(),
            status: 'completed'
          }
          setVoiceHistory(prev => [newVoice, ...prev])
          
          // 입력 필드 초기화
          setVoiceText("")
          
          toast({
            title: "음성 생성 완료",
            description: "음성이 성공적으로 생성되었습니다.",
          })

          // 자동 재생 (선택사항)
          handlePlayVoice(response.s3_url)
        }
      }
    } catch (error: any) {
      console.error('음성 생성 실패:', error)
      toast({
        title: "음성 생성 실패",
        description: error.response?.data?.detail || "음성 생성 중 오류가 발생했습니다.",
        variant: "destructive",
      })
    } finally {
      setIsGeneratingVoice(false)
    }
  }

  const checkBaseVoice = async () => {
    try {
      // 베이스 음성 확인 API 호출
      const response = await apiClient.get<{
        base_voice_url: string | null,
        has_voice: boolean,
        message?: string
      }>(`/api/v1/influencers/${params.id}/voice/base`)
      
      if (response && response.has_voice && response.base_voice_url) {
        setBaseVoiceUrl(response.base_voice_url)
        setHasBaseVoice(true)
      } else {
        // 음성이 없는 경우
        setHasBaseVoice(false)
        setBaseVoiceUrl(null)
      }
    } catch (error: any) {
      console.error('베이스 음성 확인 중 오류:', error)
      setHasBaseVoice(false)
      setBaseVoiceUrl(null)
    }
  }

  const loadVoiceHistory = async () => {
    setIsLoadingVoiceHistory(true)
    try {
      const response = await apiClient.get<any[]>(`/api/v1/influencers/${params.id}/voices`)
      
      // response가 배열인지 확인 (apiClient는 데이터를 직접 반환)
      if (Array.isArray(response)) {
        // 응답 데이터를 프론트엔드 형식에 맞게 변환
        const voiceHistory = response.map((voice: any) => ({
          id: voice.id,
          text: voice.text,
          url: voice.url || voice.s3_url,  // url 필드를 우선 사용
          duration: voice.duration,
          createdAt: voice.createdAt || voice.created_at,  // createdAt 필드를 우선 사용
          status: voice.status || 'completed',
          task_id: voice.task_id
        }))
        
        setVoiceHistory(voiceHistory)
      } else if ((response as any)?.data && Array.isArray((response as any).data)) {
        // response.data가 배열인 경우
        const voiceHistory = (response as any).data.map((voice: any) => ({
          id: voice.id,
          text: voice.text,
          url: voice.url || voice.s3_url,
          duration: voice.duration,
          createdAt: voice.createdAt || voice.created_at,
          status: voice.status || 'completed',
          task_id: voice.task_id
        }))
        
        setVoiceHistory(voiceHistory)
      } else {
        // 빈 배열로 설정
        setVoiceHistory([])
      }
    } catch (error) {
      console.error('음성 목록 로드 실패:', error)
      // 에러가 발생한 경우에만 실패 메시지 표시
      toast({
        title: "로드 실패",
        description: "음성 목록을 불러오는데 실패했습니다.",
        variant: "destructive",
      })
      setVoiceHistory([])
    } finally {
      setIsLoadingVoiceHistory(false)
    }
  }

  const handlePlayVoice = (url: string) => {
    if (!url) return

    if (playingVoiceUrl === url && audioRef.current) {
      // 이미 재생 중이면 정지
      audioRef.current.pause()
      setPlayingVoiceUrl(null)
    } else {
      // 이전 오디오가 재생 중이면 정지
      if (audioRef.current) {
        audioRef.current.pause()
      }

      // 새로운 오디오 재생
      const audio = new Audio(url)
      audioRef.current = audio
      
      audio.play().then(() => {
        setPlayingVoiceUrl(url)
      }).catch((error) => {
        console.error('오디오 재생 실패:', error)
        toast({
          title: "재생 실패",
          description: "오디오를 재생할 수 없습니다.",
          variant: "destructive",
        })
      })

      // 재생이 끝나면 상태 초기화
      audio.addEventListener('ended', () => {
        setPlayingVoiceUrl(null)
      })

      // 에러 발생 시 상태 초기화
      audio.addEventListener('error', () => {
        setPlayingVoiceUrl(null)
        toast({
          title: "재생 오류",
          description: "오디오 파일을 로드할 수 없습니다.",
          variant: "destructive",
        })
      })
    }
  }

  const handleDownloadVoice = async (url: string | undefined, id: string) => {
    try {
      if (!url) {
        throw new Error("음성 파일 URL이 없습니다")
      }
      
      console.log('Download URL:', url)
      
      // 다운로드 시작 알림
      toast({
        title: "다운로드 시작",
        description: "음성 파일을 다운로드하고 있습니다...",
      })

      const response = await fetch(url)
      
      if (!response.ok) {
        throw new Error(`다운로드 실패: ${response.status}`)
      }

      // 파일 크기 가져오기
      const contentLength = response.headers.get('content-length')
      const total = parseInt(contentLength || '0', 10)
      
      // ReadableStream을 사용해서 데이터 읽기
      const reader = response.body?.getReader()
      if (!reader) throw new Error('스트림을 읽을 수 없습니다')
      
      const chunks: Uint8Array[] = []
      let receivedLength = 0

      while (true) {
        const { done, value } = await reader.read()
        
        if (done) break
        
        chunks.push(value)
        receivedLength += value.length
        
        // 진행률 로그 (필요시 UI에 표시 가능)
        if (total) {
          const progress = Math.round((receivedLength / total) * 100)
          console.log(`다운로드 진행률: ${progress}%`)
        }
      }

      // Uint8Array로 합치기
      const chunksAll = new Uint8Array(receivedLength)
      let position = 0
      for (const chunk of chunks) {
        chunksAll.set(chunk, position)
        position += chunk.length
      }

      // Blob 생성 및 다운로드
      const blob = new Blob([chunksAll], { type: 'audio/mpeg' })
      const downloadUrl = window.URL.createObjectURL(blob)
      
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = `voice_${id}.mp3`
      document.body.appendChild(link)
      link.click()
      
      // 정리
      document.body.removeChild(link)
      window.URL.revokeObjectURL(downloadUrl)
      
      toast({
        title: "다운로드 완료",
        description: "음성 파일이 다운로드되었습니다.",
      })
      
    } catch (error: any) {
      console.error('다운로드 실패:', error)
      toast({
        title: "다운로드 실패",
        description: error.message || "음성 파일 다운로드에 실패했습니다.",
        variant: "destructive",
      })
    }
  }

  const handleDeleteVoice = async () => {
    if (!voiceToDelete) return

    try {
      // 올바른 엔드포인트 경로로 수정
      await apiClient.delete(`/api/v1/influencers/voices/${voiceToDelete}`)
      
      // 로컬에서 제거
      setVoiceHistory(prev => prev.filter(v => v.id !== voiceToDelete))
      
      toast({
        title: "삭제 완료",
        description: "음성이 삭제되었습니다.",
      })
      
      setVoiceToDelete(null)
    } catch (error: any) {
      console.error('음성 삭제 실패:', error)
      toast({
        title: "삭제 실패",
        description: error.response?.data?.detail || "음성 삭제에 실패했습니다.",
        variant: "destructive",
      })
    }
  }

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
                  onClick={model.chatbot_option ? () => window.open(`/chat/${model.id}`, '_blank') : handleChatbotToggle}
                >
                  <MessageSquare className="h-4 w-4 mr-2" />
                  {model.chatbot_option ? "챗봇 페이지로 이동" : "챗봇 생성"}
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
          <TabsList className="grid w-full grid-cols-6">
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
            <TabsTrigger value="voice" className="flex items-center space-x-2">
              <Mic className="h-4 w-4" />
              <span>음성</span>
            </TabsTrigger>
          </TabsList>

          {/* 분석 탭 */}
          <TabsContent value="analytics">
            <div className="flex justify-between items-center mb-6">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">인플루언서 분석</h3>
                <p className="text-sm text-gray-600">{model?.name}의 성과와 통계를 확인하세요</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={loadAnalyticsData}
                disabled={isPostsLoading}
                className="flex items-center space-x-2"
              >
                <RefreshCw className={`h-4 w-4 ${isPostsLoading ? 'animate-spin' : ''}`} />
                <span>새로고침</span>
              </Button>
            </div>

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
                <div className="h-64">
                  {weeklyChartData.length > 0 ? (
                    <div className="h-full flex items-end justify-between space-x-2">
                      {weeklyChartData.map((data, index) => (
                        <div key={data.date} className="flex-1 flex flex-col items-center">
                          <div
                            className="w-full bg-blue-500 rounded-t"
                            style={{
                              height: `${Math.max((data.calls / Math.max(...weeklyChartData.map(d => d.calls))) * 200, 4)}px`
                            }}
                          />
                          <div className="text-xs text-gray-500 mt-2 text-center">
                            {new Date(data.date).toLocaleDateString('ko-KR', {
                              month: 'short',
                              day: 'numeric'
                            })}
                          </div>
                          <div className="text-xs font-medium text-gray-700 mt-1">
                            {data.calls}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="h-full flex items-center justify-center">
                      <div className="text-center">
                        <BarChart3 className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                        <p className="text-gray-500 mb-2">차트 데이터 로딩 중...</p>
                      </div>
                    </div>
                  )}
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
                <Button
                  variant="outline"
                  size="sm"
                  onClick={loadPostsData}
                  disabled={isPostsLoading}
                  className="flex items-center space-x-2"
                >
                  <RefreshCw className={`h-4 w-4 ${isPostsLoading ? 'animate-spin' : ''}`} />
                  <span>새로고침</span>
                </Button>
              </div>

              {isPostsLoading ? (
                <div className="text-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
                  <p className="text-gray-500 text-lg">게시글을 불러오는 중...</p>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
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
                    <div className="flex flex-col items-center space-y-4 pt-12">
                      {/* 대형 프로필 이미지 - 클릭 가능 */}
                      <div className="relative cursor-pointer" onClick={openImageModal}>
                        {uploadedImage && imagePreview ? (
                          // 업로드된 이미지 미리보기
                          <div className="w-36 h-36 rounded-full overflow-hidden shadow-lg hover:opacity-80 transition-opacity">
                            <img
                              src={imagePreview}
                              alt="Uploaded"
                              className="w-full h-full object-cover"
                            />
                          </div>
                        ) : model?.image_url ? (
                          // 기존 인플루언서 이미지
                          <div className="w-36 h-36 rounded-full overflow-hidden shadow-lg hover:opacity-80 transition-opacity">
                            <img
                              src={model.image_url}
                              alt="Profile"
                              className="w-full h-full object-cover"
                              onError={(e) => {
                                // 이미지 로드 실패 시 기본 아이콘 표시
                                const target = e.target as HTMLImageElement;
                                target.style.display = 'none';
                                const parent = target.parentElement;
                                if (parent) {
                                  parent.innerHTML = `
                                    <div class="w-36 h-36 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg">
                                      <div class="w-20 h-20 bg-orange-500 rounded-lg flex items-center justify-center">
                                        <svg class="h-10 w-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                                        </svg>
                                      </div>
                                    </div>
                                  `;
                                }
                              }}
                            />
                          </div>
                        ) : (
                          // 기본 아이콘
                          <div className="w-36 h-36 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg hover:opacity-80 transition-opacity">
                            <div className="w-20 h-20 bg-orange-500 rounded-lg flex items-center justify-center">
                              <Bot className="h-10 w-10 text-white" />
                            </div>
                          </div>
                        )}
                        {/* 클릭 안내 오버레이 */}
                        <div className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity bg-black bg-opacity-30 rounded-full">
                          <div className="text-center">
                            <span className="text-white text-sm font-medium">확대/변경</span>
                          </div>
                        </div>
                      </div>

                      <div className="text-center space-y-3">
                        <p className="text-sm text-gray-500">권장 크기: 400x400px, 최대 5MB</p>
                        <p className="text-xs text-gray-400">이미지를 클릭하여 확대/변경</p>
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
                        disabled={isUpdating || isModelLoading || isUploadingImage}
                        className="w-full bg-gray-800 hover:bg-gray-900 text-white font-medium py-2.5"
                      >
                        {isUploadingImage ? "이미지 업로드 중..." : isUpdating ? "업데이트 중..." : isModelLoading ? "로딩 중..." : "정보 저장"}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

            </div>
          </TabsContent>

          {/* 음성 탭 */}
          <TabsContent value="voice">
            <div className="space-y-6">
              {/* 베이스 음성 업로드 카드 */}
              <Card className="bg-white shadow-sm border border-gray-200">
                <CardHeader className="pb-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-12 h-12 bg-indigo-100 rounded-lg flex items-center justify-center">
                      <Upload className="h-6 w-6 text-indigo-600" />
                    </div>
                    <div>
                      <CardTitle className="text-lg font-medium text-gray-900">베이스 음성 설정</CardTitle>
                      <CardDescription className="text-sm text-gray-600 mt-1">
                        AI 인플루언서의 목소리가 될 기본 음성을 업로드하세요.
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {hasBaseVoice ? (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between p-4 bg-green-50 border border-green-200 rounded-lg">
                        <div className="flex items-center space-x-3">
                          <CheckCircle className="h-5 w-5 text-green-600" />
                          <div>
                            <p className="text-sm font-medium text-green-900">베이스 음성이 설정되었습니다</p>
                            <p className="text-xs text-green-700 mt-1">이제 텍스트를 음성으로 변환할 수 있습니다.</p>
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          {baseVoiceUrl && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handlePlayVoice(baseVoiceUrl)}
                            >
                              {playingVoiceUrl === baseVoiceUrl ? (
                                <PauseCircle className="h-4 w-4" />
                              ) : (
                                <PlayCircle className="h-4 w-4" />
                              )}
                            </Button>
                          )}
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handleChangeBaseVoice}
                            className="text-indigo-600 hover:text-indigo-700"
                          >
                            변경
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                        <input
                          type="file"
                          accept="audio/*"
                          onChange={handleBaseVoiceFileSelect}
                          className="hidden"
                          id="base-voice-upload"
                        />
                        <label
                          htmlFor="base-voice-upload"
                          className="cursor-pointer"
                        >
                          <Upload className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                          <p className="text-sm font-medium text-gray-900 mb-1">
                            클릭하여 음성 파일 선택
                          </p>
                          <p className="text-xs text-gray-500">
                            MP3, WAV, M4A 등 (최대 10MB)
                          </p>
                        </label>
                      </div>
                      {baseVoiceFile && (
                        <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                          <div className="flex items-center space-x-3">
                            <Volume2 className="h-5 w-5 text-gray-600" />
                            <div>
                              <p className="text-sm font-medium text-gray-900">{baseVoiceFile.name}</p>
                              <p className="text-xs text-gray-500">
                                {(baseVoiceFile.size / 1024 / 1024).toFixed(2)} MB
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setBaseVoiceFile(null)
                              }}
                            >
                              취소
                            </Button>
                            <Button
                              size="sm"
                              onClick={handleUploadBaseVoice}
                              disabled={isUploadingBaseVoice}
                              className="bg-indigo-600 hover:bg-indigo-700 text-white"
                            >
                              {isUploadingBaseVoice ? (
                                <>
                                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                  업로드 중...
                                </>
                              ) : (
                                '업로드'
                              )}
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* 음성 생성 카드 */}
              <Card className={`bg-white shadow-sm border border-gray-200 ${!hasBaseVoice ? 'opacity-50' : ''}`}>
                <CardHeader className="pb-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                      <Mic className="h-6 w-6 text-purple-600" />
                    </div>
                    <div>
                      <CardTitle className="text-lg font-medium text-gray-900">음성 생성</CardTitle>
                      <CardDescription className="text-sm text-gray-600 mt-1">
                        텍스트를 입력하면 AI 인플루언서의 음성으로 변환할 수 있습니다.
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {!hasBaseVoice && (
                    <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                      <p className="text-sm text-yellow-800">
                        <AlertCircle className="h-4 w-4 inline mr-1" />
                        먼저 베이스 음성을 업로드해주세요.
                      </p>
                    </div>
                  )}
                  <div>
                    <Label htmlFor="voice-text">텍스트 입력</Label>
                    <Textarea
                      id="voice-text"
                      placeholder="음성으로 변환할 텍스트를 입력하세요..."
                      className="min-h-[100px] mt-2"
                      value={voiceText}
                      onChange={(e) => {
                        const newText = e.target.value
                        if (newText.length <= 300) {
                          setVoiceText(newText)
                        } else {
                          toast({
                            title: "글자수 제한",
                            description: "텍스트는 300자까지만 입력할 수 있습니다.",
                            variant: "destructive",
                          })
                        }
                      }}
                      disabled={!hasBaseVoice}
                      maxLength={300}
                    />
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-500">
                      {voiceText.length} / 300자
                    </span>
                    <Button
                      onClick={handleGenerateVoice}
                      disabled={!hasBaseVoice || !voiceText.trim() || isGeneratingVoice || voiceText.length > 300}
                      className="bg-purple-600 hover:bg-purple-700 text-white"
                    >
                      {isGeneratingVoice ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          생성 중...
                        </>
                      ) : (
                        <>
                          <Volume2 className="h-4 w-4 mr-2" />
                          음성 생성
                        </>
                      )}
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* 생성된 음성 목록 카드 */}
              <Card className="bg-white shadow-sm border border-gray-200">
                <CardHeader className="pb-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                        <Volume2 className="h-6 w-6 text-green-600" />
                      </div>
                      <div>
                        <CardTitle className="text-lg font-medium text-gray-900">생성된 음성</CardTitle>
                        <CardDescription className="text-sm text-gray-600 mt-1">
                          이전에 생성한 음성 파일들을 관리할 수 있습니다.
                        </CardDescription>
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={loadVoiceHistory}
                      disabled={isLoadingVoiceHistory}
                      className="flex items-center space-x-2"
                    >
                      <RefreshCw className={`h-4 w-4 ${isLoadingVoiceHistory ? 'animate-spin' : ''}`} />
                      <span>새로고침</span>
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {isLoadingVoiceHistory ? (
                    <div className="text-center py-8">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600 mx-auto mb-4"></div>
                      <p className="text-gray-500">음성 목록을 불러오는 중...</p>
                    </div>
                  ) : voiceHistory.length > 0 ? (
                    <div className="space-y-3">
                      {voiceHistory.map((voice) => (
                        <div key={voice.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                          <div className="flex items-center space-x-3">
                            {voice.status === 'pending' ? (
                              <div className="p-2 bg-yellow-100 rounded-full">
                                <Loader2 className="h-5 w-5 text-yellow-600 animate-spin" />
                              </div>
                            ) : voice.status === 'failed' ? (
                              <div className="p-2 bg-red-100 rounded-full">
                                <AlertCircle className="h-5 w-5 text-red-600" />
                              </div>
                            ) : (
                              <button
                                onClick={() => handlePlayVoice(voice.url)}
                                className="p-2 bg-white rounded-full shadow-sm hover:shadow-md transition-shadow"
                                disabled={!voice.url}
                              >
                                {playingVoiceUrl === voice.url ? (
                                  <PauseCircle className="h-5 w-5 text-purple-600" />
                                ) : (
                                  <PlayCircle className="h-5 w-5 text-purple-600" />
                                )}
                              </button>
                            )}
                            <div>
                              <p className="text-sm font-medium text-gray-900 line-clamp-1">{voice.text}</p>
                              <p className="text-xs text-gray-500">
                                {new Date(voice.createdAt).toLocaleDateString('ko-KR')} •{' '}
                                {voice.status === 'pending' ? '생성 중...' : 
                                 voice.status === 'failed' ? '생성 실패' :
                                 voice.duration ? `${voice.duration}초` : '길이 정보 없음'}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleDownloadVoice(voice.url, voice.id)}
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setVoiceToDelete(voice.id)}
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <Volume2 className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                      <p className="text-gray-500 text-lg">아직 생성된 음성이 없습니다</p>
                      <p className="text-gray-400 mt-2">위에서 텍스트를 입력하고 음성을 생성해보세요!</p>
                    </div>
                  )}
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
              <div className="flex items-center space-x-2">
                {(selectedPost?.status === 'draft' || selectedPost?.status === 'scheduled') && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setIsEditing(!isEditing)}
                    className="flex items-center space-x-1"
                  >
                    {isEditing ? (
                      <>
                        <Eye className="h-4 w-4" />
                        <span>보기 모드</span>
                      </>
                    ) : (
                      <>
                        <Edit className="h-4 w-4" />
                        <span>수정 모드</span>
                      </>
                    )}
                  </Button>
                )}
                {isEditing && (
                  <Button
                    onClick={handleEditSave}
                    size="sm"
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    저장
                  </Button>
                )}
                {selectedPost?.instagram_link && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => window.open(selectedPost.instagram_link, '_blank')}
                    className="flex items-center space-x-1"
                  >
                    <ExternalLink className="h-4 w-4" />
                    <span>인스타그램 보기</span>
                  </Button>
                )}

              </div>
            </DialogHeader>

            {selectedPost && (
              <div className="space-y-6">
                {/* 게시글 기본 정보 */}
                <div className="flex justify-between items-start pb-4 border-b">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 mb-2">{selectedPost.title}</h3>
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
                        <span>예약 발행: {formatDate(selectedPost.scheduledAt || '')}</span>
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

                  {/* 오른쪽 상단에 배지들 배치 */}
                  <div className="flex flex-col items-end space-y-2 ml-4">
                    {selectedPost.platform && getPlatformBadge(selectedPost.platform)}
                    {getStatusBadge(selectedPost.status)}
                  </div>
                </div>

                {/* 게시글 내용 */}
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-gray-900">게시글 내용</h4>
                  {isEditing && (selectedPost?.status === 'draft' || selectedPost?.status === 'scheduled') ? (
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">제목</label>
                        <Input
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          placeholder="게시글 제목을 입력하세요"
                          className="w-full"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">내용</label>
                        <textarea
                          value={editContent}
                          onChange={(e) => setEditContent(e.target.value)}
                          placeholder="게시글 내용을 입력하세요"
                          className="w-full h-32 p-3 border border-gray-300 rounded-md resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">해시태그</label>
                        <Input
                          value={editHashtags}
                          onChange={(e) => setEditHashtags(e.target.value)}
                          placeholder="#해시태그1 #해시태그2"
                          className="w-full"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">예약 시간</label>
                        <Input
                          type="datetime-local"
                          value={editScheduledAt}
                          onChange={(e) => setEditScheduledAt(e.target.value)}
                          className="w-full"
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="bg-gray-50 border rounded-lg p-4">
                      <div className="whitespace-pre-wrap text-gray-800 leading-relaxed">
                        {selectedPost.content}
                      </div>
                    </div>
                  )}
                </div>

                {/* 해시태그 */}
                {!isEditing && (
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
                )}

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

        {/* 이미지 모달 */}
        <Dialog open={isImageModalOpen} onOpenChange={setIsImageModalOpen}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle className="flex items-center space-x-2">
                <Bot className="h-5 w-5" />
                <span>프로필 이미지</span>
              </DialogTitle>
            </DialogHeader>
            
            <div className="space-y-6">
              {/* 현재 이미지 표시 */}
              <div className="flex justify-center">
                {uploadedImage && imagePreview ? (
                  <div className="relative">
                    <img
                      src={imagePreview}
                      alt="Uploaded"
                      className="w-80 h-80 object-cover rounded-lg shadow-lg"
                    />
                  </div>
                ) : model?.image_url ? (
                  <div className="relative">
                    <img
                      src={model.image_url}
                      alt="Profile"
                      className="w-80 h-80 object-cover rounded-lg shadow-lg"
                      onError={(e) => {
                        const target = e.target as HTMLImageElement;
                        target.style.display = 'none';
                        const parent = target.parentElement;
                        if (parent) {
                          parent.innerHTML = `
                            <div class="w-80 h-80 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg">
                              <div class="w-40 h-40 bg-orange-500 rounded-lg flex items-center justify-center">
                                <svg class="h-20 w-20 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                                </svg>
                              </div>
                            </div>
                          `;
                        }
                      }}
                    />
                  </div>
                ) : (
                  <div className="w-80 h-80 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg">
                    <div className="w-40 h-40 bg-orange-500 rounded-lg flex items-center justify-center">
                      <Bot className="h-20 w-20 text-white" />
                    </div>
                  </div>
                )}
              </div>

              {/* 이미지 정보 */}
              <div className="text-center space-y-2">
                <p className="text-sm text-gray-600">권장 크기: 400x400px, 최대 5MB</p>
                <p className="text-xs text-gray-400">JPG, PNG 형식 지원</p>
              </div>

              {/* 액션 버튼들 */}
              <div className="flex justify-center space-x-4">
                {/* 파일 업로드 버튼 */}
                <input
                  id="modal-image-upload"
                  type="file"
                  accept="image/*"
                  onChange={handleImageUpload}
                  className="hidden"
                />
                <Button
                  variant="outline"
                  className="flex items-center space-x-2"
                  onClick={() => document.getElementById('modal-image-upload')?.click()}
                >
                  <Upload className="h-4 w-4" />
                  <span>이미지 업로드</span>
                </Button>

                {/* 갤러리에서 불러오기 버튼 */}
                <Button
                  variant="outline"
                  onClick={openGalleryModal}
                  className="flex items-center space-x-2"
                >
                  <ImageIcon className="h-4 w-4" />
                  <span>갤러리에서 불러오기</span>
                </Button>

              </div>

              {/* 저장 버튼과 제거 버튼 - 변경사항이 있을 때만 표시 */}
              {hasImageChanges && (
                <div className="flex justify-center space-x-4 pt-4 border-t">
                  <Button
                    onClick={async () => {
                      await handleUpdateModel()
                      setIsImageModalOpen(false)
                    }}
                    disabled={isUpdating || isModelLoading || isUploadingImage}
                    className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-8"
                  >
                    {isUploadingImage ? "업로드 중..." : isUpdating ? "저장 중..." : isModelLoading ? "로딩 중..." : "저장"}
                  </Button>
                  
                  {/* 이미지 제거 버튼 (업로드된 이미지가 있을 때만) */}
                  {uploadedImage && imagePreview && (
                    <Button
                      variant="outline"
                      onClick={removeImage}
                      className="text-red-600 border-red-200 hover:bg-red-50 px-8"
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      제거
                    </Button>
                  )}
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>

        {/* 갤러리 모달 */}
        <Dialog open={isGalleryModalOpen} onOpenChange={setIsGalleryModalOpen}>
          <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center space-x-2">
                <ImageIcon className="h-5 w-5" />
                <span>갤러리에서 이미지 선택</span>
              </DialogTitle>
            </DialogHeader>
            
            <div className="space-y-6">
              {isLoadingGallery ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
                  <span className="ml-2 text-gray-600">이미지 목록을 불러오는 중...</span>
                </div>
              ) : galleryImages.length > 0 ? (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {galleryImages.map((imageUrl, index) => (
                    <div
                      key={index}
                      className="relative group cursor-pointer"
                      onClick={() => selectGalleryImage(imageUrl)}
                    >
                      <img
                        src={imageUrl}
                        alt={`Gallery image ${index + 1}`}
                        className="w-full h-32 object-cover rounded-lg border hover:border-blue-500 transition-colors"
                      />
                      <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-30 transition-all duration-200 rounded-lg flex items-center justify-center">
                        <span className="text-white opacity-0 group-hover:opacity-100 text-sm font-medium">
                          선택
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <ImageIcon className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                  <p className="text-gray-500 text-lg">갤러리에 이미지가 없습니다</p>
                  <p className="text-gray-400 mt-2">먼저 이미지를 업로드해주세요</p>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>

        <Dialog open={!!voiceToDelete} onOpenChange={(open) => !open && setVoiceToDelete(null)}>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle>음성 삭제 확인</DialogTitle>
              <DialogDescription>
                이 음성을 삭제하시겠습니까? 삭제된 음성은 복구할 수 없습니다.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setVoiceToDelete(null)}
              >
                취소
              </Button>
              <Button
                variant="destructive"
                onClick={handleDeleteVoice}
              >
                삭제
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* 토스트 알림 컴포넌트 */}
      <Toaster />
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

