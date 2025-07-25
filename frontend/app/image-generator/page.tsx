"use client"

import { useState, useEffect, useRef, useMemo, useCallback } from "react"
import { Navigation } from "@/components/navigation"
import { useAuth } from "@/hooks/use-auth"
import { tokenUtils } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"

import { Separator } from "@/components/ui/separator"

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
  Filter
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


const PRESET_SIZES = [
  { id: 'square', name: '정사각형', width: 512, height: 512 },
  { id: 'portrait', name: '세로형', width: 512, height: 768 },
  { id: 'landscape', name: '가로형', width: 768, height: 512 },
  { id: 'wide', name: '와이드', width: 1024, height: 512 }
]

// 세션 상태 인터페이스 추가
interface SessionStatus {
  success: boolean
  has_session: boolean
  pod_id?: string
  pod_status?: string
  session_created_at?: string
  session_expires_at?: string
  processing_expires_at?: string
  total_generations: number
  session_remaining_seconds?: number
  processing_remaining_seconds?: number
  message: string
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
  const [images, setImages] = useState<GeneratedImage[]>([])
  const [loading, setLoading] = useState(false)

  // 모델 선택 기능 제거 - 워크플로우에 정의된 모델 자동 사용
  const [selectedWorkflow, setSelectedWorkflow] = useState<string>("")

  const [selectedStyle, setSelectedStyle] = useState<string>("realistic")
  const [selectedSize, setSelectedSize] = useState<string>("square")

  
  // 세션 상태 관리 추가
  const [sessionStatus, setSessionStatus] = useState<SessionStatus | null>(null)
  const [sessionLoading, setSessionLoading] = useState(false)
  
  // 클라이언트 사이드 카운트다운 상태
  const [clientSessionTime, setClientSessionTime] = useState<number | null>(null)
  const [clientProcessingTime, setClientProcessingTime] = useState<number | null>(null)
  
  // 세션 자동 재시도 상태
  const [sessionRetryCount, setSessionRetryCount] = useState(0)
  const [isAutoRetrying, setIsAutoRetrying] = useState(false)
  
  // 세션 만료 추적 상태
  const [sessionExpiredNaturally, setSessionExpiredNaturally] = useState(false)
  const [lastKnownSessionStatus, setLastKnownSessionStatus] = useState<SessionStatus | null>(null)
  
  // 인증 상태 추가
  const { token, isAuthenticated } = useAuth()
  const [accessToken, setAccessToken] = useState<string | null>(null)
  
  // 토큰 초기화
  useEffect(() => {
    const storedToken = tokenUtils.getToken()
    if (storedToken) {
      setAccessToken(storedToken)
    }
  }, [token])
  
  // 생성 파라미터
  const [prompt, setPrompt] = useState("")
  // 고급 설정 제거 - 간단한 인터페이스만 유지
  
  // UI 상태
  const [activeTab, setActiveTab] = useState("generate")
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationProgress, setGenerationProgress] = useState(0)
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
      
      const currentToken = accessToken || tokenUtils.getToken()
      if (!currentToken) {
        console.error('인증 토큰이 없습니다. 로그인이 필요합니다.')
        return false
      }
      
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
      const response = await fetch(`${backendUrl}/api/v1/user-sessions/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${currentToken}`,
        },
        body: JSON.stringify({})
      })
      
      if (response.ok) {
        const data = await response.json()
        setSessionStatus(data)
        
        // 클라이언트 사이드 타이머 업데이트
        setClientSessionTime(data.session_remaining_seconds || null)
        setClientProcessingTime(data.processing_remaining_seconds || null)
        
        // 성공 시 재시도 카운트 리셋
        setSessionRetryCount(0)
        setIsAutoRetrying(false)
        
        console.log('세션 생성 성공:', data)
        return true
        
      } else {
        console.error(`세션 생성 실패 (시도 ${retryAttempt + 1}/${maxRetries + 1}):`, response.statusText)
        
        // 재시도 로직
        if (retryAttempt < maxRetries) {
          const nextAttempt = retryAttempt + 1
          setSessionRetryCount(nextAttempt)
          
          console.log(`${retryDelay/1000}초 후 세션 생성 재시도 (${nextAttempt}/${maxRetries})...`)
          
          setTimeout(async () => {
            await createUserSession(true, nextAttempt)
          }, retryDelay)
          
          return false
        } else {
          console.error('세션 생성 최대 재시도 횟수 초과')
          setIsAutoRetrying(false)
          return false
        }
      }
    } catch (error) {
      console.error(`세션 생성 오류 (시도 ${retryAttempt + 1}/${maxRetries + 1}):`, error)
      
      // 재시도 로직
      if (retryAttempt < maxRetries) {
        const nextAttempt = retryAttempt + 1
        setSessionRetryCount(nextAttempt)
        
        console.log(`${retryDelay/1000}초 후 세션 생성 재시도 (${nextAttempt}/${maxRetries})...`)
        
        setTimeout(async () => {
          await createUserSession(true, nextAttempt)
        }, retryDelay)
        
        return false
      } else {
        console.error('세션 생성 최대 재시도 횟수 초과')
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

  const checkSessionStatus = async () => {
    try {
      const currentToken = accessToken || tokenUtils.getToken()
      if (!currentToken) {
        console.error('인증 토큰이 없습니다.')
        return
      }
      
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
      const response = await fetch(`${backendUrl}/api/v1/user-sessions/status`, {
        headers: {
          'Authorization': `Bearer ${currentToken}`,
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        
        // 세션이 없는 경우 처리
        if (!data || !data.pod_id) {
          // 이전에 세션이 있었고 15분이 지나서 자연스럽게 만료된 경우 자동 재생성하지 않음
          if (lastKnownSessionStatus && lastKnownSessionStatus.pod_id) {
            console.log('세션이 정상적으로 만료되었습니다. 사용자가 수동으로 재시작해야 합니다.')
            setSessionExpiredNaturally(true)
            setSessionStatus(null) // 세션 상태를 null로 설정
            return
          }
          
          // 페이지 로드 시 처음부터 세션이 없었거나 생성 실패인 경우에만 자동 생성
          if (!sessionExpiredNaturally && !sessionLoading && !isAutoRetrying) {
            console.log('초기 세션이 없습니다. 자동으로 새 세션을 생성합니다.')
            await createUserSession(true, 0) // 자동 재시도로 세션 생성
          }
          return
        }
        
        // 유효한 세션이 있는 경우
        setLastKnownSessionStatus(data) // 마지막 알려진 세션 상태 저장
        setSessionExpiredNaturally(false) // 자연 만료 플래그 리셋
        setSessionStatus(data)
        
        // 클라이언트 사이드 타이머 업데이트
        setClientSessionTime(data.session_remaining_seconds || null)
        setClientProcessingTime(data.processing_remaining_seconds || null)
        
      } else {
        console.error('세션 상태 확인 실패:', response.statusText)
        
        // API 오류 시에는 자연 만료가 아닌 경우에만 세션 생성 시도
        if (!sessionExpiredNaturally && !sessionLoading && !isAutoRetrying) {
          console.log('세션 상태 확인 실패. 새 세션 생성을 시도합니다.')
          await createUserSession(true, 0)
        }
      }
    } catch (error) {
      console.error('세션 상태 확인 오류:', error)
      
      // 네트워크 오류 시에는 자연 만료가 아닌 경우에만 세션 생성 시도
      if (!sessionExpiredNaturally && !sessionLoading && !isAutoRetrying) {
        console.log('네트워크 오류. 새 세션 생성을 시도합니다.')
        await createUserSession(true, 0)
      }
    }
  }

  // 페이지 로드 시 세션 상태 확인 (자동 생성하지 않음)
  useEffect(() => {
    let isActive = true
    const initializeSession = async () => {
      if (accessToken && isActive) {
        // 페이지 로드 시에는 세션 상태만 확인하고 자동 생성은 checkSessionStatus에서 처리
        await checkSessionStatus()
      }
    }
    initializeSession()
    return () => { isActive = false }
  }, [accessToken])

  // 세션 상태 폴링 (5초마다)
  useEffect(() => {
    if (!sessionStatus?.has_session) return

    const interval = setInterval(checkSessionStatus, 5000)
    return () => clearInterval(interval)
  }, [sessionStatus?.has_session])

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


  // 생성된 이미지 목록 가져오기
  const fetchImages = async () => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        console.error('No access token found')
        return
      }

      const response = await fetch('/api/image-generation/my-images', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
      const data = await response.json()
      if (data.success) {
        setImages(data.images)
      }
    } catch (error) {
      console.error('Failed to fetch images:', error)
    }
  }

  useEffect(() => {
    fetchImages()
  }, [])

  // 프롬프트 최적화 테스트 함수
  const handleTestPrompt = async () => {
    if (!prompt.trim() && !getCombinedPromptKeywords()) {
      alert('테스트할 프롬프트를 입력하거나 스타일을 선택해주세요.')
      return
    }

    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        alert('로그인이 필요합니다.')
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
        
        alert(resultMessage)
        
        // 콘솔에도 상세 정보 출력
        console.log('🤖 프롬프트 최적화 테스트 결과:', testData)
      } else {
        alert('프롬프트 테스트 실패: ' + (testData.detail || '알 수 없는 오류'))
      }
    } catch (error) {
      console.error('Prompt test failed:', error)
      alert('프롬프트 테스트 중 오류가 발생했습니다.')
    }
  }

  const handleGenerateImage = async () => {
    if (!prompt.trim()) return

    setIsGenerating(true)
    setGenerationProgress(0)

    // 선택값을 명시적으로 전달
    const selectedSizeData = PRESET_SIZES.find(size => size.id === selectedSize)

    // 프론트엔드 로그: 요청 파라미터
    console.log('[이미지 생성 요청] 파라미터:', {
      prompt,
      style: selectedMainCategory,
      category: selectedCategory,
      subcategory: selectedSubcategory,
      detailStyle: selectedDetailStyle,
      landscape: selectedLandscape,
      width: selectedSizeData?.width || 512,
      height: selectedSizeData?.height || 512,
      workflow_id: selectedWorkflow || 'basic_txt2img',
    })

    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        throw new Error('No access token found')
      }

      const response = await fetch('/api/image-generation/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          prompt: prompt.trim() || getCombinedPromptKeywords(), // 사용자 입력 프롬프트 우선
          selected_styles: getSelectedStylesForAPI(), // 스타일 선택 정보 추가
          width: selectedSizeData?.width || 1024,
          height: selectedSizeData?.height || 1024,
          steps: 8,  // Flux 기본 스텝 수
          guidance: 3.5,  // Flux 가이던스 스케일
          seed: null  // 랜덤 시드
        })
      })

      console.log('Request body:', {
        prompt: prompt.trim() || getCombinedPromptKeywords(),
        selected_styles: getSelectedStylesForAPI(),
        width: selectedSizeData?.width || 1024,
        height: selectedSizeData?.height || 1024,
        steps: 8,
        guidance: 3.5,
        seed: null
      })

      // 프론트엔드 로그: 응답 상태
      console.log('[이미지 생성 응답] status:', response.status)
      const data = await response.json()
      console.log('[이미지 생성 응답] data:', data)

      if (data.success) {
        // 진행률 시뮬레이션 (실제로는 백엔드에서 진행률을 받아와야 함)
        const progressInterval = setInterval(() => {
          setGenerationProgress(prev => {
            if (prev >= 90) {
              clearInterval(progressInterval)
              return prev
            }
            return prev + Math.random() * 10
          })
        }, 200)

        // 2초 후 완료 처리 (실제로는 백엔드 응답을 기다려야 함)
        setTimeout(() => {
          setIsGenerating(false)
          setGenerationProgress(100)
          
          // 1x1 투명 이미지인 경우 placeholder 이미지로 교체
          let imageUrl = data.image_url
          if (data.image_url.includes('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')) {
            imageUrl = '/api/placeholder-image'
          }
          
          const newImage: GeneratedImage = {
            id: data.storage_id || Date.now().toString(),
            prompt,
            width: selectedSizeData?.width || 512,
            height: selectedSizeData?.height || 512,
            image_url: imageUrl,
            created_at: new Date().toISOString(),
            status: 'completed'
          }
          
          setImages(prev => [newImage, ...prev])
          setPreviewImage(newImage)
          setShowImageModal(true)
          setPrompt("")

          return
        }, 2000);
        
        if (!data.storage_id) {
          console.error('No job ID received from backend')
          setIsGenerating(false)
          return
        }
        
        let pollCount = 0
        const maxPollCount = 120 // 최대 2분 (120초)
        
        const pollProgress = setInterval(async () => {
          try {
            pollCount++
            
            // 최대 재시도 횟수 초과 시 중단
            if (pollCount > maxPollCount) {
              clearInterval(pollProgress)
              setIsGenerating(false)
              console.error('Generation timeout after 2 minutes')
              return
            }
            
            const progressResponse = await fetch(`/api/comfyui/progress/${data.storage_id}`)
            
            if (!progressResponse.ok) {
              console.error('Progress check failed:', progressResponse.status)
              return
            }
            
            const progressData = await progressResponse.json()
            
            if (progressData.success) {
              setGenerationProgress(progressData.progress)
              
              if (progressData.status === 'completed') {
                clearInterval(pollProgress)
                setIsGenerating(false)
                setGenerationProgress(100)
                
                // 새로운 이미지를 목록에 추가
                const newImage: GeneratedImage = {
                  id: progressData.image_id || data.storage_id,
                  prompt,
                  width: selectedSizeData?.width || 512,
                  height: selectedSizeData?.height || 512,
                  image_url: progressData.image_url || '/placeholder-image.jpg',
                  created_at: new Date().toISOString(),
                  status: 'completed'
                }
                
                setImages(prev => [newImage, ...prev])
                setPrompt("")
              } else if (progressData.status === 'failed') {
                clearInterval(pollProgress)
                setIsGenerating(false)
                console.error('Image generation failed:', progressData.error)
              }
            }
          } catch (error) {
            console.error('Failed to poll progress:', error)
            
            // 연속 실패 시 중단
            if (pollCount > 10) {
              clearInterval(pollProgress)
              setIsGenerating(false)
              console.error('Too many polling failures, stopping')
            }
          }
        }, 1000)
        
        // 타임아웃 설정 (5분)
        setTimeout(() => {
          clearInterval(pollProgress)
          setIsGenerating(false)
        }, 300000)
      }
    } catch (error) {
      console.error('[이미지 생성 에러]', error)
      setIsGenerating(false)
      setGenerationProgress(0)
      alert('이미지 생성에 실패했습니다: ' + (error instanceof Error ? error.message : '알 수 없는 오류'))
    }
  }

  const handleDeleteImage = async (storage_id: string) => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        console.error('No access token found')
        return
      }

      await fetch(`/api/image-generation/images/${storage_id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
      setImages(prev => prev.filter(img => img.id !== storage_id))
    } catch (error) {
      console.error('Failed to delete image:', error)
    }
  }

  const handleDownloadImage = async (imageUrl: string, filename: string) => {
    try {
      const response = await fetch(imageUrl)
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Failed to download image:', error)
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
        alert(`최대 ${maxAllowed}개까지 이미지를 선택할 수 있습니다.`)
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
        alert(`최대 ${maxAllowed}개까지 이미지를 선택할 수 있습니다.`)
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
      alert('먼저 마스크를 그려주세요.')
      return
    }

    const inpaintPrompt = (document.getElementById('inpaint-prompt') as HTMLTextAreaElement)?.value
    if (!inpaintPrompt.trim()) {
      alert('수정 프롬프트를 입력해주세요.')
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
        alert('인페인팅이 시작되었습니다!')
        // 진행 상황 모니터링 로직...
      } else {
        alert('인페인팅 시작에 실패했습니다.')
      }
    } catch (error) {
      console.error('Inpainting error:', error)
      alert('인페인팅 중 오류가 발생했습니다.')
    } finally {
      setIsGenerating(false)
    }
  }

  // 재생성 기능
  const handleRegenerate = () => {
    if (previewImage) {
      // 이전 이미지를 DB에 저장 (이미지 목록에 추가)
      setImages(prev => [previewImage, ...prev])
      
      // 모달에서 로딩 상태로 변경
      setPreviewImage(null)
      setIsGenerating(true)
      setGenerationProgress(0)
      
      // 진행률 시뮬레이션
      const progressInterval = setInterval(() => {
        setGenerationProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval)
            return prev
          }
          return prev + Math.random() * 10
        })
      }, 200)
      
      // 새로운 이미지 생성
      setTimeout(() => {
        clearInterval(progressInterval)
        setIsGenerating(false)
        setGenerationProgress(100)
        
        const selectedSizeData = PRESET_SIZES.find(size => size.id === selectedSize)
        
        const newTestImage: GeneratedImage = {
          id: `img_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          prompt: previewImage?.prompt || prompt,
          width: selectedSizeData?.width || 512,
          height: selectedSizeData?.height || 512,
          image_url: 'https://picsum.photos/512/512?random=' + Date.now(), // 새로운 랜덤 이미지
          created_at: new Date().toISOString(),
          status: 'completed'
        }
        
        setPreviewImage(newTestImage) // 모달에 새 이미지 표시
      }, 2000) // 2초 후 완료
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
        alert('이미지 파일만 업로드할 수 있습니다.')
        return
      }
      
      const remainingSlots = 2 - selectedImages.length
      const filesToUpload = files.slice(0, remainingSlots)
      
      if (files.length > remainingSlots) {
        alert(`최대 2개까지 선택 가능합니다. ${remainingSlots}개 파일만 업로드됩니다.`)
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
        alert('이미지 파일만 선택할 수 있습니다.')
        return
      }
      
      const remainingSlots = 2 - selectedImages.length
      const filesToUpload = imageFiles.slice(0, remainingSlots)
      
      if (imageFiles.length > remainingSlots) {
        alert(`최대 2개까지 선택 가능합니다. ${remainingSlots}개 파일만 업로드됩니다.`)
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

  const selectMethod2 = () => {
    setMaskMode(true)
    setSelectedMethod(2)
    // 방법 2: 마스킹 수정 모드로 전환 (이미지 1개 필요)
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

  const selectMethod3 = () => {
    setMaskMode(false)
    setSelectedMethod(3)
    // 방법 3: 이미지 합성 모드로 전환 (이미지 2개 필요)
    // 이미지가 2개 미만이면 추가 선택 안내
  }

  const selectMethod4 = () => {
    setMaskMode(true)
    setSelectedMethod(4)
    // 방법 4: 복합 마스킹 모드로 전환 (이미지 2개 필요)
    // 이미지가 2개 미만이면 추가 선택 안내
  }

  // 현재 선택된 방법 확인
  const getCurrentMethod = () => {
    return selectedMethod
  }

  // 선택된 방법에 따른 필요한 이미지 개수
  const getRequiredImageCount = () => {
    if (selectedMethod === 1 || selectedMethod === 2) {
      return 1
    } else if (selectedMethod === 3 || selectedMethod === 4) {
      return 2
    }
    return 0
  }

  // 스타일 선택 상태 (4단계)
  const [selectedMainCategory, setSelectedMainCategory] = useState<string | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [selectedSubcategory, setSelectedSubcategory] = useState<string | null>(null)
  const [selectedDetailStyle, setSelectedDetailStyle] = useState<string | null>(null)
  // 풍경 선택 상태
  const [selectedLandscape, setSelectedLandscape] = useState<string | null>(null)

  // 스타일 선택 관련 핸들러
  const handleMainCategorySelect = (mainId: string | null) => {
    setSelectedMainCategory(mainId)
    setSelectedCategory(null)
    setSelectedSubcategory(null)
    setSelectedDetailStyle(null)
    setSelectedLandscape(null)  // 풍경 선택도 초기화
  }
  const handleCategorySelect = (categoryId: string | null) => {
    setSelectedCategory(categoryId)
    setSelectedSubcategory(null)
    setSelectedDetailStyle(null)
    setSelectedLandscape(null)  // 풍경 선택도 초기화
  }
  const handleSubcategorySelect = (subcategoryId: string | null) => {
    setSelectedSubcategory(subcategoryId)
    setSelectedDetailStyle(null)
    setSelectedLandscape(null)  // 풍경 선택도 초기화
  }
  const handleDetailStyleSelect = (styleId: string | null) => {
    setSelectedDetailStyle(styleId)
    setSelectedLandscape(null)  // 풍경 선택도 초기화
  }
  const handleLandscapeSelect = (landscapeId: string) => {
    setSelectedLandscape(landscapeId)
    // 풍경을 선택하면 스타일 선택 상태 초기화
    setSelectedMainCategory(null)
    setSelectedCategory(null)
    setSelectedSubcategory(null)
    setSelectedDetailStyle(null)
  }
  const handleLandscapeOptionSelect = (optionId: string) => {
    if (selectedLandscape === 'landscape') {
      setSelectedCategory(optionId)
      setSelectedMainCategory(null)
      setSelectedSubcategory(null)
      setSelectedDetailStyle(null)
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
      if (selectedCategory && selectedSubcategory && selectedDetailStyle) {
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

        // 지역 키워드 추가
        const regionId = selectedDetailStyle.includes('east') ? 'east' : 'west'
        if (PROMPT_KEYWORDS.region[regionId]) {
          keywords.push(PROMPT_KEYWORDS.region[regionId])
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
    
    // 세부스타일 매핑 (예시로 기본적인 매핑만 구현)
    if (selectedDetailStyle) {
      const styleMapping: Record<string, string> = {
        'realistic': '사실적',
        'anime': '애니메이션',
        'cartoon': '만화',
        'painting': '유화',
        'watercolor': '수채화',
        'digital': '디지털아트',
        'minimal': '미니멀',
        'fantasy': '판타지'
      }
      selectedStyles['세부스타일'] = styleMapping[selectedDetailStyle] || '사실적'
    }
    
    // 분위기 매핑 (기본값으로 밝은 사용)
    selectedStyles['분위기'] = '밝은'  // 디폴트
    
    console.log('🎨 선택된 스타일 정보:', selectedStyles)
    return selectedStyles
  }

  return (
    <div className="min-h-screen bg-gray-50">
        <Navigation />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">이미지 생성 & 수정</h1>
            <p className="text-gray-600 mt-2">ComfyUI를 사용하여 AI 이미지를 생성하고 수정하세요</p>
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
                  {sessionStatus ? (
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
                        <p className="text-sm mb-2">{sessionStatus.message}</p>
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
                        
                        {/* 세션 시간이 만료되거나 실패한 경우 재시작 버튼 표시 */}
                        {(sessionStatus.pod_status === 'failed' || (clientSessionTime !== null && clientSessionTime <= 0)) && (
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
                        
                        {/* 세션 시간이 만료된 경우 안내 메시지 표시 */}
                        {clientSessionTime !== null && clientSessionTime <= 0 && sessionStatus.pod_status !== 'failed' && (
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
                                          setSelectedDetailStyle("")
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
                                            setSelectedDetailStyle("")
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
                                            setSelectedDetailStyle("")
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
                                  {/* 4단계: 세부 스타일(동양/서양 등) */}
                                  {selectedMainCategory === "person" && selectedCategory && selectedSubcategory ? (
                                    <div>
                                      <Label className="block mb-2">세부 스타일</Label>
                                      <div className="flex flex-col gap-2 min-w-[120px]">
                                        <button
                                          onClick={() => setSelectedDetailStyle("")}
                                          className={
                                            "p-3 rounded-xl border text-center transition-colors min-w-[120px] min-h-[40px] text-base font-semibold " +
                                            (selectedDetailStyle === ""
                                              ? "bg-blue-100 border-blue-300 text-blue-700 ring-2 ring-blue-300 scale-105 shadow"
                                              : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:scale-105")
                                          }
                                        >
                                          선택안함
                                        </button>
                                        {(() => {
                                          const main = STYLE_CATEGORIES.find((m: any) => m.id === selectedMainCategory)
                                          const cat = main?.subcategories?.find((c: any) => c.id === selectedCategory)
                                          const sub = (cat as any)?.subcategories?.find((s: any) => s.id === selectedSubcategory)
                                          if (sub && Array.isArray(sub.styles)) {
                                            return sub.styles.map((style: { id: string; name: string }) => (
                                              <button
                                                key={style.id}
                                                onClick={() => handleDetailStyleSelect(style.id)}
                                                className={
                                                  "p-3 rounded-xl border text-center transition-colors min-w-[120px] min-h-[40px] text-base font-semibold " +
                                                  (selectedDetailStyle === style.id
                                                    ? "bg-blue-100 border-blue-300 text-blue-700 ring-2 ring-blue-300 scale-105 shadow"
                                                    : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:scale-105")
                                                }
                                              >
                                                <div>{style.name}</div>
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

                            {/* 스타일 선택이 모두 끝난 경우에만 풍경 선택 카드 표시 */}
                            {(
                              // 대분류가 '선택안함'이면 바로 풍경 선택 카드 표시
                              selectedMainCategory === "" ||
                              // 사람
                              (selectedMainCategory === "person" && selectedCategory !== null && selectedSubcategory !== null && selectedDetailStyle !== null) ||
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
                                      <Progress value={generationProgress} className="mt-2" />
                                      <p className="text-xs text-gray-500 mt-1">{generationProgress}%</p>
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

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
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

                      {/* 방법 2: 마스킹 수정 */}
                      <button
                        onClick={selectMethod2}
                        className={`p-4 rounded-lg border-2 transition-all text-left ${
                          selectedMethod === 2
                            ? 'border-green-500 bg-green-50' 
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <div className="flex items-center gap-3 mb-2">
                          <div className="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center">
                            <span className="text-green-600 font-medium text-xs">2</span>
                          </div>
                          <div>
                            <h4 className="font-medium text-sm">마스킹 수정</h4>
                            <p className="text-xs text-gray-600">이미지 1개 + 마스킹 + 프롬프트</p>
                          </div>
                        </div>
                        <p className="text-xs text-gray-500">특정 영역만 선택하여 수정</p>
                      </button>

                      {/* 방법 3: 이미지 합성 */}
                      <button
                        onClick={selectMethod3}
                        className={`p-4 rounded-lg border-2 transition-all text-left ${
                          selectedMethod === 3
                            ? 'border-purple-500 bg-purple-50' 
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <div className="flex items-center gap-3 mb-2">
                          <div className="w-6 h-6 bg-purple-100 rounded-full flex items-center justify-center">
                            <span className="text-purple-600 font-medium text-xs">3</span>
                          </div>
                          <div>
                            <h4 className="font-medium text-sm">이미지 합성</h4>
                            <p className="text-xs text-gray-600">이미지 2개 + 프롬프트</p>
                          </div>
                        </div>
                        <p className="text-xs text-gray-500">두 이미지를 설명과 함께 합성</p>
                      </button>

                      {/* 방법 4: 복합 마스킹 */}
                      <button
                        onClick={selectMethod4}
                        className={`p-4 rounded-lg border-2 transition-all text-left ${
                          selectedMethod === 4
                            ? 'border-orange-500 bg-orange-50' 
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <div className="flex items-center gap-3 mb-2">
                          <div className="w-6 h-6 bg-orange-100 rounded-full flex items-center justify-center">
                            <span className="text-orange-600 font-medium text-xs">4</span>
                          </div>
                          <div>
                            <h4 className="font-medium text-sm">복합 마스킹</h4>
                            <p className="text-xs text-gray-600">이미지 2개 + 마스킹 + 프롬프트</p>
                          </div>
                        </div>
                        <p className="text-xs text-gray-500">두 이미지의 특정 영역 합성</p>
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
                                    {getRequiredImageCount() === 1 
                                      ? "수정할 이미지를 드래그하여 놓거나 클릭하여 선택하세요"
                                      : "합성할 이미지들을 드래그하여 놓거나 클릭하여 선택하세요"
                                    }
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
                              onClick={() => setShowGallerySelector(true)}
                              disabled={images.length === 0}
                              className="px-8 py-3 text-base font-medium transition-all duration-300 hover:scale-105"
                            >
                              <ImageIcon className="h-5 w-5 mr-2" />
                              갤러리에서 선택
                            </Button>
                            {images.length === 0 && (
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
                                    onClick={() => setShowGallerySelector(true)}
                                    disabled={images.length === 0}
                                    size="sm"
                                    className="transition-all duration-300 hover:scale-105"
                                  >
                                    <ImageIcon className="h-4 w-4 mr-2" />
                                    갤러리에서 추가
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
                          {selectedImages.length === 2 && !maskMode && "두 이미지를 어떻게 합성할지 설명하세요"}
                          {selectedImages.length === 2 && maskMode && "마스킹된 영역을 어떻게 합성할지 설명하세요"}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* 단계 4: 추가 도구 (방법이 선택된 경우에만 표시) */}
                  {getCurrentMethod() > 0 && (
                    <div className="border-t pt-6 space-y-4 mt-6">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full flex items-center justify-center text-sm font-medium bg-blue-500 text-white">
                          4
                        </div>
                        <h3 className="text-lg font-medium">
                          {getCurrentMethod() === 1 && "수정 실행"}
                          {getCurrentMethod() === 2 && "마스킹 도구"}
                          {getCurrentMethod() === 3 && "합성 실행"}
                          {getCurrentMethod() === 4 && "마스킹 도구"}
                        </h3>
                      </div>
                      
                      <div className="space-y-4">
                        {/* 마스킹 도구 (방법 2, 4에서만 표시) */}
                        {(getCurrentMethod() === 2 || getCurrentMethod() === 4) && (
                          <div className="space-y-3">
                            <Label className="text-sm font-medium">수정할 영역 선택</Label>
                            
                            {/* 방법 4번일 때 이미지 선택 버튼 */}
                            {getCurrentMethod() === 4 && selectedImages.length > 1 && (
                              <div className="flex gap-2">
                                <Button
                                  variant={activeImageIndex === 0 ? "default" : "outline"}
                                  size="sm"
                                  onClick={() => setActiveImageIndex(0)}
                                  className="flex-1"
                                >
                                  이미지 1 마스킹
                                </Button>
                                <Button
                                  variant={activeImageIndex === 1 ? "default" : "outline"}
                                  size="sm"
                                  onClick={() => setActiveImageIndex(1)}
                                  className="flex-1"
                                >
                                  이미지 2 마스킹
                                </Button>
                              </div>
                            )}
                            
                            <div className="space-y-3">
                              {/* 브러시 크기 조절 */}
                              <div>
                                <Label htmlFor="brush-size" className="text-xs text-gray-600">
                                  브러시 크기: {brushSize}px
                                </Label>
                                <input
                                  id="brush-size"
                                  type="range"
                                  min="5"
                                  max="50"
                                  value={brushSize}
                                  onChange={(e) => setBrushSize(Number(e.target.value))}
                                  className="w-full mt-1"
                                />
                              </div>

                              {/* 마스킹 색상 선택 */}
                              <div>
                                <Label htmlFor="mask-color" className="text-xs text-gray-600">
                                  마스킹 색상
                                </Label>
                                <div className="flex items-center gap-3 mt-1">
                                  <input
                                    id="mask-color"
                                    type="color"
                                    value={maskColor}
                                    onChange={(e) => setMaskColor(e.target.value)}
                                    className="w-12 h-8 rounded border cursor-pointer"
                                  />
                                  <div className="flex gap-1">
                                    {['#FFFFFF', '#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF', '#FFA500', '#800080'].map((color) => (
                                      <button
                                        key={color}
                                        onClick={() => setMaskColor(color)}
                                        className={`w-6 h-6 rounded border-2 transition-all ${
                                          maskColor === color ? 'border-gray-800 scale-110' : 'border-gray-300 hover:border-gray-500'
                                        }`}
                                        style={{ backgroundColor: color }}
                                        title={color}
                                      />
                                    ))}
                                  </div>
                                </div>
                              </div>

                              {/* 마스킹 캔버스 */}
                              <div className="relative border rounded-lg overflow-hidden bg-gray-50">
                                <img
                                  ref={imageRef}
                                  src={selectedImages[activeImageIndex]?.url}
                                  alt={`마스킹 대상 이미지 ${activeImageIndex + 1}`}
                                  className="w-full h-auto max-h-64 object-contain"
                                  style={{ display: maskMode ? 'block' : 'none' }}
                                />
                                <canvas
                                  ref={canvasRef}
                                  className="absolute top-0 left-0 w-full h-full cursor-crosshair"
                                  style={{ display: maskMode ? 'block' : 'none' }}
                                  onMouseDown={handleMouseDown}
                                  onMouseMove={handleMouseMove}
                                  onMouseUp={handleMouseUp}
                                  onMouseLeave={handleMouseUp}
                                />
                              </div>

                              <Button
                                variant="outline"
                                onClick={clearMask}
                                size="sm"
                                className="w-full"
                              >
                                <Eraser className="h-4 w-4 mr-2" />
                                마스크 지우기
                              </Button>
                            </div>
                          </div>
                        )}

                        {/* 수정 실행 버튼 */}
                        <Button 
                          className="w-full bg-blue-600 hover:bg-blue-700 text-white"
                          size="lg"
                          onClick={() => {
                            const editPrompt = (document.getElementById('edit-prompt') as HTMLTextAreaElement)?.value
                            if (!editPrompt?.trim()) {
                              alert('수정 내용을을 입력해주세요.')
                              return
                            }
                            
                            // TODO: 각 방법에 따른 수정 API 호출
                            console.log('수정 실행:', {
                              method: getCurrentMethod(),
                              prompt: editPrompt,
                              images: selectedImages,
                              maskMode: maskMode
                            })
                          }}
                        >
                          <Wand2 className="h-4 w-4 mr-2" />
                          {getCurrentMethod() === 1 && "이미지 수정"}
                          {getCurrentMethod() === 2 && "마스킹 수정"}
                          {getCurrentMethod() === 3 && "이미지 합성"}
                          {getCurrentMethod() === 4 && "복합 마스킹"}
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
                <h2 className="text-xl font-semibold">생성된 이미지</h2>
                <Button variant="outline" onClick={fetchImages}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  새로고침
                </Button>
              </div>

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
                  </Card>
                ))}
              </div>

              {images.length === 0 && (
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
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500">모델:</span>
                      <p className="font-medium">{previewImage.prompt}</p>
                    </div>
                    <div>
                      <span className="text-gray-500">크기:</span>
                      <p className="font-medium">{previewImage.width} × {previewImage.height}</p>
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
                    <Progress value={generationProgress} className="w-64 mx-auto" />
                    <p className="text-sm text-gray-500 mt-2">{generationProgress}%</p>
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
                            const originalPrompt = image.prompt
                            setActiveTab("generate")
                            setTimeout(() => {
                              setPrompt(originalPrompt)
                              setTimeout(() => {
                                handleGenerateImage()
                              }, 100)
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
                갤러리 이미지
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
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500">모델:</span>
                      <p className="font-medium">{previewImage.prompt}</p>
                    </div>
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
                      // 동일한 프롬프트로 재생성
                      const originalPrompt = previewImage.prompt
                      setShowGalleryImageModal(false)
                      setActiveTab("generate") // 생성 탭으로 이동
                      
                      // 프롬프트 설정 후 이미지 생성 실행
                      setTimeout(() => {
                        setPrompt(originalPrompt)
                        // 생성 버튼 자동 클릭을 위해 약간의 딜레이
                        setTimeout(() => {
                          handleGenerateImage()
                        }, 100)
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