"use client"

import { useState, useEffect, useRef } from "react"
import { Navigation } from "@/components/navigation"
import { RequireAuth } from "@/components/auth/protected-route"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
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
  Sliders
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

const PRESET_STYLES = [
  { id: 'realistic', name: '사실적', description: '실제 사진과 같은 고품질 이미지' },
  { id: 'artistic', name: '예술적', description: '예술 작품 스타일의 이미지' },
  { id: 'anime', name: '애니메이션', description: '애니메이션/만화 스타일' },
  { id: 'portrait', name: '인물 사진', description: '인물 중심의 포트레이트' },
  { id: 'landscape', name: '풍경', description: '자연 풍경 및 배경' },
  { id: 'abstract', name: '추상화', description: '추상적이고 창의적인 디자인' }
]

const PRESET_SIZES = [
  { id: 'square', name: '정사각형', width: 512, height: 512 },
  { id: 'portrait', name: '세로형', width: 512, height: 768 },
  { id: 'landscape', name: '가로형', width: 768, height: 512 },
  { id: 'wide', name: '와이드', width: 1024, height: 512 }
]

export default function ImageGeneratorPage() {
  const [images, setImages] = useState<GeneratedImage[]>([])
  const [models, setModels] = useState<ComfyUIModel[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedModel, setSelectedModel] = useState<string>("")
  const [selectedStyle, setSelectedStyle] = useState<string>("realistic")
  const [selectedSize, setSelectedSize] = useState<string>("square")
  
  // 생성 파라미터
  const [prompt, setPrompt] = useState("")
  const [negativePrompt, setNegativePrompt] = useState("")
  const [steps, setSteps] = useState(20)
  const [cfgScale, setCfgScale] = useState(7)
  const [seed, setSeed] = useState(-1)
  
  // UI 상태
  const [activeTab, setActiveTab] = useState("generate")
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationProgress, setGenerationProgress] = useState(0)
  const [selectedImage, setSelectedImage] = useState<GeneratedImage | null>(null)
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [uploadedImageUrl, setUploadedImageUrl] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [maskMode, setMaskMode] = useState(false)
  const [isDrawing, setIsDrawing] = useState(false)
  const [brushSize, setBrushSize] = useState(20)
  const [lastPoint, setLastPoint] = useState<{x: number, y: number} | null>(null)
  
  // Canvas refs
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imageRef = useRef<HTMLImageElement>(null)

  // 모델 목록 가져오기
  useEffect(() => {
    const fetchModels = async () => {
      try {
        // ComfyUI 모델 목록 API 호출
        const response = await fetch('/api/comfyui/models')
        const data = await response.json()
        if (data.success) {
          setModels(data.models)
          if (data.models.length > 0) {
            setSelectedModel(data.models[0].id)
          }
        }
      } catch (error) {
        console.error('Failed to fetch models:', error)
      }
    }

    fetchModels()
  }, [])

  // 생성된 이미지 목록 가져오기
  useEffect(() => {
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

    fetchImages()
  }, [])

  const handleGenerateImage = async () => {
    if (!prompt.trim()) return

    setIsGenerating(true)
    setGenerationProgress(0)

    try {
      const selectedSizeData = PRESET_SIZES.find(size => size.id === selectedSize)
      const response = await fetch('/api/comfyui/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt,
          negative_prompt: negativePrompt,
          model: selectedModel,
          style: selectedStyle,
          width: selectedSizeData?.width || 512,
          height: selectedSizeData?.height || 512,
          steps,
          cfg_scale: cfgScale,
          seed: seed === -1 ? Math.floor(Math.random() * 1000000) : seed
        })
      })

      const data = await response.json()
      
      if (data.success) {
        // 생성 진행 상황 모니터링
        const jobId = data.job_id
        const pollProgress = setInterval(async () => {
          try {
            const progressResponse = await fetch(`/api/comfyui/progress/${jobId}`)
            const progressData = await progressResponse.json()
            
            if (progressData.success) {
              setGenerationProgress(progressData.progress)
              
              if (progressData.status === 'completed') {
                clearInterval(pollProgress)
                setIsGenerating(false)
                setGenerationProgress(100)
                
                // 새로운 이미지를 목록에 추가
                const newImage: GeneratedImage = {
                  id: progressData.image_id,
                  prompt,
                  negative_prompt: negativePrompt,
                  model: selectedModel,
                  width: selectedSizeData?.width || 512,
                  height: selectedSizeData?.height || 512,
                  steps,
                  cfg_scale: cfgScale,
                  seed: progressData.seed,
                  image_url: progressData.image_url,
                  created_at: new Date().toISOString(),
                  status: 'completed'
                }
                
                setImages(prev => [newImage, ...prev])
                setPrompt("")
                setNegativePrompt("")
              } else if (progressData.status === 'failed') {
                clearInterval(pollProgress)
                setIsGenerating(false)
                console.error('Image generation failed:', progressData.error)
              }
            }
          } catch (error) {
            console.error('Failed to poll progress:', error)
          }
        }, 1000)
        
        // 타임아웃 설정 (5분)
        setTimeout(() => {
          clearInterval(pollProgress)
          setIsGenerating(false)
        }, 300000)
      }
    } catch (error) {
      console.error('Failed to generate image:', error)
      setIsGenerating(false)
    }
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

  const getSelectedSizeData = () => {
    return PRESET_SIZES.find(size => size.id === selectedSize)
  }

  const getSelectedStyleData = () => {
    return PRESET_STYLES.find(style => style.id === selectedStyle)
  }

  // 파일 업로드 핸들러
  const handleFileUpload = (file: File) => {
    if (file && file.type.startsWith('image/')) {
      setUploadedFile(file)
      const reader = new FileReader()
      reader.onload = (e) => {
        setUploadedImageUrl(e.target?.result as string)
      }
      reader.readAsDataURL(file)
    }
  }

  // 파일 선택 핸들러
  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      handleFileUpload(file)
    }
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
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0])
    }
  }

  // 업로드된 이미지 제거
  const handleRemoveUploadedImage = () => {
    setUploadedFile(null)
    setUploadedImageUrl(null)
    setMaskMode(false)
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

  // 마스크 그리기 종료
  const stopMaskDrawing = () => {
    setMaskMode(false)
  }

  // 마스크 지우기
  const clearMask = () => {
    const canvas = canvasRef.current
    if (canvas) {
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height)
      }
    }
  }

  // Canvas 마우스 이벤트
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!maskMode) return
    setIsDrawing(true)
    
    const canvas = canvasRef.current
    if (canvas) {
      const rect = canvas.getBoundingClientRect()
      const scaleX = canvas.width / rect.width
      const scaleY = canvas.height / rect.height
      
      const x = (e.clientX - rect.left) * scaleX
      const y = (e.clientY - rect.top) * scaleY
      
      setLastPoint({ x, y })
      
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.globalCompositeOperation = 'source-over'
        ctx.fillStyle = 'rgba(255, 255, 255, 0.8)'
        ctx.beginPath()
        ctx.arc(x, y, brushSize / 2, 0, 2 * Math.PI)
        ctx.fill()
      }
    }
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!maskMode || !isDrawing) return
    
    const canvas = canvasRef.current
    if (canvas && lastPoint) {
      const rect = canvas.getBoundingClientRect()
      const scaleX = canvas.width / rect.width
      const scaleY = canvas.height / rect.height
      
      const x = (e.clientX - rect.left) * scaleX
      const y = (e.clientY - rect.top) * scaleY
      
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.globalCompositeOperation = 'source-over'
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)'
        ctx.lineWidth = brushSize
        ctx.lineCap = 'round'
        ctx.lineJoin = 'round'
        
        ctx.beginPath()
        ctx.moveTo(lastPoint.x, lastPoint.y)
        ctx.lineTo(x, y)
        ctx.stroke()
        
        setLastPoint({ x, y })
      }
    }
  }

  const handleMouseUp = () => {
    setIsDrawing(false)
    setLastPoint(null)
  }

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
          model: selectedModel,
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

  return (
    <RequireAuth>
      <div className="min-h-screen bg-gray-50">
        <Navigation />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">이미지 생성 & 수정</h1>
            <p className="text-gray-600 mt-2">ComfyUI를 사용하여 AI 이미지를 생성하고 수정하세요</p>
          </div>

          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="generate" className="flex items-center gap-2">
                <Wand2 className="h-4 w-4" />
                이미지 생성
              </TabsTrigger>
              <TabsTrigger value="edit" className="flex items-center gap-2">
                <Edit className="h-4 w-4" />
                이미지 수정
              </TabsTrigger>
              <TabsTrigger value="gallery" className="flex items-center gap-2">
                <ImageIcon className="h-4 w-4" />
                갤러리
              </TabsTrigger>
            </TabsList>

            {/* 이미지 생성 탭 */}
            <TabsContent value="generate" className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* 생성 설정 */}
                <div className="lg:col-span-2 space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Sparkles className="h-5 w-5" />
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
                      <div>
                        <Label htmlFor="negative-prompt">네거티브 프롬프트</Label>
                        <Textarea
                          id="negative-prompt"
                          placeholder="생성하지 않았으면 하는 요소들을 입력하세요..."
                          value={negativePrompt}
                          onChange={(e) => setNegativePrompt(e.target.value)}
                          className="min-h-[80px]"
                        />
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Palette className="h-5 w-5" />
                        스타일 및 크기 설정
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div>
                        <Label>스타일 프리셋</Label>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-2">
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

                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Sliders className="h-5 w-5" />
                        고급 설정
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div>
                        <Label htmlFor="model">모델 선택</Label>
                        <Select value={selectedModel} onValueChange={setSelectedModel}>
                          <SelectTrigger>
                            <SelectValue placeholder="모델을 선택하세요" />
                          </SelectTrigger>
                          <SelectContent>
                            {models.map((model) => (
                              <SelectItem key={model.id} value={model.id}>
                                {model.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                          <Label htmlFor="steps">스텝 수: {steps}</Label>
                          <input
                            id="steps"
                            type="range"
                            min="1"
                            max="100"
                            value={steps}
                            onChange={(e) => setSteps(parseInt(e.target.value))}
                            className="w-full mt-2"
                          />
                        </div>
                        <div>
                          <Label htmlFor="cfg-scale">CFG Scale: {cfgScale}</Label>
                          <input
                            id="cfg-scale"
                            type="range"
                            min="1"
                            max="20"
                            step="0.5"
                            value={cfgScale}
                            onChange={(e) => setCfgScale(parseFloat(e.target.value))}
                            className="w-full mt-2"
                          />
                        </div>
                        <div>
                          <Label htmlFor="seed">시드</Label>
                          <Input
                            id="seed"
                            type="number"
                            value={seed}
                            onChange={(e) => setSeed(parseInt(e.target.value))}
                            placeholder="-1 (랜덤)"
                            className="mt-2"
                          />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>

                {/* 미리보기 및 생성 버튼 */}
                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle>생성 미리보기</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="aspect-square bg-gray-100 rounded-lg flex items-center justify-center mb-4">
                        {isGenerating ? (
                          <div className="text-center">
                            <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-2" />
                            <p className="text-sm text-gray-600">생성 중...</p>
                            <Progress value={generationProgress} className="mt-2" />
                            <p className="text-xs text-gray-500 mt-1">{generationProgress}%</p>
                          </div>
                        ) : (
                          <div className="text-center text-gray-500">
                            <ImageIcon className="h-12 w-12 mx-auto mb-2" />
                            <p className="text-sm">이미지 미리보기</p>
                          </div>
                        )}
                      </div>
                      
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-600">스타일:</span>
                          <span className="font-medium">{getSelectedStyleData()?.name}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">크기:</span>
                          <span className="font-medium">
                            {getSelectedSizeData()?.width} × {getSelectedSizeData()?.height}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">스텝:</span>
                          <span className="font-medium">{steps}</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Button 
                    onClick={handleGenerateImage}
                    disabled={!prompt.trim() || isGenerating}
                    className="w-full"
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
              </div>
            </TabsContent>

            {/* 이미지 수정 탭 */}
            <TabsContent value="edit" className="space-y-6">
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
                  {!uploadedImageUrl ? (
                    <div 
                      className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                        dragActive 
                          ? "border-blue-400 bg-blue-50" 
                          : "border-gray-300 hover:border-gray-400"
                      }`}
                      onDragEnter={handleDrag}
                      onDragLeave={handleDrag}
                      onDragOver={handleDrag}
                      onDrop={handleDrop}
                    >
                      <Upload className={`h-12 w-12 mx-auto mb-4 ${
                        dragActive ? "text-blue-600" : "text-gray-400"
                      }`} />
                      <p className="text-lg font-medium text-gray-900 mb-2">이미지 업로드</p>
                      <p className="text-sm text-gray-600 mb-4">
                        수정하고 싶은 이미지를 드래그하여 놓거나 클릭하여 선택하세요
                      </p>
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleFileSelect}
                        className="hidden"
                        id="file-upload"
                      />
                      <label htmlFor="file-upload">
                        <Button variant="outline" asChild className="cursor-pointer">
                          <span>
                            <Upload className="h-4 w-4 mr-2" />
                            파일 선택
                          </span>
                        </Button>
                      </label>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      {/* 업로드된 이미지 미리보기 */}
                      <div className="relative">
                        <div className="relative inline-block">
                          <img
                            ref={imageRef}
                            src={uploadedImageUrl}
                            alt="업로드된 이미지"
                            className="w-full max-w-md mx-auto rounded-lg shadow-md"
                          />
                          {maskMode && (
                            <canvas
                              ref={canvasRef}
                              onMouseDown={handleMouseDown}
                              onMouseMove={handleMouseMove}
                              onMouseUp={handleMouseUp}
                              onMouseLeave={handleMouseUp}
                              className="absolute top-0 left-0 cursor-crosshair rounded-lg"
                              style={{ 
                                pointerEvents: maskMode ? 'auto' : 'none',
                                border: maskMode ? '2px solid #3b82f6' : 'none'
                              }}
                            />
                          )}
                        </div>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={handleRemoveUploadedImage}
                          className="absolute top-2 right-2"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>

                      {/* 마스크 그리기 컨트롤 */}
                      {maskMode && (
                        <Card className="bg-blue-50 border-blue-200">
                          <CardContent className="p-4">
                            <div className="flex items-center justify-between mb-4">
                              <h3 className="font-medium text-blue-900">마스크 그리기 모드</h3>
                              <div className="flex gap-2">
                                <Button variant="outline" size="sm" onClick={clearMask}>
                                  지우기
                                </Button>
                                <Button variant="outline" size="sm" onClick={stopMaskDrawing}>
                                  완료
                                </Button>
                              </div>
                            </div>
                            <div className="space-y-3">
                              <div>
                                <Label htmlFor="brush-size">브러시 크기: {brushSize}px</Label>
                                <input
                                  id="brush-size"
                                  type="range"
                                  min="5"
                                  max="100"
                                  value={brushSize}
                                  onChange={(e) => setBrushSize(parseInt(e.target.value))}
                                  className="w-full mt-2"
                                />
                              </div>
                              <p className="text-sm text-blue-700">
                                수정하고 싶은 영역을 마우스로 드래그하여 마스크를 그리세요.
                              </p>
                            </div>
                          </CardContent>
                        </Card>
                      )}

                      {/* 이미지 수정 옵션 */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <Card>
                          <CardHeader>
                            <CardTitle className="text-lg">img2img 생성</CardTitle>
                            <CardDescription>
                              업로드된 이미지를 기반으로 새로운 이미지를 생성합니다
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div>
                              <Label htmlFor="img2img-prompt">프롬프트</Label>
                              <Textarea
                                id="img2img-prompt"
                                placeholder="이미지를 어떻게 변형하고 싶나요?"
                                className="min-h-[80px]"
                              />
                            </div>
                            <div>
                              <Label htmlFor="denoising-strength">Denoising Strength: 0.7</Label>
                              <input
                                id="denoising-strength"
                                type="range"
                                min="0.1"
                                max="1"
                                step="0.1"
                                defaultValue="0.7"
                                className="w-full mt-2"
                              />
                            </div>
                            <Button className="w-full">
                              <Wand2 className="h-4 w-4 mr-2" />
                              img2img 생성
                            </Button>
                          </CardContent>
                        </Card>

                        <Card>
                          <CardHeader>
                            <CardTitle className="text-lg">인페인팅</CardTitle>
                            <CardDescription>
                              이미지의 특정 부분을 수정하거나 제거합니다
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div>
                              <Label htmlFor="inpaint-prompt">수정 프롬프트</Label>
                              <Textarea
                                id="inpaint-prompt"
                                placeholder="수정하고 싶은 부분을 설명하세요"
                                className="min-h-[80px]"
                              />
                            </div>
                            <Button 
                              className="w-full" 
                              variant="outline"
                              onClick={startMaskDrawing}
                              disabled={maskMode}
                            >
                              <Edit className="h-4 w-4 mr-2" />
                              {maskMode ? "마스크 그리는 중..." : "마스크 그리기"}
                            </Button>
                            <Button 
                              className="w-full"
                              onClick={handleInpainting}
                              disabled={isGenerating || !uploadedImageUrl}
                            >
                              {isGenerating ? (
                                <>
                                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                  처리 중...
                                </>
                              ) : (
                                <>
                                  <Sparkles className="h-4 w-4 mr-2" />
                                  인페인팅 시작
                                </>
                              )}
                            </Button>
                          </CardContent>
                        </Card>
                      </div>

                      {/* 새 이미지 업로드 버튼 */}
                      <div className="text-center">
                        <Button variant="outline" onClick={handleRemoveUploadedImage}>
                          <Plus className="h-4 w-4 mr-2" />
                          다른 이미지 업로드
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* 갤러리 탭 */}
            <TabsContent value="gallery" className="space-y-6">
              <div className="flex justify-between items-center">
                <h2 className="text-xl font-semibold">생성된 이미지</h2>
                <Button variant="outline" onClick={() => window.location.reload()}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  새로고침
                </Button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {images.map((image) => (
                  <Card key={image.id} className="overflow-hidden">
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
                          onClick={() => handleDownloadImage(image.image_url, `generated_${image.id}.png`)}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleDeleteImage(image.id)}
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
                ))}
              </div>

              {images.length === 0 && (
                <div className="text-center py-12">
                  <ImageIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-lg font-medium text-gray-900 mb-2">생성된 이미지가 없습니다</p>
                  <p className="text-gray-600">첫 번째 이미지를 생성해보세요</p>
                </div>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </RequireAuth>
  )
}