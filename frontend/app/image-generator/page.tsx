"use client"

import { useState, useEffect, useRef, useMemo, useCallback } from "react"
import { RunPodService, type RunPodCredits } from "@/lib/services/runpod.service"
import { Navigation } from "@/components/navigation"
import { useAuth } from "@/hooks/use-auth"
import { useWebSocket } from "@/hooks/use-websocket"
import { tokenUtils } from "@/lib/auth"
import apiClient from "@/lib/api"
import { galleryService } from "@/lib/services/gallery.service"
import { imageModificationService } from "@/lib/services/image-modification.service"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import { useToast } from "@/hooks/use-toast"
import { Progress } from "@/components/ui/progress"
import { 
  ImageIcon, 
  Wand2, 
  Download, 
  Edit, 
  Trash2, 
  Plus, 
  RefreshCw,
  Upload,
  Loader2,
  Sparkles,
  Palette,
  Sliders,
  X,
  Maximize2,
  Eraser,
  Filter,
  ChevronLeft,
  ChevronRight
} from "lucide-react"

interface GeneratedImage {
  id: string
  prompt: string
  width: number
  height: number
  image_url: string
  created_at: string
  status: 'generating' | 'completed' | 'failed'
  progress?: number
}

interface ImageSynthesisResult {
  storage_id: string
  prompt: string
  width: number
  height: number
  s3_url: string
}


const PRESET_SIZES = [
  { id: 'square', name: '정사각형', width: 512, height: 512 },
  { id: 'portrait', name: '세로형', width: 512, height: 768 },
  { id: 'landscape', name: '가로형', width: 768, height: 512 },
  { id: 'wide', name: '와이드', width: 1024, height: 512 }
]

// 세션 상태 인터페이스 추가
interface SessionStatus {
  pod_id?: string
  pod_status?: string
  session_created_at?: string
  session_expires_at?: string
  processing_expires_at?: string
  total_generations?: number
  session_remaining_seconds?: number
  processing_remaining_seconds?: number
}

// WebSocket 메시지 타입
interface WSMessage {
  type: 'session_status' | 'generation_progress' | 'generation_complete' | 'error' | 'pong' | 'session_created'
  data: any
}

// 공통 2단계 유형
const COMMON_TYPES = [
  { id: 'real', name: '실사' },
  { id: 'movie', name: '영화' },
  { id: 'anime', name: '애니메이션' },
  { id: 'webtoon', name: '웹툰' },
  { id: 'digital', name: '디지털' },
];

const LANDSCAPE_OPTIONS = [
  { id: 'nature', name: '자연' },
  { id: 'city', name: '도시' },
  { id: 'space', name: '우주' },
  { id: 'digital', name: '디지털' },
]

// 프롬프트 키워드 매핑
const PROMPT_KEYWORDS = {
  // 스타일 키워드
  styles: {
    real: 'photo-realistic, 8k portrait, DSLR, realistic skin texture',
    movie: 'cinematic lighting, film grain, movie poster, dynamic shadows',
    anime: 'anime style, Makoto Shinkai, Ghibli, anime lighting, 2D cell shading',
    webtoon: 'webtoon style, flat colors, ink outline, clean lines',
    digital: 'digital painting, concept art, soft shading, detailed brush strokes'
  },
  // 성별 키워드
  gender: {
    man: 'male, boy, handsome man, young male, masculine face',
    woman: 'female, girl, beautiful woman, young female, feminine face'
  },
  // 지역 키워드
  region: {
    east: 'Asian, Korean, Japanese, Chinese, pale skin, almond eyes',
    west: 'Caucasian, European, American, blonde hair, blue eyes, fair skin'
  },
  // 동물/사물 스타일 키워드
  animalObjectStyles: {
    real: 'photo of, ultra-realistic, national geographic, macro shot',
    movie: 'cinematic animal, Pixar-style, Dreamworks, film lighting',
    anime: 'anime animal, Ghibli animal, 2D cartoon style',
    webtoon: 'webtoon-style animal, clean outline, simplified design',
    digital: 'digital illustration, concept art, soft brush texture, fantasy style'
  },
  // 풍경 키워드
  landscape: {
    nature: 'mountain landscape, misty forest, sunset at the lake, snowy field, desert dunes',
    city: 'futuristic city, Korean alley, urban skyline at night, abandoned industrial ruins',
    space: 'nebula space scene, planet surface, satellite orbit, alien world landscape',
    digital: 'fantasy digital world, VR cyberspace, holographic environment, synthwave grid'
  }
}

const STYLE_CATEGORIES = [
  {
    id: 'person',
    name: '사람',
    subcategories: COMMON_TYPES.map(type => ({
      ...type,
      subcategories: [
        {
          id: 'man',
          name: '남성',
          styles: [
            { id: `${type.id}_man_east`, name: '동양' },
            { id: `${type.id}_man_west`, name: '서양' },
          ],
        },
        {
          id: 'woman',
          name: '여성',
          styles: [
            { id: `${type.id}_woman_east`, name: '동양' },
            { id: `${type.id}_woman_west`, name: '서양' },
          ],
        },
      ],
    })),
  },
  {
    id: 'animal',
    name: '동물',
    subcategories: COMMON_TYPES.map(type => ({
      ...type,
      name: type.name,
      id: type.id
    })),
  },
  {
    id: 'object',
    name: '사물',
    subcategories: COMMON_TYPES.map(type => ({
      ...type,
      name: type.name,
      id: type.id
    })),
  },
  {
    id: 'landscape',
    name: '풍경',
    // 풍경은 별도의 세부 옵션만 가짐
    options: LANDSCAPE_OPTIONS,
  },
]

export default function ImageGeneratorPage() {
  const { toast } = useToast()
  const { user } = useAuth()
  const [images, setImages] = useState<GeneratedImage[]>([])
  const [loading, setLoading] = useState(false)

  // 모델 선택 기능 제거 - 워크플로우에 정의된 모델 자동 사용
  const [selectedWorkflow, setSelectedWorkflow] = useState<string>("")

  const [selectedStyle, setSelectedStyle] = useState<string>("realistic")
  const [selectedSize, setSelectedSize] = useState<string>("square")

  // 갤러리 페이지네이션 상태
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(0)
  const [totalImages, setTotalImages] = useState(0)
  const [galleryLoading, setGalleryLoading] = useState(false)
  
  // 세션 상태 관리 추가
  const [sessionStatus, setSessionStatus] = useState<SessionStatus | null>(null)
  const [sessionLoading, setSessionLoading] = useState(false)
  
  // 클라이언트 사이드 카운트다운 상태
  const [clientSessionTime, setClientSessionTime] = useState<number | null>(null)
  const [clientProcessingTime, setClientProcessingTime] = useState<number | null>(null)
  
  // 세션 자동 재시도 상태
  const [sessionRetryCount, setSessionRetryCount] = useState(0)
  
  // 진행 상태
  const [generationProgress, setGenerationProgress] = useState<{
    status: string
    progress: number
    message: string
  } | null>(null)
  const [isAutoRetrying, setIsAutoRetrying] = useState(false)
  
  // 세션 만료 추적 상태
  const [sessionExpiredNaturally, setSessionExpiredNaturally] = useState(false)
  const [lastKnownSessionStatus, setLastKnownSessionStatus] = useState<SessionStatus | null>(null)
  
  // 인증 상태 추가
  const { token, isAuthenticated } = useAuth()

  // 웹소켓 훅 사용
  const { isConnected: wsConnected, send: wsSend } = useWebSocket({
    onSessionStatus: (status: SessionStatus) => {
      setSessionStatus(prev => {
        // pod_ready로 이미 ready 상태인 경우, session_status로 starting으로 되돌리지 않음
        if (prev?.pod_status === 'ready' && status.pod_status === 'starting') {
          console.log('🔒 Pod ready 상태 보호: starting으로 되돌리지 않음')
          return {
            ...status,
            pod_status: 'ready' // ready 상태 유지
          }
        }
        return status
      })
      if (status.session_remaining_seconds !== undefined) {
        setClientSessionTime(status.session_remaining_seconds)
      }
      if (status.processing_remaining_seconds !== undefined) {
        setClientProcessingTime(status.processing_remaining_seconds)
      }
    },
    onGenerationProgress: (progress: any) => {
      setGenerationProgress(progress)
    },
    onGenerationComplete: (data: any) => {
      console.log('🎉 Generation complete received:', data)
      handleGenerationComplete(data)
    },
    onMessage: (message: any) => {
      switch (message.type) {
        case 'pod_ready':
          if (message.data) {
            console.log('🎯 Pod ready 메시지 수신:', message.data)
            setSessionStatus(prev => ({
              ...prev,
              pod_status: 'ready',
              pod_id: message.data.pod_id || prev?.pod_id
            }))
            toast({
              title: "🎨 RunPod 준비 완료!",
              description: message.data.message || '🎨 RunPod가 준비 완료되었습니다! 이제 이미지 생성이 가능합니다.',
              duration: 5000,
            })
          }
          break
          
        case 'pod_failed':
          if (message.data) {
            setSessionStatus(prev => ({
              ...prev,
              pod_status: 'failed'
            }))
            toast({
              title: "Pod 준비 실패",
              description: message.data.message || 'Pod 준비에 실패했습니다. 다시 시도해주세요.',
              variant: "destructive",
              duration: 3000,
            })
          }
          break
          
        case 'modification_progress':
          if (message.data) {
            toast({
              title: "이미지 수정 중",
              description: `${message.data.message} (${message.data.progress}%)`,
              duration: 1000,
            })
          }
          break
          
        case 'modification_complete':
          if (message.data && message.data.success) {
            if (message.data.lora_settings) {
              console.log('이미지 수정에 사용된 LoRA 설정:', message.data.lora_settings)
            }
            
            const newImage: GeneratedImage = {
              id: message.data.storage_id,
              prompt: `[Modified] ${message.data.edit_instruction}`,
              width: message.data.width,
              height: message.data.height,
              image_url: message.data.s3_url,
              created_at: new Date().toISOString(),
              status: 'completed'
            }
            
            setImages(prev => [newImage, ...prev])
            setPreviewImage(newImage)
            
            if (activeTab === "modify") {
              setShowGalleryImageModal(true)
            } else {
              setShowImageModal(true)
            }
            
            toast({
              title: "수정 완료",
              description: '이미지가 성공적으로 수정되었습니다.',
              duration: 3000,
            })
            
            const textArea = document.getElementById('edit-prompt') as HTMLTextAreaElement
            if (textArea) textArea.value = ''
            setSelectedImages([])
            setSelectedMethod(0)
            setIsGenerating(false)
          }
          break
          
        case 'session_created':
          if (message.data) {
            const data = message.data
            if (data.success) {
              setSessionStatus(data.session_status)
              setClientSessionTime(data.session_status?.session_remaining_seconds || null)
              setClientProcessingTime(data.session_status?.processing_remaining_seconds || null)
              setSessionRetryCount(0)
              setIsAutoRetrying(false)
              toast({
                title: "세션 생성 성공",
                description: '이미지 생성이 가능합니다.',
                duration: 3000,
              })
            } else {
              // 세션 생성 실패 처리
              toast({
                title: "세션 생성 실패",
                description: data.message || '세션 생성에 실패했습니다.',
                variant: "destructive",
                duration: 3000,
              })
            }
          }
          break
      }
    },
    onError: (error: any) => {
      if (error?.message) {
        toast({
          title: "오류",
          description: error.message,
          variant: "destructive",
          duration: 3000,
        })
      }
    },
    onConnect: () => {
      // 연결되면 세션 상태 요청
      wsSend({ type: 'session_status' })
    }
  })
  const [accessToken, setAccessToken] = useState<string | null>(null)
  
  // RunPod 크레딧 상태
  const [credits, setCredits] = useState<RunPodCredits | null>(null)
  
  // 토큰 초기화
  useEffect(() => {
    const storedToken = tokenUtils.getToken()
    if (storedToken) {
      setAccessToken(storedToken)
    }
  }, [token])

  // RunPod 크레딧 조회
  useEffect(() => {
    const fetchCredits = async () => {
      try {
        const creditsData = await RunPodService.getCredits()
        setCredits(creditsData)
      } catch (err) {
        console.error('RunPod 크레딧 조회 실패:', err)
        // API 오류 시 크레딧을 null로 설정하여 UI에서 적절히 처리
        setCredits(null)
        
        // 사용자에게 친화적인 에러 메시지 표시
        if (err instanceof Error) {
          if (err.message.includes('503') || err.message.includes('Service Unavailable')) {
            console.warn('RunPod API 연결 실패 - API 키 설정을 확인하세요')
          } else if (err.message.includes('401') || err.message.includes('Unauthorized')) {
            console.warn('RunPod API 인증 실패 - 로그인이 필요합니다')
          } else {
            console.warn('RunPod 크레딧 조회 중 일시적인 오류가 발생했습니다')
          }
        }
      }
    }

    if (accessToken) {
      fetchCredits()
      
      // 5분마다 자동 새로고침
      const interval = setInterval(fetchCredits, 5 * 60 * 1000)
      return () => clearInterval(interval)
    }
  }, [accessToken])

  // WebSocket 연결은 useWebSocket 훅에서 관리됨
  // 수동 WebSocket 연결 코드 제거 (wsRef 미정의 오류 해결)
  
  // 생성 파라미터
  const [prompt, setPrompt] = useState("")
  // 고급 설정 제거 - 간단한 인터페이스만 유지
  
  // UI 상태
  const [activeTab, setActiveTab] = useState("generate")
  const [isGenerating, setIsGenerating] = useState(false)
  const [selectedImage, setSelectedImage] = useState<GeneratedImage | null>(null)
  // 이미지 수정 관련 상태
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [uploadedImageUrl, setUploadedImageUrl] = useState<string | null>(null)
  const [selectedGalleryImage, setSelectedGalleryImage] = useState<GeneratedImage | null>(null)
  
  // 새로 추가된 상태
  const [previewImage, setPreviewImage] = useState<GeneratedImage | null>(null)
  const [showImageModal, setShowImageModal] = useState(false) // 이미지 생성용 모달
  const [showGalleryImageModal, setShowGalleryImageModal] = useState(false) // 갤러리용 모달
  const [showDownloadDialog, setShowDownloadDialog] = useState(false)
  const [downloadFileName, setDownloadFileName] = useState("")
  
  // 갤러리에서 이미지 선택
  const [showGallerySelector, setShowGallerySelector] = useState(false)
  
  // 최대 2개 이미지 선택을 위한 상태
  const [selectedImages, setSelectedImages] = useState<Array<{
    id: string
    url: string
    type: 'upload' | 'gallery'
    file?: File
    galleryImage?: GeneratedImage
  }>>([])
  
  // 선택된 수정 방법 상태
  const [selectedMethod, setSelectedMethod] = useState<number>(0)
  
  // 드래그 이벤트 핸들러
  const [dragActive, setDragActive] = useState(false)
  const [maskMode, setMaskMode] = useState(false)
  const [isDrawing, setIsDrawing] = useState(false)
  const [brushSize, setBrushSize] = useState(10)
  const [maskColor, setMaskColor] = useState("#FFFFFF") // 마스킹 색상 (기본값: 빨간색)
  const [lastPoint, setLastPoint] = useState<{x: number, y: number} | null>(null)
  const [activeImageIndex, setActiveImageIndex] = useState(0) // 현재 마스킹 중인 이미지 인덱스
  
  // Canvas refs
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imageRef = useRef<HTMLImageElement>(null)

  // 세션 관리 함수들
  const createUserSession = async (isAutoRetry = false, retryAttempt = 0) => {
    const maxRetries = 3
    const retryDelay = 3000 // 3초
    
    try {
      if (!isAutoRetry) {
        setSessionLoading(true)
        setSessionRetryCount(0)
        // 사용자가 수동으로 세션을 생성하는 경우 만료 플래그 리셋
        setSessionExpiredNaturally(false)
      } else {
        setIsAutoRetrying(true)
      }
      
      // WebSocket 연결 확인
      if (!wsConnected) {
        // WebSocket 연결이 없습니다
        toast({
          title: "연결 오류",
          description: 'WebSocket 연결이 끊어졌습니다. 페이지를 새로고침해주세요.',
          variant: "destructive",
          duration: 3000,
        })
        return false
      }
      
      // WebSocket으로 세션 생성 요청
      wsSend({ type: 'create_session' })
      
      // 세션 생성 요청 후 상태를 기다리지 않고 바로 리턴
      // onMessage 핸들러에서 session_created 이벤트를 처리함
      return true
    } catch (error) {
      // 세션 생성 오류
      
      // 재시도 로직
      if (retryAttempt < maxRetries) {
        const nextAttempt = retryAttempt + 1
        setSessionRetryCount(nextAttempt)
        
        // console.log(`${retryDelay/1000}초 후 세션 생성 재시도 (${nextAttempt}/${maxRetries})...`)
        
        setTimeout(async () => {
          await createUserSession(true, nextAttempt)
        }, retryDelay)
        
        return false
      } else {
        // console.error('세션 생성 최대 재시도 횟수 초과')
        setIsAutoRetrying(false)
        return false
      }
    } finally {
      if (!isAutoRetry) {
        setSessionLoading(false)
      }
    }
  }

  // 버튼 클릭용 래퍼 함수
  const handleCreateSession = async () => {
    await createUserSession(false, 0) // 수동 호출
  }

  // HTTP status 체크 제거 - WebSocket으로만 세션 상태 관리

  // 페이지 로드 시 세션 상태는 WebSocket 연결 후 자동으로 받음
  // HTTP 요청 제거

  // HTTP polling 제거 - WebSocket으로만 세션 상태 관리

  // 클라이언트 사이드 타이머 (1초마다 감소)
  useEffect(() => {
    const interval = setInterval(() => {
      setClientSessionTime(prev => {
        if (prev && prev > 0) {
          const newValue = prev - 1
          // 세션 시간이 0이 되면 자연 만료로 표시
          if (newValue <= 0) {
            setSessionExpiredNaturally(true)
            return null
          }
          return newValue
        }
        return prev
      })
      
      setClientProcessingTime(prev => {
        if (prev && prev > 0) {
          const newValue = prev - 1
          return newValue <= 0 ? null : newValue
        }
        return prev
      })
    }, 1000)
    
    return () => clearInterval(interval)
  }, [])

  const lastPointRef = useRef<{x: number, y: number} | null>(null)


  // 갤러리 이미지 가져오기 함수
  const fetchGalleryImages = async (page: number = 1) => {
    try {
      setGalleryLoading(true)

      // 팀 ID 가져오기
      const teamId = user?.teams?.[0]?.group_id
      if (!teamId) {
        toast({
          title: "팀 정보 없음",
          description: '소속된 팀이 없습니다.',
          variant: "destructive",
          duration: 3000,
        })
        return
      }

      const data = await galleryService.getImages({
        page: page,
        page_size: 12,
        team_id: teamId
      })

      // GeneratedImage 형식으로 변환
      const convertedImages = data.images.map((img) => ({
        id: img.storage_id,
        prompt: img.prompt || '',
        width: img.width,
        height: img.height,
        image_url: img.s3_url,
        created_at: img.created_at,
        status: 'completed' as const
      }))
      
      setImages(convertedImages)
      setTotalPages(data.pagination.total_pages)
      setTotalImages(data.pagination.total_count)
      setCurrentPage(data.pagination.page)
    } catch (error) {
      // Failed to fetch gallery images
      toast({
        title: "오류 발생",
        description: '이미지 목록을 불러오는데 실패했습니다.',
        variant: "destructive",
        duration: 3000,
      })
    } finally {
      setGalleryLoading(false)
    }
  }

  // 페이지 변경 핸들러
  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setCurrentPage(newPage)
      fetchGalleryImages(newPage)
    }
  }

  // 갤러리 탭 활성화 시 이미지 가져오기
  useEffect(() => {
    if (activeTab === 'gallery' && user?.teams?.[0]?.group_id) {
      fetchGalleryImages(currentPage)
    }
  }, [activeTab, user])

  // 갤러리 선택기 열릴 때 이미지 가져오기
  useEffect(() => {
    if (showGallerySelector && user?.teams?.[0]?.group_id) {
      fetchGalleryImages(1)
    }
  }, [showGallerySelector, user])

  // 프롬프트 최적화 테스트 함수
  const handleTestPrompt = async () => {
    if (!prompt.trim() && !getCombinedPromptKeywords()) {
      toast({
        title: "입력 필요",
        description: '테스트할 프롬프트를 입력하거나 스타일을 선택해주세요.',
        variant: "destructive",
        duration: 3000,
      })
      return
    }

    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        toast({
          title: "인증 필요",
          description: '로그인이 필요합니다.',
          variant: "destructive",
          duration: 3000,
        })
        return
      }

      const testResponse = await fetch('/api/prompt-test/test-prompt', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          prompt: prompt.trim() || getCombinedPromptKeywords(),
          selected_styles: getSelectedStylesForAPI()
        })
      })

      const testData = await testResponse.json()
      
      if (testData.success) {
        // 결과를 알림으로 표시
        const resultMessage = `
📝 원본 프롬프트:
${testData.original_prompt}

🎨 선택된 스타일:
${JSON.stringify(testData.selected_styles, null, 2)}

🤖 최적화된 프롬프트:
${testData.optimized_prompt}

📊 통계:
- 길이: ${testData.character_count} 문자
- 추정 토큰: ${testData.estimated_tokens}
- 최적화 방법: ${testData.optimization_method}

${testData.message}
        `
        
        toast({
          title: "프롬프트 최적화 테스트 완료",
          description: resultMessage,
          duration: 3000,
        })
        
        // 콘솔에도 상세 정보 출력
        // 프롬프트 최적화 테스트 완료
      } else {
        toast({
          title: "프롬프트 테스트 실패",
          description: testData.detail || '알 수 없는 오류',
          variant: "destructive",
          duration: 3000,
        })
      }
    } catch (error) {
      // Prompt test failed
      toast({
        title: "오류 발생",
        description: '프롬프트 테스트 중 오류가 발생했습니다.',
        variant: "destructive",
        duration: 3000,
      })
    }
  }

  // WebSocket을 통해 이미지 생성 완료 처리
  const handleGenerationComplete = (data: any) => {
    setIsGenerating(false)
    setGenerationProgress(null)
    
    if (data.success && data.s3_url) {
      const newImage: GeneratedImage = {
        id: data.storage_id || Date.now().toString(),
        prompt: data.prompt || prompt,  // 백엔드에서 받은 원본 프롬프트 사용
        width: data.width || 1024,
        height: data.height || 1024,
        image_url: data.s3_url,
        created_at: new Date().toISOString(),
        status: 'completed'
      }
      
      setImages(prev => [newImage, ...prev])
      setPreviewImage(newImage)
      setShowImageModal(true)
      
      // 재생성이 아닌 일반 생성의 경우에만 프롬프트 초기화
      if (!isGenerating || prompt !== '') {
        setPrompt("")
      }
      
      // 세션 상태는 WebSocket을 통해 자동으로 업데이트됨
    } else {
      toast({
        title: "이미지 생성 실패",
        description: data.message || '이미지 생성 실패',
        variant: "destructive",
        duration: 3000,
      })
    }
  }

  const handleGenerateImage = async () => {
    if (!prompt.trim() && !getCombinedPromptKeywords()) {
      toast({
        title: "입력 필요",
        description: '프롬프트를 입력하거나 스타일을 선택해주세요.',
        variant: "destructive",
        duration: 3000,
      })
      return
    }

    // WebSocket 연결 확인
    if (!wsConnected) {
      toast({
        title: "연결 오류",
        description: 'WebSocket 연결이 끊어졌습니다. 페이지를 새로고침해주세요.',
        variant: "destructive",
        duration: 3000,
      })
      return
    }

    setIsGenerating(true)
    setGenerationProgress({
      status: 'starting',
      progress: 0,
      message: '이미지 생성 준비 중...'
    })

    // 선택값을 명시적으로 전달
    const selectedSizeData = PRESET_SIZES.find(size => size.id === selectedSize)

    // 프론트엔드 로그: 요청 파라미터
    // console.log('[이미지 생성 요청] 파라미터:', {
    //   prompt,
    //   selected_styles: getSelectedStylesForAPI(),
    //   width: selectedSizeData?.width || 1024,
    //   height: selectedSizeData?.height || 1024,
    // })

    try {
      // WebSocket으로 이미지 생성 요청
      wsSend({
        type: 'generate_image',
        data: {
          prompt: prompt.trim() || getCombinedPromptKeywords(),
          selected_styles: getSelectedStylesForAPI(),
          width: selectedSizeData?.width || 1024,
          height: selectedSizeData?.height || 1024,
          steps: 8,
          guidance: 3.5,
          seed: null
        }
      })
    } catch (error) {
      // console.error('Failed to send image generation request:', error)
      setIsGenerating(false)
      setGenerationProgress(null)
      toast({
        title: "오류 발생",
        description: '이미지 생성 요청 중 오류가 발생했습니다.',
        variant: "destructive",
        duration: 3000,
      })
    }
  }

  const handleDeleteImage = async (storage_id: string) => {
    if (!confirm('이 이미지를 삭제하시겠습니까?')) return

    try {
      await galleryService.deleteImage(storage_id)
      
      setImages(prev => prev.filter(img => img.id !== storage_id))
      toast({
        title: "삭제 완료",
        description: '이미지가 삭제되었습니다.',
        duration: 3000,
      })
      
      // 현재 페이지 새로고침
      if (activeTab === 'gallery') {
        fetchGalleryImages(currentPage)
      }
    } catch (error) {
      // console.error('Failed to delete image:', error)
      toast({
        title: "삭제 실패",
        description: '이미지 삭제에 실패했습니다.',
        variant: "destructive",
        duration: 3000,
      })
    }
  }

  const handleDownloadImage = async (imageUrl: string, filename: string) => {
    try {
      // S3 URL에서 직접 다운로드하면 CORS 에러가 발생하므로
      // 백엔드 프록시를 통해 다운로드
      const encodedUrl = encodeURIComponent(imageUrl)
      
      // apiClient의 downloadImage 메서드를 사용하여 백엔드에 요청
      const blob = await apiClient.downloadImage(`/api/v1/image-generation/proxy-download?url=${encodedUrl}`)
      
      // Blob을 사용하여 다운로드 처리
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      toast({
        title: "다운로드 완료",
        description: "이미지가 성공적으로 다운로드되었습니다.",
        duration: 2000,
      })
    } catch (error) {
      console.error('Failed to download image:', error)
      toast({
        title: "다운로드 실패",
        description: error instanceof Error ? error.message : "이미지 다운로드에 실패했습니다.",
        variant: "destructive",
        duration: 3000,
      })
    }
  }

  // 파일 이름 변경 다운로드 함수
  const handleDownloadWithCustomName = async () => {
    if (previewImage && downloadFileName.trim()) {
      const fileExtension = '.png'
      const finalFileName = downloadFileName.endsWith(fileExtension) 
        ? downloadFileName 
        : downloadFileName + fileExtension
      
      await handleDownloadImage(previewImage.image_url, finalFileName)
      setShowDownloadDialog(false)
      setDownloadFileName("")
    }
  }

  // 다운로드 다이얼로그 열기
  const openDownloadDialog = () => {
    if (previewImage) {
      // 기본 파일 이름 설정 (프롬프트 기반)
      const defaultName = previewImage.prompt
        .slice(0, 30) // 30자로 제한
        .replace(/[^a-zA-Z0-9가-힣\s]/g, '') // 특수문자 제거
        .replace(/\s+/g, '_') // 공백을 언더스코어로 변경
        .trim()
      
      setDownloadFileName(defaultName || 'generated_image')
      setShowDownloadDialog(true)
    }
  }

  const getSelectedSizeData = () => {
    return PRESET_SIZES.find(size => size.id === selectedSize)
  }

  // 갤러리에서 선택된 이미지들
  const [gallerySelectedImages, setGallerySelectedImages] = useState<GeneratedImage[]>([])

  // 갤러리 모달에서 이미지 선택/해제
  const handleGalleryImageToggle = (image: GeneratedImage) => {
    const isSelected = gallerySelectedImages.some(img => img.id === image.id)
    
    if (isSelected) {
      setGallerySelectedImages(prev => prev.filter(img => img.id !== image.id))
    } else {
      const currentCount = selectedImages.length + gallerySelectedImages.length
      const maxAllowed = getRequiredImageCount()
      if (currentCount >= maxAllowed) {
        toast({
          title: "선택 제한",
          description: `최대 ${maxAllowed}개까지 이미지를 선택할 수 있습니다.`,
          variant: "destructive",
          duration: 3000,
        })
        return
      }
      setGallerySelectedImages(prev => [...prev, image])
    }
  }

  // 갤러리에서 선택 완료
  const handleGallerySelectionComplete = () => {
    const newImages = gallerySelectedImages.map(image => ({
      id: `gallery_${image.id}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      url: image.image_url,
      type: 'gallery' as const,
      galleryImage: image
    }))
    
    setSelectedImages(prev => [...prev, ...newImages])
    setGallerySelectedImages([])
    setShowGallerySelector(false)
  }

  // 파일 업로드 핸들러
  const handleFileUpload = (file: File) => {
    if (file && file.type.startsWith('image/')) {
      const maxAllowed = getRequiredImageCount()
      if (selectedImages.length >= maxAllowed) {
        toast({
          title: "선택 제한",
          description: `최대 ${maxAllowed}개까지 이미지를 선택할 수 있습니다.`,
          variant: "destructive",
          duration: 3000,
        })
        return
      }
      
      const newImage = {
        id: `upload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        url: URL.createObjectURL(file),
        type: 'upload' as const,
        file: file
      }
      
      setSelectedImages(prev => [...prev, newImage])
    }
  }

  // 이미지 제거 함수
  const handleRemoveImage = (imageId: string) => {
    setSelectedImages(prev => {
      const imageToRemove = prev.find(img => img.id === imageId)
      if (imageToRemove?.type === 'upload' && imageToRemove.url) {
        URL.revokeObjectURL(imageToRemove.url)
      }
      return prev.filter(img => img.id !== imageId)
    })
  }

  // 모든 이미지 제거
  const handleRemoveAllImages = () => {
    selectedImages.forEach(image => {
      if (image.type === 'upload' && image.url) {
        URL.revokeObjectURL(image.url)
      }
    })
    setSelectedImages([])
  }

  // 마스크 그리기 시작
  const startMaskDrawing = () => {
    setMaskMode(true)
    
    // Canvas 초기화
    setTimeout(() => {
      const canvas = canvasRef.current
      const image = imageRef.current
      
      if (canvas && image) {
        const ctx = canvas.getContext('2d')
        if (ctx) {
          canvas.width = image.naturalWidth
          canvas.height = image.naturalHeight
          canvas.style.width = image.offsetWidth + 'px'
          canvas.style.height = image.offsetHeight + 'px'
          
          // 투명한 캔버스로 시작
          ctx.clearRect(0, 0, canvas.width, canvas.height)
        }
      }
    }, 100)
  }

  // 이미지 영역 내부인지 확인하는 함수
  const isPointInImageBounds = useCallback((x: number, y: number): boolean => {
    const image = imageRef.current
    if (!image) return false
    
    return x >= 0 && x <= image.naturalWidth && y >= 0 && y <= image.naturalHeight
  }, [])

  // 마스크 그리기 종료
  const stopMaskDrawing = () => {
    setMaskMode(false)
  }

  // 마스크 지우기
  const clearMask = useCallback(() => {
    const canvas = canvasRef.current
    if (canvas) {
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height)
      }
    }
  }, [])

  // Canvas 마우스 이벤트
  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!maskMode) return
    setIsDrawing(true)
    
    const canvas = canvasRef.current
    const image = imageRef.current
    if (canvas && image) {
      const rect = canvas.getBoundingClientRect()
      const scaleX = canvas.width / rect.width
      const scaleY = canvas.height / rect.height
      
      let x = (e.clientX - rect.left) * scaleX
      let y = (e.clientY - rect.top) * scaleY
      
      // 이미지 영역 내부인지 확인
      if (!isPointInImageBounds(x, y)) {
        setIsDrawing(false)
        return
      }
      
      lastPointRef.current = { x, y }
      setLastPoint({ x, y })
      
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.globalCompositeOperation = 'source-over'
        ctx.fillStyle = maskColor + '80' // 선택된 색상에 투명도 추가
        ctx.beginPath()
        ctx.arc(x, y, brushSize / 2, 0, 2 * Math.PI)
        ctx.fill()
      }
    }
  }, [maskMode, maskColor, brushSize, isPointInImageBounds])

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!maskMode || !isDrawing) return
    
    const canvas = canvasRef.current
    const image = imageRef.current
    if (canvas && image && lastPointRef.current) {
      const rect = canvas.getBoundingClientRect()
      const scaleX = canvas.width / rect.width
      const scaleY = canvas.height / rect.height
      
      let x = (e.clientX - rect.left) * scaleX
      let y = (e.clientY - rect.top) * scaleY
      
      // 이미지 영역 내부인지 확인
      if (!isPointInImageBounds(x, y)) {
        return
      }
      
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.globalCompositeOperation = 'source-over'
        ctx.strokeStyle = maskColor + '80' // 선택된 색상에 투명도 추가
        ctx.lineWidth = brushSize
        ctx.lineCap = 'round'
        ctx.lineJoin = 'round'
        
        ctx.beginPath()
        ctx.moveTo(lastPointRef.current.x, lastPointRef.current.y)
        ctx.lineTo(x, y)
        ctx.stroke()
        
        lastPointRef.current = { x, y }
      }
    }
  }, [maskMode, isDrawing, maskColor, brushSize, isPointInImageBounds])

  const handleMouseUp = useCallback(() => {
    setIsDrawing(false)
    setLastPoint(null)
    lastPointRef.current = null
  }, [])

  // 마스크 데이터 추출
  const getMaskData = () => {
    const canvas = canvasRef.current
    if (canvas) {
      return canvas.toDataURL('image/png')
    }
    return null
  }

  // 인페인팅 시작
  const handleInpainting = async () => {
    const maskData = getMaskData()
    if (!maskData) {
      toast({
        title: "마스크 필요",
        description: '먼저 마스크를 그려주세요.',
        variant: "destructive",
        duration: 3000,
      })
      return
    }

    const inpaintPrompt = (document.getElementById('inpaint-prompt') as HTMLTextAreaElement)?.value
    if (!inpaintPrompt.trim()) {
      toast({
        title: "입력 필요",
        description: '수정 프롬프트를 입력해주세요.',
        variant: "destructive",
        duration: 3000,
      })
      return
    }

    try {
      setIsGenerating(true)
      
      // 인페인팅 API 호출
      const response = await fetch('/api/comfyui/inpaint', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          image: uploadedImageUrl,
          mask: maskData,
          prompt: inpaintPrompt
        })
      })

      const data = await response.json()
      
      if (data.success) {
        toast({
          title: "인페인팅 시작",
          description: '인페인팅이 시작되었습니다!',
          duration: 3000,
        })
        // 진행 상황 모니터링 로직...
      } else {
        toast({
          title: "인페인팅 실패",
          description: '인페인팅 시작에 실패했습니다.',
          variant: "destructive",
          duration: 3000,
        })
      }
    } catch (error) {
      // console.error('Inpainting error:', error)
      toast({
        title: "오류 발생",
        description: '인페인팅 중 오류가 발생했습니다.',
        variant: "destructive",
        duration: 3000,
      })
    } finally {
      setIsGenerating(false)
    }
  }

  // 재생성 기능
  const handleRegenerate = () => {
    if (!previewImage) return
    
    // WebSocket 연결 확인
    if (!wsConnected) {
      toast({
        title: "연결 오류",
        description: 'WebSocket 연결이 끊어졌습니다. 페이지를 새로고침해주세요.',
        variant: "destructive",
        duration: 3000,
      })
      return
    }
    
    // 이전 이미지를 임시 저장
    const previousImage = previewImage
    const previousPrompt = previewImage.prompt || prompt
    
    // 모달에서 로딩 상태로 변경
    setPreviewImage(null)
    setIsGenerating(true)
    setGenerationProgress({
      status: 'starting',
      progress: 0,
      message: '이미지 재생성 준비 중...'
    })
    
    try {
      // 선택된 크기 데이터 가져오기
      const selectedSizeData = PRESET_SIZES.find(size => size.id === selectedSize)
      
      // WebSocket으로 이미지 재생성 요청
      wsSend({
        type: 'generate_image',
        data: {
          prompt: previousPrompt,
          selected_styles: getSelectedStylesForAPI(),
          width: selectedSizeData?.width || 1024,
          height: selectedSizeData?.height || 1024,
          steps: 8,
          guidance: 3.5,
          seed: null  // 새로운 시드로 재생성
        }
      })
      
      // console.log('[이미지 재생성 요청] 파라미터:', {
      //   prompt: previousPrompt,
      //   selected_styles: getSelectedStylesForAPI(),
      //   width: selectedSizeData?.width || 1024,
      //   height: selectedSizeData?.height || 1024,
      //   previousImage: previousImage
      // })
    } catch (error) {
      // console.error('Failed to send regeneration request:', error)
      setIsGenerating(false)
      setGenerationProgress(null)
      setPreviewImage(previousImage) // 실패 시 이전 이미지 복원
      toast({
        title: "오류 발생",
        description: '이미지 재생성 요청 중 오류가 발생했습니다.',
        variant: "destructive",
        duration: 3000,
      })
    }
  }

  // 모달 닫기
  const handleCloseModal = () => {
    setShowImageModal(false)
    setPreviewImage(null)
  }

  // 탭 변경 시 상태 초기화
  const handleTabChange = (newTab: string) => {
    setActiveTab(newTab)
    // 탭 변경 시 상태 초기화
    setPrompt("")
    setSelectedSize("")
    
    setPreviewImage(null)
    setShowImageModal(false)
    setShowGalleryImageModal(false)
    setShowDownloadDialog(false)
    setDownloadFileName("")
    setShowGallerySelector(false)
    setSelectedImages([])
    setSelectedMethod(0)
    setUploadedFile(null)
    setUploadedImageUrl(null)
    setSelectedGalleryImage(null)
    setGallerySelectedImages([])
    setMaskMode(false)
    setBrushSize(10)
    setMaskColor("#FFFFFF")
    setLastPoint(null)
    lastPointRef.current = null
    setActiveImageIndex(0)
    if (canvasRef.current) {
      const ctx = canvasRef.current.getContext('2d')
      if (ctx) {
        ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height)
      }
    }
  }

  // 갤러리 선택기 닫기
  const handleCloseGallerySelector = () => {
    setShowGallerySelector(false)
  }

  // 드래그 이벤트 핸들러
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  // 드롭 이벤트 핸들러
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    
    if (e.dataTransfer.files) {
      const files = Array.from(e.dataTransfer.files).filter(file => file.type.startsWith('image/'))
      
      if (files.length === 0) {
        toast({
          title: "파일 형식 오류",
          description: '이미지 파일만 업로드할 수 있습니다.',
          variant: "destructive",
          duration: 3000,
        })
        return
      }
      
      const remainingSlots = 2 - selectedImages.length
      const filesToUpload = files.slice(0, remainingSlots)
      
      if (files.length > remainingSlots) {
        toast({
          title: "선택 제한",
          description: `최대 2개까지 선택 가능합니다. ${remainingSlots}개 파일만 업로드됩니다.`,
          variant: "destructive",
          duration: 3000,
        })
      }
      
      filesToUpload.forEach(file => {
        handleFileUpload(file)
      })
    }
  }

  // 파일 선택 핸들러 (다중 선택 지원)
  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (files) {
      const imageFiles = Array.from(files).filter(file => file.type.startsWith('image/'))
      
      if (imageFiles.length === 0) {
        toast({
          title: "파일 형식 오류",
          description: '이미지 파일만 선택할 수 있습니다.',
          variant: "destructive",
          duration: 3000,
        })
        return
      }
      
      const remainingSlots = 2 - selectedImages.length
      const filesToUpload = imageFiles.slice(0, remainingSlots)
      
      if (imageFiles.length > remainingSlots) {
        toast({
          title: "선택 제한",
          description: `최대 2개까지 선택 가능합니다. ${remainingSlots}개 파일만 업로드됩니다.`,
          variant: "destructive",
          duration: 3000,
        })
      }
      
      filesToUpload.forEach(file => {
        handleFileUpload(file)
      })
    }
  }

  // 수정 방법 선택 함수들
  const selectMethod1 = () => {
    setMaskMode(false)
    setSelectedMethod(1)
    // 방법 1: 단순 프롬프트 수정 모드로 전환 (이미지 1개 필요)
    if (selectedImages.length > 1) {
      // 첫 번째 이미지만 유지하고 나머지는 제거
      const firstImage = selectedImages[0]
      selectedImages.slice(1).forEach(image => {
        if (image.type === 'upload' && image.url) {
          URL.revokeObjectURL(image.url)
        }
      })
      setSelectedImages([firstImage])
    }
  }


  // 현재 선택된 방법 확인
  const getCurrentMethod = () => {
    return selectedMethod
  }

  // 선택된 방법에 따른 필요한 이미지 개수
  const getRequiredImageCount = () => {
    if (selectedMethod === 1) {
      return 1
    }
    return 0
  }

  // 스타일 선택 상태 (4단계)
  const [selectedMainCategory, setSelectedMainCategory] = useState<string | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [selectedSubcategory, setSelectedSubcategory] = useState<string | null>(null)
  const [selectedDetailStyle, setSelectedDetailStyle] = useState<string | null>(null)
  // 인종 스타일 선택 상태
  const [selectedEthnicityStyle, setSelectedEthnicityStyle] = useState<string>("기본")
  // 풍경 선택 상태
  const [selectedLandscape, setSelectedLandscape] = useState<string | null>(null)

  // 스타일 선택 관련 핸들러
  const handleMainCategorySelect = (mainId: string | null) => {
    setSelectedMainCategory(mainId)
    setSelectedCategory(null)
    setSelectedSubcategory(null)
    setSelectedLandscape(null)  // 풍경 선택도 초기화
  }
  const handleCategorySelect = (categoryId: string | null) => {
    setSelectedCategory(categoryId)
    setSelectedSubcategory(null)
    setSelectedLandscape(null)  // 풍경 선택도 초기화
  }
  const handleSubcategorySelect = (subcategoryId: string | null) => {
    setSelectedSubcategory(subcategoryId)
    setSelectedLandscape(null)  // 풍경 선택도 초기화
  }
  const handleLandscapeSelect = (landscapeId: string) => {
    setSelectedLandscape(landscapeId)
    // 풍경을 선택하면 스타일 선택 상태 초기화
    setSelectedMainCategory(null)
    setSelectedCategory(null)
    setSelectedSubcategory(null)
  }
  const handleLandscapeOptionSelect = (optionId: string) => {
    if (selectedLandscape === 'landscape') {
      setSelectedCategory(optionId)
      setSelectedMainCategory(null)
      setSelectedSubcategory(null)
    }
  }

  // 선택된 스타일을 프롬프트 키워드로 변환하는 함수
  const getStylePromptKeywords = () => {
    let keywords: string[] = []

    // 대분류가 선택되지 않았거나 풍경인 경우
    if (!selectedMainCategory || selectedMainCategory === 'landscape') {
      return keywords
    }

    // 사람인 경우
    if (selectedMainCategory === 'person') {
      if (selectedCategory && selectedSubcategory) {
        // 스타일 키워드 추가
        const styleId = selectedCategory // real, movie, anime, webtoon, digital
        if (PROMPT_KEYWORDS.styles[styleId as keyof typeof PROMPT_KEYWORDS.styles]) {
          keywords.push(PROMPT_KEYWORDS.styles[styleId as keyof typeof PROMPT_KEYWORDS.styles])
        }

        // 성별 키워드 추가
        const genderId = selectedSubcategory // man, woman
        if (PROMPT_KEYWORDS.gender[genderId as keyof typeof PROMPT_KEYWORDS.gender]) {
          keywords.push(PROMPT_KEYWORDS.gender[genderId as keyof typeof PROMPT_KEYWORDS.gender])
        }
      }
    }
    // 동물/사물인 경우
    else if (selectedMainCategory === 'animal' || selectedMainCategory === 'object') {
      if (selectedCategory) {
        // 동물/사물 스타일 키워드 추가
        const styleId = selectedCategory // real, movie, anime, webtoon, digital
        if (PROMPT_KEYWORDS.animalObjectStyles[styleId as keyof typeof PROMPT_KEYWORDS.animalObjectStyles]) {
          keywords.push(PROMPT_KEYWORDS.animalObjectStyles[styleId as keyof typeof PROMPT_KEYWORDS.animalObjectStyles])
        }
      }
    }

    return keywords
  }

  // 풍경 키워드 가져오기
  const getLandscapePromptKeywords = () => {
    if (selectedLandscape && selectedLandscape !== '' && PROMPT_KEYWORDS.landscape[selectedLandscape as keyof typeof PROMPT_KEYWORDS.landscape]) {
      return PROMPT_KEYWORDS.landscape[selectedLandscape as keyof typeof PROMPT_KEYWORDS.landscape]
    }
    return ''
  }

  // 전체 프롬프트 키워드 조합
  const getCombinedPromptKeywords = () => {
    const styleKeywords = getStylePromptKeywords()
    const landscapeKeywords = getLandscapePromptKeywords()
    
    let combinedKeywords = [...styleKeywords]
    if (landscapeKeywords) {
      combinedKeywords.push(landscapeKeywords)
    }
    
    return combinedKeywords.join(', ')
  }
  
  // 백엔드 API용 스타일 선택 정보 구성
  const getSelectedStylesForAPI = () => {
    const selectedStyles: Record<string, string> = {}
    
    // 대분류 매핑
    if (selectedMainCategory) {
      const categoryMapping: Record<string, string> = {
        'person': '사람',
        'animal': '동물',
        'object': '사물',
        'landscape': '풍경',
        'building': '건물'
      }
      selectedStyles['대분류'] = categoryMapping[selectedMainCategory] || '선택안함'
    }
    
    
    // 분위기 매핑 (기본값으로 밝은 사용)
    selectedStyles['분위기'] = '밝은'  // 디폴트
    
    // 인종 스타일 추가
    if (selectedEthnicityStyle) {
      selectedStyles['인종스타일'] = selectedEthnicityStyle
    }
    
    // console.log('🎨 선택된 스타일 정보:', selectedStyles)
    return selectedStyles
  }

  return (
    <div className="min-h-screen bg-gray-50">
        <Navigation />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="mb-8">
            <div className="flex justify-between items-start">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">이미지 생성 & 수정</h1>
                <p className="text-gray-600 mt-2">ComfyUI를 사용하여 AI 이미지를 생성하고 수정하세요</p>
              </div>
              {/* 상단 우측 정보 영역 */}
              <div className="flex flex-col space-y-2">
                {/* WebSocket 연결 상태 표시 */}
                <div className="flex items-center space-x-2">
                  <div className={`w-3 h-3 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-500'}`} />
                  <span className="text-sm text-gray-600">
                    {wsConnected ? 'WebSocket 연결됨' : 'WebSocket 연결 끊김'}
                  </span>
                </div>
                
                {/* RunPod 크레딧 표시 */}
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium text-gray-600">남은 크레딧 : </span>
                  <span className="text-sm font-medium text-gray-600">
                    {credits ? `${credits.remaining_credits.toFixed(2)} $` : '로딩 중...'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <Card className="shadow">
              <CardHeader className="pb-0 pt-0 px-0">
                <div className="flex">
                  <button
                    onClick={() => handleTabChange("generate")}
                    className={`flex-1 py-3 rounded-tl-lg border-b-0 text-base font-semibold transition-all duration-200 focus:outline-none border-r
                      ${activeTab === "generate"
                        ? "bg-white text-blue-600 border-x border-t border-blue-600 z-10"
                        : "bg-gray-100 text-gray-500 border-x border-t border-b border-gray-200 hover:text-blue-600"}
                    `}
                  >
                    <Wand2 className="inline-block mr-1 h-4 w-4 align-text-bottom" />
                    이미지 생성
                  </button>
                  <button
                    onClick={() => handleTabChange("edit")}
                    className={`flex-1 py-3 border-b-0 text-base font-semibold transition-all duration-200 focus:outline-none border-r
                      ${activeTab === "edit"
                        ? "bg-white text-green-600 border-x border-t border-green-500 z-10"
                        : "bg-gray-100 text-gray-500 border-x border-t border-b border-gray-200 hover:text-green-600"}
                    `}
                  >
                    <Edit className="inline-block mr-1 h-4 w-4 align-text-bottom" />
                    이미지 수정
                  </button>
                  <button
                    onClick={() => handleTabChange("gallery")}
                    className={`flex-1 py-3 rounded-tr-lg border-b-0 text-base font-semibold transition-all duration-200 focus:outline-none
                      ${activeTab === "gallery"
                        ? "bg-white text-purple-600 border-x border-t border-purple-500 z-10"
                        : "bg-gray-100 text-gray-500 border-x border-t border-b border-gray-200 hover:text-purple-600"}
                    `}
                  >
                    <ImageIcon className="inline-block mr-1 h-4 w-4 align-text-bottom" />
                    갤러리
                  </button>
                </div>
              </CardHeader>
              <CardContent className="border-t-0 bg-white p-6 rounded-b-lg">
                {/* 이미지 생성 탭 */}
                {activeTab === "generate" && (
                  <div className="space-y-6">
                  {/* 세션 상태 카드 */}
                  {(sessionStatus && sessionStatus.pod_id && sessionStatus.pod_status !== 'none') ? (
                    <Card className={`border-2 ${
                      sessionStatus.pod_status === 'ready' || sessionStatus.pod_status === 'running' ? 'border-blue-300' : 
                      sessionStatus.pod_status === 'starting' ? 'border-gray-200' :
                      sessionStatus.pod_status === 'processing' ? 'border-blue-500' :
                      sessionStatus.pod_status === 'failed' ? 'border-red-500' :
                      'border-gray-200'
                    }`}>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                          <div className={`w-3 h-3 rounded-full ${
                            sessionStatus.pod_status === 'ready' || sessionStatus.pod_status === 'running' ? 'bg-blue-300 animate-pulse' :
                            sessionStatus.pod_status === 'starting' ? 'bg-gray-400 animate-pulse' :
                            sessionStatus.pod_status === 'processing' ? 'bg-blue-500 animate-pulse' :
                            sessionStatus.pod_status === 'failed' ? 'bg-red-500' :
                            'bg-gray-400'
                          }`} />
                          런팟 세션 상태
                          {sessionLoading && <Loader2 className="h-4 w-4 animate-spin" />}
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm mb-2">
                          {sessionStatus?.pod_status === 'ready' || sessionStatus?.pod_status === 'running' ? '✅ 세션이 활성 상태입니다' :
                           sessionStatus?.pod_status === 'starting' ? '🚀 세션을 시작하고 있습니다...' :
                           sessionStatus?.pod_status === 'processing' ? '🎨 이미지를 생성하고 있습니다...' :
                           sessionStatus?.pod_status === 'failed' ? '❌ 세션 시작에 실패했습니다' :
                           sessionStatus?.pod_status === 'none' || !sessionStatus?.pod_id ? '🔄 세션이 없습니다' :
                           '🔍 세션 상태를 확인하고 있습니다...'}
                        </p>
                        {clientSessionTime !== null && clientSessionTime > 0 && (
                          <p className="text-xs text-gray-600">
                            세션 시간: {Math.floor(clientSessionTime / 60)}분 {clientSessionTime % 60}초
                          </p>
                        )}
                        {clientProcessingTime !== null && clientProcessingTime > 0 && (
                          <p className="text-xs text-gray-600">
                            처리 시간: {Math.floor(clientProcessingTime / 60)}분 {clientProcessingTime % 60}초
                          </p>
                        )}
                        
                        {/* 세션 시간이 만료되거나 실패한 경우 재시작 버튼 표시 (생성 중이 아닐 때만) */}
                        {(sessionStatus.pod_status === 'failed' || (clientSessionTime !== null && clientSessionTime <= 0)) && 
                         sessionStatus.pod_status !== 'starting' && (
                          <Button 
                            onClick={handleCreateSession} 
                            className="mt-2" 
                            size="sm"
                            disabled={sessionLoading}
                            variant="outline"
                          >
                            {sessionLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                            세션 재시작
                          </Button>
                        )}
                        
                        {/* Pod 생성 중 메시지 표시 */}
                        {sessionStatus.pod_status === 'starting' && (
                          <div className="flex items-center text-xs text-blue-600 mt-2">
                            <Loader2 className="h-3 w-3 animate-spin mr-1" />
                            Pod 생성 중... 잠시만 기다려주세요.
                          </div>
                        )}
                        
                        {/* 세션 시간이 만료된 경우 안내 메시지 표시 */}
                        {clientSessionTime !== null && clientSessionTime <= 0 && sessionStatus.pod_status !== 'failed' && sessionStatus.pod_status !== 'starting' && (
                          <p className="text-xs text-orange-600 mt-2">
                            ⏰ 세션 시간이 만료되었습니다. 새로운 세션을 시작해주세요.
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  ) : (
                    /* 세션이 없는 경우 새 세션 생성 안내 카드 */
                    <Card className="border-2 border-gray-300">
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full bg-gray-500" />
                          런팟 세션 상태
                          {sessionLoading && <Loader2 className="h-4 w-4 animate-spin" />}
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm mb-2 text-gray-600">🔄 세션이 만료되었습니다</p>
                        <p className="text-xs text-gray-500 mb-4">
                          AI 이미지 생성을 위해 새로운 RunPod 세션을 시작해주세요.
                        </p>
                        <Button 
                          onClick={handleCreateSession} 
                          size="default"
                          disabled={sessionLoading || isAutoRetrying}
                          variant="default"
                          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3"
                        >
                          {sessionLoading ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin mr-2" />
                              세션 생성 중...
                            </>
                          ) : isAutoRetrying ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin mr-2" />
                              자동 재시도 중... ({sessionRetryCount}/3)
                            </>
                          ) : (
                            <>
                              <RefreshCw className="h-4 w-4 mr-2" />
                              새 세션 시작하기
                            </>
                          )}
                        </Button>
                        
                        {/* 자동 재시도 안내 메시지 */}
                        {isAutoRetrying && sessionRetryCount > 0 && (
                          <p className="text-xs text-blue-600 mt-2 text-center">
                            🔄 연결 실패 시 자동으로 재시도합니다 ({sessionRetryCount}/3)
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  )}
                  
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                          <Wand2 className="h-5 w-5" />
                          이미지 생성 설정
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                          {/* 스타일 3단계 선택 UI */}
                          <div className="lg:col-span-2 space-y-6">
                            {/* 스타일 선택: 선택 사항 안내 */}
                            <Card className="border-0 shadow-none bg-gray-50">
                              <CardHeader className="pb-3">
                                <CardTitle className="flex items-center gap-2 text-base">
                                  <Palette className="h-4 w-4" />
                                  스타일 선택
                                </CardTitle>
                                <CardDescription className="text-xs text-gray-500 mt-1">
                                  원하는 경우 스타일을 선택하세요. 선택하지 않으면 기본 스타일로 생성됩니다.
                                </CardDescription>
                              </CardHeader>
                              <CardContent className="space-y-4">
                                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                                  {/* 1단계: 대분류(사람/동물/사물/풍경) */}
                                  <div>
                                    <Label className="block mb-2">대분류</Label>
                                    <div className="flex flex-col gap-2 min-w-[120px]">
                                      <button
                                        onClick={() => {
                                          setSelectedMainCategory("")
                                          setSelectedCategory("")
                                          setSelectedSubcategory("")
                                          setSelectedLandscape("")
                                        }}
                                        className={
                                          "p-3 rounded-xl border text-center transition-colors min-w-[120px] min-h-[40px] text-base font-semibold " +
                                          (selectedMainCategory === ""
                                            ? "bg-blue-100 border-blue-300 text-blue-700 ring-2 ring-blue-300 scale-105 shadow"
                                            : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:scale-105")
                                        }
                                      >
                                        선택안함
                                      </button>
                                      {STYLE_CATEGORIES
                                        .filter((main): main is { id: string; name: string; subcategories: any[] } => main.id !== 'landscape' && !!main.subcategories)
                                        .map((main) => (
                                          <button
                                            key={main.id}
                                            onClick={() => handleMainCategorySelect(main.id)}
                                            className={
                                              "p-3 rounded-xl border text-center transition-colors min-w-[120px] min-h-[40px] text-base font-semibold " +
                                              (selectedMainCategory === main.id
                                                ? "bg-blue-100 border-blue-300 text-blue-700 ring-2 ring-blue-300 scale-105 shadow"
                                                : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:scale-105")
                                            }
                                          >
                                            <div>{main.name}</div>
                                          </button>
                                        ))}
                                    </div>
                                  </div>
                                  {/* 2단계: 중분류(실사/영화/...) */}
                                  {selectedMainCategory && selectedMainCategory !== 'landscape' ? (
                                    <div>
                                      <Label className="block mb-2">중분류</Label>
                                      <div className="flex flex-col gap-2 min-w-[120px]">
                                        <button
                                          onClick={() => {
                                            setSelectedCategory("")
                                            setSelectedSubcategory("")
                                          }}
                                          className={
                                            "p-3 rounded-xl border text-center transition-colors min-w-[120px] min-h-[40px] text-base font-semibold " +
                                            (selectedCategory === ""
                                              ? "bg-blue-100 border-blue-300 text-blue-700 ring-2 ring-blue-300 scale-105 shadow"
                                              : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:scale-105")
                                          }
                                        >
                                          선택안함
                                        </button>
                                        {(() => {
                                          const main = STYLE_CATEGORIES.find((m: any) => m.id === selectedMainCategory)
                                          if (main && Array.isArray(main.subcategories)) {
                                            return main.subcategories.map((cat: { id: string; name: string; subcategories?: any[] }) => (
                                              <button
                                                key={cat.id}
                                                onClick={() => handleCategorySelect(cat.id)}
                                                className={
                                                  "p-3 rounded-xl border text-center transition-colors min-w-[120px] min-h-[40px] text-base font-semibold " +
                                                  (selectedCategory === cat.id
                                                    ? "bg-blue-100 border-blue-300 text-blue-700 ring-2 ring-blue-300 scale-105 shadow"
                                                    : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:scale-105")
                                                }
                                              >
                                                <div>{cat.name}</div>
                                              </button>
                                            ))
                                          }
                                          return null
                                        })()}
                                      </div>
                                    </div>
                                  ) : <div />}
                                  {/* 3단계: 소분류(남성/여성 등) */}
                                  {selectedMainCategory === "person" && selectedCategory ? (
                                    <div>
                                      <Label className="block mb-2">소분류</Label>
                                      <div className="flex flex-col gap-2 min-w-[120px]">
                                        <button
                                          onClick={() => {
                                            setSelectedSubcategory("")
                                          }}
                                          className={
                                            "p-3 rounded-xl border text-center transition-colors min-w-[120px] min-h-[40px] text-base font-semibold " +
                                            (selectedSubcategory === ""
                                              ? "bg-blue-100 border-blue-300 text-blue-700 ring-2 ring-blue-300 scale-105 shadow"
                                              : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:scale-105")
                                          }
                                        >
                                          선택안함
                                        </button>
                                        {(() => {
                                          const main = STYLE_CATEGORIES.find((m: any) => m.id === selectedMainCategory)
                                          const cat = main?.subcategories?.find((c: any) => c.id === selectedCategory)
                                          // 사람인 경우에만 subcategories가 있음
                                          if (selectedMainCategory === "person" && cat && Array.isArray((cat as any).subcategories)) {
                                            return (cat as any).subcategories.map((sub: { id: string; name: string; styles: { id: string; name: string }[] }) => (
                                              <button
                                                key={sub.id}
                                                onClick={() => handleSubcategorySelect(sub.id)}
                                                className={
                                                  "p-3 rounded-xl border text-center transition-colors min-w-[120px] min-h-[40px] text-base font-semibold " +
                                                  (selectedSubcategory === sub.id
                                                    ? "bg-blue-100 border-blue-300 text-blue-700 ring-2 ring-blue-300 scale-105 shadow"
                                                    : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:scale-105")
                                                }
                                              >
                                                <div>{sub.name}</div>
                                              </button>
                                            ))
                                          }
                                          return null
                                        })()}
                                      </div>
                                    </div>
                                  ) : <div />}
                                </div>
                              </CardContent>
                            </Card>

                            {/* 인종 스타일 선택 - 사람 카테고리가 선택된 경우에만 표시 */}
                            {selectedMainCategory === "person" && (
                              <Card className="border-0 shadow-none bg-gray-50 mt-4">
                                <CardHeader className="pb-3">
                                  <CardTitle className="flex items-center gap-2 text-base">
                                    <Palette className="h-4 w-4" />
                                    인종 스타일 선택
                                  </CardTitle>
                                  <CardDescription className="text-xs text-gray-500 mt-1">
                                    생성할 인물의 인종 특성을 선택하세요.
                                  </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                  <div className="flex gap-3 flex-wrap">
                                    {[
                                      { id: '기본', name: '기본', description: '지정하지 않음' },
                                      { id: '동양인', name: '동양인', description: '한국, 일본, 중국 등' },
                                      { id: '서양인', name: '서양인', description: '유럽, 북미 등' },
                                      { id: '혼합', name: '혼합', description: '다양한 특성 혼합' }
                                    ].map(style => (
                                      <button
                                        key={style.id}
                                        onClick={() => setSelectedEthnicityStyle(style.id)}
                                        className={
                                          "p-4 rounded-xl border text-center transition-colors min-w-[140px] " +
                                          (selectedEthnicityStyle === style.id
                                            ? "bg-blue-100 border-blue-300 text-blue-700 ring-2 ring-blue-300 scale-105 shadow"
                                            : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:scale-105")
                                        }
                                      >
                                        <div className="font-semibold text-base">{style.name}</div>
                                        <div className="text-xs text-gray-400 mt-1">{style.description}</div>
                                      </button>
                                    ))}
                                  </div>
                                </CardContent>
                              </Card>
                            )}

                            {/* 스타일 선택이 모두 끝난 경우에만 풍경 선택 카드 표시 */}
                            {(
                              // 대분류가 '선택안함'이면 바로 풍경 선택 카드 표시
                              selectedMainCategory === "" ||
                              // 사람 (3단계: 카테고리와 서브카테고리까지만 선택하면 됨)
                              (selectedMainCategory === "person" && selectedCategory !== null && selectedSubcategory !== null) ||
                              // 동물/사물 (2단계만 있으므로 분류까지만 선택하면 됨)
                              ((selectedMainCategory === "animal" || selectedMainCategory === "object") && selectedCategory !== null)
                            ) && (
                              <Card className="border-0 shadow-none bg-gray-50 mt-4">
                                <CardHeader className="pb-3">
                                  <CardTitle className="flex items-center gap-2 text-base">
                                    <Palette className="h-4 w-4" />
                                    풍경 선택
                                  </CardTitle>
                                  <CardDescription className="text-xs text-gray-500 mt-1">
                                    원하는 풍경 유형을 바로 선택하세요.
                                  </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                  <div className="flex gap-3 flex-wrap">
                                    <button
                                      onClick={() => setSelectedLandscape("")}
                                      className={
                                        "p-3 rounded-xl border text-center transition-colors min-w-[120px] min-h-[40px] text-base font-semibold " +
                                        (selectedLandscape === ""
                                          ? "bg-blue-100 border-blue-300 text-blue-700 ring-2 ring-blue-300 scale-105 shadow"
                                          : selectedLandscape === null
                                            ? "bg-white border-gray-200 text-gray-400"
                                            : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:scale-105")
                                      }
                                    >
                                      선택안함
                                    </button>
                                    {[
                                      { id: 'nature', name: '자연' },
                                      { id: 'city', name: '도시' },
                                      { id: 'space', name: '우주' },
                                      { id: 'digital', name: '디지털' },
                                    ].map(opt => (
                                      <button
                                        key={opt.id}
                                        onClick={() => {
                                          setSelectedLandscape(opt.id)
                                          // 스타일 선택 초기화는 필요에 따라 조정
                                        }}
                                        className={
                                          "p-3 rounded-xl border text-center transition-colors min-w-[120px] min-h-[40px] text-base font-semibold " +
                                          (selectedLandscape === opt.id
                                            ? "bg-blue-100 border-blue-300 text-blue-700 ring-2 ring-blue-300 scale-105 shadow"
                                            : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:scale-105")
                                        }
                                      >
                                        {opt.name}
                                      </button>
                                    ))}
                                  </div>
                                </CardContent>
                              </Card>
                            )}

                            {/* 이미지 설명(프롬프트) 입력란: 풍경이 '선택안함'("")이거나 실제 풍경이 선택된 경우 모두 표시 */}
                            {selectedLandscape !== null && (
                              <Card className="border-0 shadow-none bg-gray-50 mt-4">
                                <CardHeader className="pb-3">
                                  <CardTitle className="flex items-center gap-2 text-base">
                                    <Sparkles className="h-4 w-4" />
                                    이미지 설명 입력
                                  </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                  <div>
                                    <Label htmlFor="prompt">이미지 설명*</Label>
                                    <Textarea
                                      id="prompt"
                                      placeholder="생성하고 싶은 이미지를 자세히 설명해주세요..."
                                      value={prompt}
                                      onChange={(e) => setPrompt(e.target.value)}
                                      className="min-h-[100px]"
                                    />
                                  </div>
                                  {/* 프롬프트 테스트 버튼 */}
                                  <div className="flex justify-end">
                                    <Button
                                      type="button"
                                      variant="outline" 
                                      size="sm"
                                      onClick={handleTestPrompt}
                                      className="flex items-center gap-2 text-sm"
                                    >
                                      <Sparkles className="h-4 w-4" />
                                      AI 프롬프트 미리보기
                                    </Button>
                                  </div>
                                </CardContent>
                              </Card>
                            )}
                            {/* 이미지 크기 선택: 항상 표시 */}
                            <Card className="border-0 shadow-none bg-gray-50 mt-4">
                              <CardHeader className="pb-3">
                                <CardTitle className="flex items-center gap-2 text-base">
                                  <Palette className="h-4 w-4" />
                                  이미지 크기 선택
                                </CardTitle>
                              </CardHeader>
                              <CardContent className="space-y-4">
                                <div>
                                  <Label>이미지 크기</Label>
                                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-2">
                                    {PRESET_SIZES.map((size) => (
                                      <button
                                        key={size.id}
                                        onClick={() => setSelectedSize(size.id)}
                                        className={`p-3 rounded-lg border text-center transition-colors ${
                                          selectedSize === size.id
                                            ? "bg-blue-100 border-blue-300 text-blue-700"
                                            : "bg-white border-gray-200 hover:bg-gray-50"
                                        }`}
                                      >
                                        <div className="font-medium text-sm">{size.name}</div>
                                        <div className="text-xs text-gray-500 mt-1">
                                          {size.width} × {size.height}
                                        </div>
                                      </button>
                                    ))}
                                  </div>
                                </div>
                              </CardContent>
                            </Card>
                          </div>
                          {/* 미리보기 및 생성 버튼 영역은 기존대로 유지 */}
                          <div className="space-y-6">
                            <Card className="border-0 shadow-none bg-gray-50 min-h-[600px]">
                              <CardHeader className="pb-3">
                                <CardTitle className="text-base">생성 미리보기</CardTitle>
                              </CardHeader>
                              <CardContent className="h-full flex flex-col">
                                <div className="aspect-square bg-gray-100 rounded-lg flex items-center justify-center mb-4 overflow-hidden flex-shrink-0">
                                  {isGenerating ? (
                                    <div className="text-center">
                                      <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-2" />
                                      <p className="text-sm text-gray-600">생성 중...</p>
                                      <Progress value={generationProgress?.progress || 0} className="mt-2" />
                                      <p className="text-xs text-gray-500 mt-1">{generationProgress?.progress || 0}%</p>
                                      {generationProgress?.message && (
                                        <p className="text-xs text-gray-600 mt-1">{generationProgress.message}</p>
                                      )}
                                    </div>
                                  ) : previewImage ? (
                                    <div className="relative w-full h-full">
                                      <img
                                        src={previewImage.image_url}
                                        alt={previewImage.prompt}
                                        className="w-full h-full object-cover cursor-pointer"
                                        onClick={() => setShowImageModal(true)}
                                      />
                                      <div className="absolute top-2 right-2">
                                        <Button
                                          size="sm"
                                          variant="secondary"
                                          onClick={() => setShowImageModal(true)}
                                        >
                                          <Maximize2 className="h-4 w-4" />
                                        </Button>
                                      </div>
                                    </div>
                                  ) : (
                                    <div className="text-center text-gray-500">
                                      <ImageIcon className="h-12 w-12 mx-auto mb-2" />
                                      <p className="text-sm">이미지 미리보기</p>
                                    </div>
                                  )}
                                </div>

                                <div className="space-y-2 text-sm flex-grow">
                                  <div className="flex justify-between">
                                    <span className="text-gray-600">스타일:</span>
                                    <span className="font-medium">선택된 스타일</span>
                                  </div>
                                  <div className="flex justify-between">
                                    <span className="text-gray-600">크기:</span>
                                    <span className="font-medium">
                                      {getSelectedSizeData()?.width} × {getSelectedSizeData()?.height}
                                    </span>
                                  </div>
                                </div>

                                <div className="mt-auto pt-4">
                                  <Button 
                                    onClick={handleGenerateImage}
                                    disabled={!prompt.trim() || !selectedSize || isGenerating || (clientSessionTime !== null && clientSessionTime <= 0)}
                                    className="w-full text-white bg-blue-600 hover:bg-blue-700"
                                    size="lg"
                                  >
                                    {isGenerating ? (
                                      <>
                                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                        생성 중...
                                      </>
                                      ) : clientSessionTime !== null && clientSessionTime <= 0 ? (
                                        <>
                                          <RefreshCw className="h-4 w-4 mr-2" />
                                          세션 재시작 후 생성 가능
                                        </>
                                    ) : (
                                      <>
                                        <Wand2 className="h-4 w-4 mr-2" />
                                        이미지 생성
                                      </>
                                    )}
                                  </Button>
                                </div>
                              </CardContent>
                            </Card>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}

                {/* 이미지 수정 탭 */}
                {activeTab === "edit" && (
                  <div className="space-y-6">
                    <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Edit className="h-5 w-5" />
                    이미지 수정
                  </CardTitle>
                  <CardDescription>
                    기존 이미지를 업로드하거나 생성된 이미지를 수정하세요
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {/* 단계 1: 수정 방법 선택 */}
                  <div className="space-y-4">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full flex items-center justify-center text-sm font-medium bg-blue-500 text-white">
                        1
                      </div>
                      <h3 className="text-lg font-medium">수정 방법 선택</h3>
                    </div>

                    <div className="grid grid-cols-1 gap-3">
                      {/* 방법 1: 단순 프롬프트 수정 */}
                      <button
                        onClick={selectMethod1}
                        className={`p-4 rounded-lg border-2 transition-all text-left ${
                          selectedMethod === 1
                            ? 'border-blue-500 bg-blue-50' 
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <div className="flex items-center gap-3 mb-2">
                          <div className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center">
                            <span className="text-blue-600 font-medium text-xs">1</span>
                          </div>
                          <div>
                            <h4 className="font-medium text-sm">단순 설명 수정</h4>
                            <p className="text-xs text-gray-600">이미지 1개 + 수정</p>
                          </div>
                        </div>
                        <p className="text-xs text-gray-500">기존 이미지를 설명으로 전체 수정</p>
                      </button>

                    </div>
                  </div>

                  {/* 단계 2: 이미지 선택 (방법이 선택된 경우에만 표시) */}
                  {getCurrentMethod() > 0 && (
                    <div className="border-t pt-6 space-y-4">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full flex items-center justify-center text-sm font-medium bg-blue-500 text-white">
                          2
                        </div>
                        <h3 className="text-lg font-medium">
                          이미지 선택 ({getRequiredImageCount()}개 필요)
                        </h3>
                        {selectedImages.length > 0 && (
                          <span className="text-sm text-blue-600 font-medium">
                            ({selectedImages.length}/{getRequiredImageCount()} 선택됨)
                          </span>
                        )}
                      </div>

                      {selectedImages.length === 0 ? (
                        <div className="space-y-6">
                          {/* 메인 업로드 영역 */}
                          <div 
                            className={`relative group transition-all duration-300 ${
                              dragActive 
                                ? "scale-105" 
                                : "hover:scale-[1.02]"
                            }`}
                            onDragEnter={handleDrag}
                            onDragLeave={handleDrag}
                            onDragOver={handleDrag}
                            onDrop={handleDrop}
                          >
                            <div className={`
                              relative overflow-hidden rounded-xl border-2 border-dashed transition-all duration-300
                              ${dragActive 
                                ? "border-blue-500 bg-gradient-to-br from-blue-50 to-indigo-50 shadow-lg shadow-blue-100" 
                                : "border-gray-300 bg-gradient-to-br from-gray-50 to-white hover:border-blue-400 hover:bg-gradient-to-br hover:from-blue-50 hover:to-indigo-50"
                              }
                            `}>
                              {/* 배경 패턴 */}
                              <div className="absolute inset-0 opacity-5">
                                <div className="absolute top-4 left-4 w-8 h-8 border-2 border-gray-400 rounded-lg"></div>
                                <div className="absolute top-12 right-8 w-6 h-6 border-2 border-gray-400 rounded-full"></div>
                                <div className="absolute bottom-8 left-12 w-4 h-4 border-2 border-gray-400 rotate-45"></div>
                                <div className="absolute bottom-16 right-4 w-10 h-10 border-2 border-gray-400 rounded-lg"></div>
                              </div>
                              
                              <div className="relative p-12 text-center">
                                {/* 아이콘 영역 */}
                                <div className={`
                                  relative mx-auto mb-6 w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300
                                  ${dragActive 
                                    ? "bg-blue-100 shadow-lg shadow-blue-200" 
                                    : "bg-gray-100 group-hover:bg-blue-100 group-hover:shadow-lg group-hover:shadow-blue-200"
                                  }
                                `}>
                                  <Upload className={`
                                    h-8 w-8 transition-all duration-300
                                    ${dragActive 
                                      ? "text-blue-600 scale-110" 
                                      : "text-gray-500 group-hover:text-blue-600 group-hover:scale-110"
                                    }
                                  `} />
                                  {/* 애니메이션 효과 */}
                                  {dragActive && (
                                    <div className="absolute inset-0 rounded-full border-2 border-blue-300 animate-ping"></div>
                                  )}
                                </div>
                                
                                {/* 텍스트 영역 */}
                                <div className="space-y-3">
                                  <h3 className={`
                                    text-xl font-semibold transition-colors duration-300
                                    ${dragActive ? "text-blue-700" : "text-gray-800 group-hover:text-blue-700"}
                                  `}>
                                    {dragActive ? "여기에 놓으세요!" : "이미지 업로드"}
                                  </h3>
                                  <p className={`
                                    text-sm transition-colors duration-300 max-w-md mx-auto
                                    ${dragActive ? "text-blue-600" : "text-gray-600 group-hover:text-blue-600"}
                                  `}>
                                    수정할 이미지를 드래그하여 놓거나 클릭하여 선택하세요
                                  </p>
                                  <p className="text-xs text-gray-500">
                                    지원 형식: JPG, PNG, GIF, WebP
                                  </p>
                                </div>
                                
                                {/* 파일 선택 버튼 */}
                                <div className="mt-6">
                                  <input
                                    type="file"
                                    accept="image/*"
                                    multiple
                                    onChange={handleFileSelect}
                                    className="hidden"
                                    id="file-upload"
                                  />
                                  <label htmlFor="file-upload">
                                    <Button 
                                      className={`
                                        transition-all duration-300 cursor-pointer
                                        ${dragActive 
                                          ? "bg-blue-600 hover:bg-blue-700 text-white shadow-lg" 
                                          : "bg-white hover:bg-blue-50 text-gray-700 border-gray-300 hover:border-blue-400 hover:text-blue-700 shadow-sm hover:shadow-md"
                                        }
                                      `} 
                                      asChild
                                    >
                                      <span className="flex items-center gap-2">
                                        <Upload className="h-4 w-4" />
                                        파일 선택
                                      </span>
                                    </Button>
                                  </label>
                                </div>
                              </div>
                            </div>
                          </div>
                          
                          {/* 구분선 */}
                          <div className="relative">
                            <div className="absolute inset-0 flex items-center">
                              <div className="w-full border-t border-gray-200"></div>
                            </div>
                            <div className="relative flex justify-center text-sm">
                              <span className="bg-white px-4 text-gray-500">또는</span>
                            </div>
                          </div>
                          
                          {/* 갤러리 선택 버튼 */}
                          <div className="text-center mb-8">
                            <Button 
                              variant="outline" 
                              onClick={() => {
                                setShowGallerySelector(true)
                                fetchGalleryImages(1) // 갤러리 선택기 열 때 이미지 로드
                              }}
                              disabled={galleryLoading}
                              className="px-8 py-3 text-base font-medium transition-all duration-300 hover:scale-105"
                            >
                              {galleryLoading ? (
                                <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                              ) : (
                                <ImageIcon className="h-5 w-5 mr-2" />
                              )}
                              {galleryLoading ? '이미지 로딩 중...' : '갤러리에서 선택'}
                            </Button>
                            {!galleryLoading && images.length === 0 && (
                              <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                                <p className="text-sm text-amber-700">
                                  💡 갤러리에 이미지가 없습니다. 먼저 이미지를 생성해보세요.
                                </p>
                              </div>
                            )}
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-4">
                          {/* 선택된 이미지들 표시 */}
                          <div className={`grid gap-6 ${
                            selectedImages.length === 1 
                              ? 'grid-cols-1' 
                              : 'grid-cols-1 md:grid-cols-2'
                          }`}>
                            {selectedImages.map((image, index) => (
                              <div key={image.id} className="relative group">
                                <div className="absolute top-3 left-3 bg-blue-500 text-white text-xs px-2 py-1 rounded z-10 shadow-sm">
                                  이미지 {index + 1}
                                </div>
                                <div className={`bg-gray-50 rounded-lg shadow-md overflow-hidden ${
                                  selectedImages.length === 1 
                                    ? 'aspect-video' 
                                    : 'aspect-square'
                                }`}>
                                  <img
                                    src={image.url}
                                    alt={`선택된 이미지 ${index + 1}`}
                                    className="w-full h-full object-contain p-2"
                                  />
                                </div>
                                <Button
                                  variant="destructive"
                                  size="sm"
                                  onClick={() => handleRemoveImage(image.id)}
                                  className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity shadow-sm"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                                {image.type === 'gallery' && image.galleryImage && (
                                  <div className="absolute bottom-3 left-3 bg-blue-600 text-white text-xs px-2 py-1 rounded shadow-sm">
                                    갤러리
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>

                          {/* 추가 선택 옵션 */}
                          {selectedImages.length < getRequiredImageCount() && (
                            <div className="mt-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
                              <div className="text-center space-y-3">
                                <p className="text-sm font-medium text-gray-700">
                                  추가 이미지가 필요합니다 ({selectedImages.length}/{getRequiredImageCount()})
                                </p>
                                <div className="flex gap-3 justify-center">
                                  <input
                                    type="file"
                                    accept="image/*"
                                    multiple
                                    onChange={handleFileSelect}
                                    className="hidden"
                                    id="additional-file-upload"
                                  />
                                  <label htmlFor="additional-file-upload">
                                    <Button 
                                      variant="outline" 
                                      asChild 
                                      size="sm"
                                      className="transition-all duration-300 hover:scale-105"
                                    >
                                      <span className="flex items-center gap-2">
                                        <Upload className="h-4 w-4" />
                                        추가 업로드
                                      </span>
                                    </Button>
                                  </label>
                                  <Button 
                                    variant="outline" 
                                    onClick={() => {
                                      setShowGallerySelector(true)
                                      fetchGalleryImages(1) // 갤러리 선택기 열 때 이미지 로드
                                    }}
                                    disabled={galleryLoading}
                                    size="sm"
                                    className="transition-all duration-300 hover:scale-105"
                                  >
                                    {galleryLoading ? (
                                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    ) : (
                                      <ImageIcon className="h-4 w-4 mr-2" />
                                    )}
                                    {galleryLoading ? '로딩 중...' : '갤러리에서 추가'}
                                  </Button>
                                </div>
                              </div>
                            </div>
                          )}

                          <div className="text-center pt-4 border-t border-gray-200">
                            <Button 
                              variant="outline" 
                              onClick={handleRemoveAllImages} 
                              size="sm"
                              className="text-red-600 border-red-200 hover:bg-red-50 hover:border-red-300 transition-all duration-300 mb-6"
                            >
                              <Trash2 className="h-4 w-4 mr-2" />
                              모든 이미지 제거
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* 단계 3: 프롬프트 입력 (수정 방법이 선택된 경우에만 표시) */}
                  {getCurrentMethod() > 0 && (
                    <div className="border-t pt-6 space-y-4 mt-6">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full flex items-center justify-center text-sm font-medium bg-blue-500 text-white">
                          3
                        </div>
                        <h3 className="text-lg font-medium">수정 프롬프트</h3>
                      </div>
                      
                      <div>
                        <Label htmlFor="edit-prompt" className="text-sm font-medium">
                          어떻게 수정할지 설명하세요
                        </Label>
                        <Textarea
                          placeholder="예: 고양이를 강아지로 바꿔주세요"
                          className="mt-2 min-h-[80px]"
                          id="edit-prompt"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          {selectedImages.length === 1 && !maskMode && "이미지를 어떻게 수정할지 설명하세요"}
                          {selectedImages.length === 1 && maskMode && "마스킹된 영역을 어떻게 수정할지 설명하세요"}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* 이미지 생성 버튼 (방법이 선택된 경우에만 표시) */}
                  {getCurrentMethod() > 0 && (
                    <div className="border-t pt-6 mt-6">
                      <div className="space-y-4">
                        {/* 수정 실행 버튼 */}
                        <Button 
                          className="w-full bg-blue-600 hover:bg-blue-700 text-white"
                          size="lg"
                          onClick={async () => {
                            const editPrompt = (document.getElementById('edit-prompt') as HTMLTextAreaElement)?.value
                            if (!editPrompt?.trim()) {
                              toast({
                                title: "입력 필요",
                                description: '수정 내용을 입력해주세요.',
                                variant: "destructive",
                                duration: 3000,
                              })
                              return
                            }
                            
                            // 단순 이미지 수정 (방법 1)
                            if (getCurrentMethod() === 1 && selectedImages.length > 0) {
                              try {
                                setIsGenerating(true)
                                
                                // 선택된 이미지 파일 가져오기
                                let imageFile: File | null = null
                                
                                if (selectedImages[0].type === 'upload' && selectedImages[0].file) {
                                  imageFile = selectedImages[0].file
                                } else if (selectedImages[0].type === 'gallery' && selectedImages[0].url) {
                                  // 갤러리 이미지의 경우 URL에서 blob으로 변환
                                  const imageUrl = selectedImages[0].url
                                  console.log('Gallery image URL:', imageUrl, typeof imageUrl)
                                  
                                  // URL이 문자열인지 확인
                                  if (typeof imageUrl !== 'string') {
                                    throw new Error(`이미지 URL이 올바르지 않습니다: ${typeof imageUrl}`)
                                  }
                                  
                                  const response = await fetch(imageUrl)
                                  const blob = await response.blob()
                                  imageFile = new File([blob], `image_${Date.now()}.png`, { type: 'image/png' })
                                }
                                
                                if (!imageFile) {
                                  throw new Error('이미지 파일을 찾을 수 없습니다')
                                }
                                
                                // 기존 WebSocket 연결 사용
                                if (wsConnected) {
                                  // 이미지를 Base64로 변환
                                  const reader = new FileReader()
                                  reader.onload = () => {
                                    const base64Data = reader.result?.toString().split(',')[1]
                                    
                                    // WebSocket으로 이미지 수정 요청 전송
                                    wsSend({
                                      type: 'modify_image',
                                      data: {
                                        image: base64Data,
                                        edit_instruction: editPrompt
                                      }
                                    })
                                    
                                    toast({
                                      title: "이미지 수정 중",
                                      description: '이미지를 수정하고 있습니다. 잠시만 기다려주세요...',
                                      duration: 5000,
                                    })
                                  }
                                  reader.readAsDataURL(imageFile)
                                } else {
                                  throw new Error('WebSocket 연결이 없습니다. 페이지를 새로고침해주세요.')
                                }
                              } catch (error) {
                                // console.error('이미지 수정 실패:', error)
                                toast({
                                  title: "수정 실패",
                                  description: error instanceof Error ? error.message : '이미지 수정에 실패했습니다.',
                                  variant: "destructive",
                                  duration: 5000,
                                })
                              } finally {
                                setIsGenerating(false)
                              }
                            } else {
                              // 기타 경우
                              toast({
                                title: "준비 중",
                                description: '해당 수정 방법은 아직 준비 중입니다.',
                                variant: "default",
                                duration: 3000,
                              })
                            }
                          }}
                          disabled={isGenerating}
                        >
                          {isGenerating ? (
                            <>
                              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                              처리 중...
                            </>
                          ) : (
                            <>
                              <Wand2 className="h-4 w-4 mr-2" />
                              {getCurrentMethod() === 1 && "이미지 수정"}
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
                  </div>
                )}

                {/* 갤러리 탭 */}
                {activeTab === "gallery" && (
                  <div className="space-y-6">
                    <div className="flex justify-between items-center">
                      <div>
                        <h2 className="text-xl font-semibold">생성된 이미지</h2>
                        {totalImages > 0 && (
                          <p className="text-sm text-gray-600 mt-1">
                            총 {totalImages}개의 이미지
                          </p>
                        )}
                      </div>
                      <Button variant="outline" onClick={() => fetchGalleryImages(currentPage)}>
                        <RefreshCw className="h-4 w-4 mr-2" />
                        새로고침
                      </Button>
                    </div>

                    {/* 로딩 상태 */}
                    {galleryLoading && (
                      <div className="text-center py-12">
                        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
                        <p className="mt-2 text-gray-600">이미지를 불러오는 중...</p>
                      </div>
                    )}

                    {/* 이미지 그리드 */}
                    {!galleryLoading && images.length > 0 && (
                      <>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                          {images.map((image) => (
                            <Card key={image.id} className="overflow-hidden cursor-pointer hover:shadow-lg transition-shadow" onClick={() => {
                              setPreviewImage(image)
                              setShowGalleryImageModal(true)
                            }}>
                              <div className="aspect-square relative">
                                <img
                                  src={image.image_url}
                                  alt={image.prompt}
                                  className="w-full h-full object-cover"
                                />
                                <div className="absolute top-2 right-2 flex gap-1">
                                  <Button
                                    size="sm"
                                    variant="secondary"
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      handleDownloadImage(image.image_url, `generated_image_${image.id}.png`)
                                    }}
                                    title="다운로드"
                                  >
                                    <Download className="h-4 w-4" />
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="secondary"
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      setPreviewImage(image)
                                      setShowGalleryImageModal(true)
                                    }}
                                    title="확대 보기"
                                  >
                                    <Maximize2 className="h-4 w-4" />
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="destructive"
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      handleDeleteImage(image.id)
                                    }}
                                    title="삭제"
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </Button>
                                </div>
                              </div>
                              <CardContent className="p-3">
                                <p className="text-sm text-gray-600 truncate">
                                  {image.prompt || '프롬프트 없음'}
                                </p>
                                <p className="text-xs text-gray-400 mt-1">
                                  {new Date(image.created_at).toLocaleDateString()}
                                </p>
                              </CardContent>
                            </Card>
                          ))}
                        </div>

                        {/* 페이지네이션 */}
                        {totalPages > 1 && (
                          <div className="mt-8 flex justify-center items-center gap-4">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handlePageChange(currentPage - 1)}
                              disabled={currentPage === 1}
                            >
                              <ChevronLeft className="h-4 w-4" />
                              이전
                            </Button>
                            <span className="text-sm">
                              {currentPage} / {totalPages} 페이지
                            </span>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handlePageChange(currentPage + 1)}
                              disabled={currentPage === totalPages}
                            >
                              다음
                              <ChevronRight className="h-4 w-4" />
                            </Button>
                          </div>
                        )}
                      </>
                    )}

                    {/* 이미지가 없을 때 */}
                    {!galleryLoading && images.length === 0 && (
                      <div className="text-center py-12">
                        <ImageIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                        <p className="text-lg font-medium text-gray-900 mb-2">생성된 이미지가 없습니다</p>
                        <p className="text-gray-600">첫 번째 이미지를 생성해보세요</p>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        {/* 이미지 모달 */}
        <Dialog open={showImageModal} onOpenChange={setShowImageModal}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                생성된 이미지
              </DialogTitle>
              <p>
                생성된 이미지는 자동으로 갤러리에 저장됩니다.
              </p>
            </DialogHeader>
            {previewImage ? (
              <div className="space-y-6">
                {/* 이미지 표시 */}
                <div className="flex justify-center">
                  <img
                    src={previewImage.image_url}
                    alt={previewImage.prompt}
                    className="max-w-full max-h-[60vh] object-contain rounded-lg shadow-lg"
                  />
                </div>
                
                {/* 이미지 정보 */}
                <div className="space-y-4">
                  <div className="space-y-3">
                    <div>
                      <span className="text-gray-500">프롬프트:</span>
                      <p className="font-medium text-sm mt-1">{previewImage.prompt}</p>
                    </div>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-gray-500">크기:</span>
                        <p className="font-medium">{previewImage.width} × {previewImage.height}</p>
                      </div>
                      <div>
                        <span className="text-gray-500">생성일:</span>
                        <p className="font-medium">{new Date(previewImage.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* 액션 버튼 */}
                <div className="flex gap-3 justify-center">
                  <Button
                    onClick={openDownloadDialog}
                    className="flex-1"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    다운로드
                  </Button>
                  <Button
                    onClick={handleRegenerate}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    <RefreshCw className="h-4 w-4 mr-2" />
                    재생성
                  </Button>
                </div>
              </div>
            ) : isGenerating ? (
              <div className="space-y-6">
                {/* 로딩 상태 표시 */}
                <div className="flex justify-center">
                  <div className="text-center">
                    <Loader2 className="h-16 w-16 animate-spin text-blue-600 mx-auto mb-4" />
                    <p className="text-lg font-medium text-gray-900 mb-2">이미지 생성 중...</p>
                    <Progress value={generationProgress?.progress || 0} className="w-64 mx-auto" />
                    <p className="text-sm text-gray-500 mt-2">{generationProgress?.progress || 0}%</p>
                    {generationProgress?.message && (
                      <p className="text-sm text-gray-600 mt-2">{generationProgress.message}</p>
                    )}
                  </div>
                </div>
                
                {/* 프롬프트 정보 (로딩 중에도 표시) */}
                <div className="space-y-4">
                  <div>
                    <h3 className="font-medium text-gray-900 mb-2">프롬프트</h3>
                    <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg">
                      {prompt}
                    </p>
                  </div>
                </div>
              </div>
            ) : null}
          </DialogContent>
        </Dialog>

        {/* 파일 이름 변경 다운로드 다이얼로그 */}
        <Dialog open={showDownloadDialog} onOpenChange={setShowDownloadDialog}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>파일 이름 설정</DialogTitle>
              <p className="text-sm text-gray-600">
                다운로드할 파일의 이름을 입력하세요.
              </p>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label htmlFor="filename">파일 이름</Label>
                <Input
                  id="filename"
                  value={downloadFileName}
                  onChange={(e) => setDownloadFileName(e.target.value)}
                  placeholder="파일 이름을 입력하세요"
                  className="mt-1"
                />
                <p className="text-xs text-gray-500 mt-1">
                  .png 확장자는 자동으로 추가됩니다.
                </p>
              </div>
              <div className="flex gap-3 justify-end">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowDownloadDialog(false)
                    setDownloadFileName("")
                  }}
                >
                  취소
                </Button>
                <Button
                  onClick={handleDownloadWithCustomName}
                  disabled={!downloadFileName.trim()}
                >
                  <Download className="h-4 w-4 mr-2" />
                  다운로드
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* 갤러리 선택기 모달 */}
        <Dialog open={showGallerySelector} onOpenChange={setShowGallerySelector}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>갤러리에서 이미지 선택</DialogTitle>
              <p className="text-sm text-gray-600">
                생성된 이미지 중에서 수정하고 싶은 이미지를 선택하세요. (최대 {getRequiredImageCount()}개까지 선택 가능)
              </p>
              <div className="flex items-center gap-2 text-sm text-blue-600">
                <span>선택된 이미지: {gallerySelectedImages.length}개</span>
                {selectedImages.length > 0 && (
                  <span className="text-gray-500">(기존: {selectedImages.length}개)</span>
                )}
              </div>
            </DialogHeader>
            <div className="space-y-4">
              {/* 이미지 그리드 */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {images.map((image) => {
                  const isSelected = gallerySelectedImages.some(img => img.id === image.id)
                  return (
                    <Card 
                      key={image.id} 
                      className={`overflow-hidden cursor-pointer transition-all duration-200 ${
                        isSelected ? 'ring-2 ring-blue-500 bg-blue-50' : 'hover:shadow-md'
                      }`} 
                      onClick={() => handleGalleryImageToggle(image)}
                    >
                      <div className="aspect-square relative">
                        <img
                          src={image.image_url}
                          alt={image.prompt}
                          className="w-full h-full object-cover"
                        />
                        {/* 선택 표시 */}
                        {isSelected && (
                          <div className="absolute top-2 left-2 bg-blue-500 text-white rounded-full w-6 h-6 flex items-center justify-center">
                            <span className="text-xs font-bold">✓</span>
                          </div>
                        )}
                        <div className="absolute top-2 right-2">
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleDeleteImage(image.id)
                            }}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                      <CardContent className="p-4">
                        <p className="text-sm text-gray-600 line-clamp-2 mb-2">
                          {image.prompt}
                        </p>
                        <div className="flex justify-between items-center text-xs text-gray-500 mb-3">
                          <span>{image.width} × {image.height}</span>
                          <span>{new Date(image.created_at).toLocaleDateString()}</span>
                        </div>
                        {/* 빠른 액션 버튼들 */}
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={(e) => {
                              e.stopPropagation()
                              
                              // WebSocket 연결 확인
                              if (!wsConnected) {
                                toast({
        title: "연결 오류",
        description: 'WebSocket 연결이 끊어졌습니다. 페이지를 새로고침해주세요.',
        variant: "destructive",
        duration: 3000,
      })
                                return
                              }
                              
                              const originalPrompt = image.prompt
                              
                              // 생성 탭으로 이동하고 모달 열기
                              setActiveTab("generate")
                              setPrompt(originalPrompt)
                              setShowImageModal(true)
                              setIsGenerating(true)
                              setGenerationProgress({
                                status: 'starting',
                                progress: 0,
                                message: '이미지 재생성 준비 중...'
                              })
                              
                              // WebSocket으로 재생성 요청
                              setTimeout(() => {
                                const selectedSizeData = PRESET_SIZES.find(size => size.id === selectedSize)
                                
                                wsSend({
                                  type: 'generate_image',
                                  data: {
                                  prompt: originalPrompt,
                                  selected_styles: getSelectedStylesForAPI(),
                                  width: selectedSizeData?.width || 1024,
                                  height: selectedSizeData?.height || 1024,
                                  steps: 8,
                                  guidance: 3.5,
                                  seed: null
                                }
                              })
                            }, 100)
                          }}
                          className="flex-1 text-xs"
                        >
                          <RefreshCw className="h-3 w-3 mr-1" />
                          재생성
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDownloadImage(image.image_url, `generated_image_${image.id}.png`)
                          }}
                          className="flex-1 text-xs"
                        >
                          <Download className="h-3 w-3 mr-1" />
                          저장
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>
            
            {images.length === 0 && (
              <div className="text-center py-12">
                <ImageIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-lg font-medium text-gray-900 mb-2">생성된 이미지가 없습니다</p>
                <p className="text-gray-600">먼저 이미지를 생성해보세요</p>
              </div>
            )}
            
            {/* 페이지네이션 */}
            {totalPages > 1 && (
              <div className="flex justify-center items-center gap-2 mt-6 pt-4 border-t">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage <= 1}
                  className="flex items-center gap-1"
                >
                  <ChevronLeft className="h-4 w-4" />
                  이전
                </Button>
                
                <div className="flex items-center gap-1">
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    let pageNum
                    if (totalPages <= 5) {
                      pageNum = i + 1
                    } else if (currentPage <= 3) {
                      pageNum = i + 1
                    } else if (currentPage >= totalPages - 2) {
                      pageNum = totalPages - 4 + i
                    } else {
                      pageNum = currentPage - 2 + i
                    }
                    
                    return (
                      <Button
                        key={pageNum}
                        variant={currentPage === pageNum ? "default" : "outline"}
                        size="sm"
                        onClick={() => handlePageChange(pageNum)}
                        className="w-8 h-8 p-0"
                      >
                        {pageNum}
                      </Button>
                    )
                  })}
                </div>
                
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage >= totalPages}
                  className="flex items-center gap-1"
                >
                  다음
                  <ChevronRight className="h-4 w-4" />
                </Button>
                
                <span className="text-sm text-gray-500 ml-2">
                  {currentPage} / {totalPages} 페이지
                </span>
              </div>
            )}
          </div>
          
          <div className="flex justify-between items-center mt-6 pt-4 border-t">
              <div className="text-sm text-gray-600">
                {gallerySelectedImages.length > 0 && (
                  <span>선택된 이미지: {gallerySelectedImages.length}개</span>
                )}
              </div>
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  onClick={() => {
                    setGallerySelectedImages([])
                    setShowGallerySelector(false)
                  }}
                >
                  취소
                </Button>
                <Button 
                  onClick={handleGallerySelectionComplete}
                  disabled={gallerySelectedImages.length === 0}
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                >
                  선택하기 ({gallerySelectedImages.length}개)
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* 갤러리 이미지 모달 */}
        <Dialog open={showGalleryImageModal} onOpenChange={setShowGalleryImageModal}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                {previewImage?.prompt?.includes('[Modified]') ? '수정된 이미지' : '갤러리 이미지'}
              </DialogTitle>
            </DialogHeader>
            {previewImage ? (
              <div className="space-y-6">
                {/* 이미지 표시 */}
                <div className="flex justify-center">
                  <img
                    src={previewImage.image_url}
                    alt={previewImage.prompt}
                    className="max-w-full max-h-[60vh] object-contain rounded-lg shadow-lg"
                  />
                </div>
                
                {/* 이미지 정보 */}
                <div className="space-y-4">
                  
                  <div className="space-y-3">
                    <div>
                      <span className="text-gray-500">프롬프트:</span>
                      <p className="font-medium text-sm mt-1">{previewImage.prompt}</p>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                      <div>
                        <span className="text-gray-500">크기:</span>
                        <p className="font-medium">{previewImage.width} × {previewImage.height}</p>
                      </div>
                      <div>
                        <span className="text-gray-500">생성일:</span>
                        <p className="font-medium">{new Date(previewImage.created_at).toLocaleDateString()}</p>
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* 액션 버튼 */}
                <div className="flex gap-2 justify-center">
                  <Button
                    onClick={openDownloadDialog}
                    className="flex-1"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    다운로드
                  </Button>
                  <Button
                    onClick={() => {
                      // 갤러리 모달 닫고 생성 탭으로 이동
                      setShowGalleryImageModal(false)
                      setActiveTab("generate")
                      
                      // 프롬프트 설정
                      const originalPrompt = previewImage.prompt
                      setPrompt(originalPrompt)
                      
                      // 이미지 생성 모달 열기
                      setShowImageModal(true)
                      setIsGenerating(true)
                      setGenerationProgress({
                        status: 'starting',
                        progress: 0,
                        message: '이미지 재생성 준비 중...'
                      })
                      
                      // WebSocket으로 재생성 요청
                      setTimeout(() => {
                        if (wsConnected) {
                          const selectedSizeData = PRESET_SIZES.find(size => size.id === selectedSize)
                          
                          wsSend({
                            type: 'generate_image',
                            data: {
                              prompt: originalPrompt,
                              selected_styles: getSelectedStylesForAPI(),
                              width: selectedSizeData?.width || 1024,
                              height: selectedSizeData?.height || 1024,
                              steps: 8,
                              guidance: 3.5,
                              seed: null
                            }
                          })
                        } else {
                          toast({
          title: "연결 오류",
          description: 'WebSocket 연결이 끊어졌습니다. 페이지를 새로고침해주세요.',
          variant: "destructive",
          duration: 3000,
        })
                          setIsGenerating(false)
                          setGenerationProgress(null)
                          setShowImageModal(false)
                        }
                      }, 100)
                    }}
                    variant="outline"
                    className="flex-1"
                  >
                    <RefreshCw className="h-4 w-4 mr-2" />
                    재생성
                  </Button>
                  <Button
                    onClick={() => handleDeleteImage(previewImage.id)}
                    variant="destructive"
                    className="flex-1"
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    삭제
                  </Button>
                </div>
              </div>
            ) : null}
          </DialogContent>
        </Dialog>
      </div>
  )
}