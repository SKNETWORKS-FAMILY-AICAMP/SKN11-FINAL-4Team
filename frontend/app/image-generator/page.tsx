"use client"

import { useState, useEffect, useRef, useMemo, useCallback } from "react"
import { Navigation } from "@/components/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
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
  Settings,
  Upload,
  Loader2,
  History,
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
  negative_prompt?: string
  model: string
  width: number
  height: number
  steps: number
  cfg_scale: number
  seed: number
  image_url: string
  created_at: string
  status: 'generating' | 'completed' | 'failed'
  progress?: number
}

interface ComfyUIModel {
  id: string
  name: string
  type: string
  description?: string
}

interface WorkflowTemplate {
  id: string
  name: string
  description: string
  category: string
  tags: string[]
  input_parameters: Record<string, any>
  is_active: boolean
}

const PRESET_STYLES = [
  { id: 'realistic', name: '사실적', description: '실제 사진과 같은 고품질 이미지' },
  { id: 'artistic', name: '예술적', description: '예술 작품 스타일의 이미지' },
  { id: 'anime', name: '애니메이션', description: '애니메이션/만화 스타일' },
  { id: 'portrait', name: '인물 사진', description: '인물 중심의 포트레이트' },
  { id: 'landscape', name: '풍경', description: '자연 풍경 및 배경' }
]

const PRESET_SIZES = [
  { id: 'square', name: '정사각형', width: 512, height: 512 },
  { id: 'portrait', name: '세로형', width: 512, height: 768 },
  { id: 'landscape', name: '가로형', width: 768, height: 512 },
  { id: 'wide', name: '와이드', width: 1024, height: 512 }
]

export default function ImageGeneratorPage() {
  const [images, setImages] = useState<GeneratedImage[]>([])
  const [workflows, setWorkflows] = useState<WorkflowTemplate[]>([])
  const [loading, setLoading] = useState(false)
  // 모델 선택 기능 제거 - 워크플로우에 정의된 모델 자동 사용
  const [selectedWorkflow, setSelectedWorkflow] = useState<string>("")
  const [selectedStyle, setSelectedStyle] = useState<string>("") // 빈 문자열로 초기화
  const [selectedSize, setSelectedSize] = useState<string>("")
  
  // 생성 파라미터
  const [prompt, setPrompt] = useState("")
  // 커스텀 템플릿에서는 부정 프롬프트 사용하지 않음
  const [steps, setSteps] = useState(20)
  const [cfgScale, setCfgScale] = useState(7)
  const [seed, setSeed] = useState(-1)
  
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
  
  // 갤러리 필터 상태
  const [galleryFilter, setGalleryFilter] = useState<string>("all")
  const [tempGalleryFilter, setTempGalleryFilter] = useState<string>("all")
  const [isFilterModalOpen, setIsFilterModalOpen] = useState(false)
  
  // 필터링된 이미지 목록
  const filteredImages = useMemo(() => {
    if (galleryFilter === "all") {
      return images
    }
    
    const [width, height] = galleryFilter.split("x").map(Number)
    return images.filter(image => image.width === width && image.height === height)
  }, [images, galleryFilter])
  
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
  const lastPointRef = useRef<{x: number, y: number} | null>(null)

  // 모델 목록 가져오기 제거 - 워크플로우에 정의된 모델 자동 사용

  // 워크플로우 목록 가져오기
  useEffect(() => {
    const fetchWorkflows = async () => {
      try {
        const response = await fetch('/api/comfyui/workflows')
        const data = await response.json()
        if (data.success) {
          // workflows가 배열인지 확인
          const workflowsArray = Array.isArray(data.workflows) ? data.workflows : []
          setWorkflows(workflowsArray)
          if (workflowsArray.length > 0) {
            setSelectedWorkflow(workflowsArray[0].id)
          } else {
            // 워크플로우가 없으면 기본 워크플로우 설정
            setSelectedWorkflow('basic_txt2img')
          }
        }
      } catch (error) {
        console.error('Failed to fetch workflows:', error)
        // 에러 발생 시 빈 배열로 설정하고 기본 워크플로우 설정
        setWorkflows([])
        setSelectedWorkflow('custom_workflow')
      }
    }

    fetchWorkflows()
  }, [])

  // 생성된 이미지 목록 가져오기
  const fetchImages = async () => {
    try {
      const response = await fetch('/api/comfyui/images')
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

  const handleGenerateImage = async () => {
    if (!prompt.trim()) return

    setIsGenerating(true)
    setGenerationProgress(0)

    // 테스트용: ComfyUI 호출 없이 바로 완료 처리
    setTimeout(() => {
      setIsGenerating(false)
      setGenerationProgress(100)
      
      const selectedSizeData = PRESET_SIZES.find(size => size.id === selectedSize)
      
      const testImage: GeneratedImage = {
        id: `img_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        prompt,
        negative_prompt: '',
        model: 'test-model',
        width: selectedSizeData?.width || 512,
        height: selectedSizeData?.height || 512,
        steps,
        cfg_scale: cfgScale,
        seed: Math.floor(Math.random() * 1000000),
        image_url: 'https://picsum.photos/512/512?random=' + Date.now(), // 랜덤 테스트 이미지
        created_at: new Date().toISOString(),
        status: 'completed'
      }
      
      setImages(prev => [testImage, ...prev])
      setPreviewImage(testImage) // 미리보기 영역에 표시
      setShowImageModal(true) // 모달 띄우기
      setPrompt("")
    }, 2000) // 2초 후 완료
  }

  const handleDeleteImage = async (imageId: string) => {
    try {
      await fetch(`/api/comfyui/images/${imageId}`, {
        method: 'DELETE'
      })
      setImages(prev => prev.filter(img => img.id !== imageId))
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

  const getSelectedStyleData = () => {
    if (!selectedStyle) return null
    return PRESET_STYLES.find(style => style.id === selectedStyle)
  }

  // 갤러리에서 이미지 선택 함수
  const handleSelectFromGallery = (image: GeneratedImage) => {
    const maxAllowed = getRequiredImageCount()
    if (selectedImages.length >= maxAllowed) {
      alert(`최대 ${maxAllowed}개까지 이미지를 선택할 수 있습니다.`)
      return
    }
    
    const newImage = {
      id: `gallery_${image.id}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      url: image.image_url,
      type: 'gallery' as const,
      galleryImage: image
    }
    
    setSelectedImages(prev => [...prev, newImage])
  }

  // 갤러리에서 추가 선택 함수
  const handleAddFromGallery = (image: GeneratedImage) => {
    const currentCount = selectedImages.length
    const maxAllowed = getRequiredImageCount()
    const remainingSlots = maxAllowed - currentCount
    
    if (remainingSlots <= 0) {
      alert(`최대 ${maxAllowed}개까지 이미지를 선택할 수 있습니다.`)
      return
    }
    
    const newImage = {
      id: `gallery_${image.id}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      url: image.image_url,
      type: 'gallery' as const,
      galleryImage: image
    }
    
    setSelectedImages(prev => [...prev, newImage])
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
          prompt: inpaintPrompt,
          model: 'default', // 워크플로우에서 정의된 모델 사용
          steps,
          cfg_scale: cfgScale
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
          negative_prompt: '',
          model: 'test-model',
          width: selectedSizeData?.width || 512,
          height: selectedSizeData?.height || 512,
          steps,
          cfg_scale: cfgScale,
          seed: Math.floor(Math.random() * 1000000),
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
    setSelectedStyle("")
    setPreviewImage(null)
    setShowImageModal(false)
    setShowGalleryImageModal(false)
    setShowDownloadDialog(false)
    setDownloadFileName("")
    setShowGallerySelector(false)
    setIsFilterModalOpen(false)
    setSelectedImages([])
    setSelectedMethod(0)
    setGalleryFilter("all")
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

  // 필터 관련 함수들
  const handleApplyFilters = () => {
    setGalleryFilter(tempGalleryFilter)
    setIsFilterModalOpen(false)
  }

  const handleOpenFilterModal = () => {
    setTempGalleryFilter(galleryFilter)
    setIsFilterModalOpen(true)
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
                    <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Wand2 className="h-5 w-5" />
                  이미지 생성 설정
                </CardTitle>
                <CardDescription>
                  프롬프트를 입력하고 스타일을 설정하여 AI 이미지를 생성하세요
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* 생성 설정 */}
                  <div className="lg:col-span-2 space-y-6">
                    <Card className="border-0 shadow-none bg-gray-50">
                      <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base">
                          <Sparkles className="h-4 w-4" />
                          프롬프트 설정
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div>
                          <Label htmlFor="prompt">프롬프트 *</Label>
                          <Textarea
                            id="prompt"
                            placeholder="생성하고 싶은 이미지를 자세히 설명해주세요..."
                            value={prompt}
                            onChange={(e) => setPrompt(e.target.value)}
                            className="min-h-[100px]"
                          />
                        </div>
                        {/* 커스텀 템플릿에서는 부정 프롬프트 사용하지 않아 제거 */}
                      </CardContent>
                    </Card>

                    <Card className="border-0 shadow-none bg-gray-50">
                      <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base">
                          <Palette className="h-4 w-4" />
                          스타일 및 크기 설정
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div>
                          <Label>스타일 프리셋</Label>
                          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-2">
                            <button
                              onClick={() => setSelectedStyle("")}
                              className={`p-3 rounded-lg border text-left transition-colors ${
                                selectedStyle === ""
                                  ? "bg-blue-100 border-blue-300 text-blue-700"
                                  : "bg-white border-gray-200 hover:bg-gray-50"
                              }`}
                            >
                              <div className="font-medium text-sm">스타일 없음</div>
                              <div className="text-xs text-gray-500 mt-1">기본 스타일 사용</div>
                            </button>
                            {PRESET_STYLES.map((style) => (
                              <button
                                key={style.id}
                                onClick={() => setSelectedStyle(style.id)}
                                className={`p-3 rounded-lg border text-left transition-colors ${
                                  selectedStyle === style.id
                                    ? "bg-blue-100 border-blue-300 text-blue-700"
                                    : "bg-white border-gray-200 hover:bg-gray-50"
                                }`}
                              >
                                <div className="font-medium text-sm">{style.name}</div>
                                <div className="text-xs text-gray-500 mt-1">{style.description}</div>
                              </button>
                            ))}
                          </div>
                        </div>

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

                  {/* 미리보기 및 생성 버튼 */}
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
                            <span className="text-gray-600">워크플로우:</span>
                            <span className="font-medium">{Array.isArray(workflows) ? workflows.find(w => w.id === selectedWorkflow)?.name || '기본' : '기본'}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-600">스타일:</span>
                            <span className="font-medium">
                              {selectedStyle ? getSelectedStyleData()?.name : "기본 스타일"}
                            </span>
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
                            disabled={!prompt.trim() || !selectedSize || isGenerating}
                            className="w-full text-white bg-blue-600 hover:bg-blue-700"
                            size="lg"
                          >
                            {isGenerating ? (
                              <>
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                생성 중...
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

              <div className="flex items-center gap-2 mb-4">
                <Dialog open={isFilterModalOpen} onOpenChange={setIsFilterModalOpen}>
                  <DialogTrigger asChild>
                    <Button variant="outline" className="flex items-center gap-2" onClick={handleOpenFilterModal}>
                      <Filter className="h-4 w-4" />
                      필터
                      {galleryFilter !== "all" && (
                        <Badge variant="secondary" className="ml-1">
                          1
                        </Badge>
                      )}
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-md">
                    <DialogHeader>
                      <DialogTitle>크기 필터 설정</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-6">
                      {/* 크기 필터 */}
                      <div>
                        <h3 className="font-medium text-sm text-gray-900 mb-3">이미지 크기</h3>
                        <div className="grid grid-cols-1 gap-2">
                          <button
                            onClick={() => setTempGalleryFilter("all")}
                            className={`text-left px-3 py-2 rounded-md text-sm transition-colors ${tempGalleryFilter === "all"
                              ? "bg-blue-100 text-blue-700 border border-blue-200"
                              : "bg-gray-50 text-gray-700 hover:bg-gray-100 border border-gray-200"
                              }`}
                          >
                            모든 크기
                          </button>
                          {PRESET_SIZES.map((size) => (
                            <button
                              key={size.id}
                              onClick={() => setTempGalleryFilter(`${size.width}x${size.height}`)}
                              className={`text-left px-3 py-2 rounded-md text-sm transition-colors ${tempGalleryFilter === `${size.width}x${size.height}`
                                ? "bg-blue-100 text-blue-700 border border-blue-200"
                                : "bg-gray-50 text-gray-700 hover:bg-gray-100 border border-gray-200"
                                }`}
                            >
                              {size.name} ({size.width} × {size.height})
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                    {/* 적용하기 버튼 */}
                    <div className="flex justify-end gap-2 pt-4 border-t">
                      <Button
                        variant="outline"
                        onClick={() => setIsFilterModalOpen(false)}
                      >
                        취소
                      </Button>
                      <Button
                        onClick={handleApplyFilters}
                        className="bg-blue-600 hover:bg-blue-700"
                      >
                        적용하기
                      </Button>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {filteredImages.map((image) => (
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
                      <div className="absolute top-2 right-2 flex gap-2">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={(e) => {
                            e.stopPropagation()
                            setPreviewImage(image)
                            setShowGalleryImageModal(true)
                          }}
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
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>

              {filteredImages.length === 0 && (
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
                      <p className="font-medium">{previewImage.model}</p>
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
                      <div className="flex justify-between items-center text-xs text-gray-500">
                        <span>{image.width} × {image.height}</span>
                        <span>{new Date(image.created_at).toLocaleDateString()}</span>
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
                      <p className="font-medium">{previewImage.model}</p>
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
                <div className="flex gap-3 justify-center">
                  <Button
                    onClick={openDownloadDialog}
                    className="flex-1"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    다운로드
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