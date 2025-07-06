"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Navigation } from "@/components/navigation"
import { RequireAuth } from "@/components/auth/protected-route"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { 
  ArrowLeft, 
  Save, 
  Image as ImageIcon, 
  Hash, 
  Sparkles,
  AlertCircle,
  Loader2
} from "lucide-react"
import { usePermission } from "@/hooks/use-auth"
import { ModelService, type AIInfluencer } from "@/lib/services/model.service"

// 타입 정의
interface CreatePostFormData {
  influencer_id: string
  board_topic: string
  board_description: string
  board_platform: number
  board_hashtag: string[]
  uploaded_image: File | null
}


interface PlatformOption {
  value: number
  label: string
  description: string
  icon: string
}

const PLATFORM_OPTIONS: PlatformOption[] = [
  { value: 0, label: "Instagram", description: "이미지 중심의 소셜 미디어", icon: "📸" },
  { value: 1, label: "Blog", description: "긴 글 형태의 블로그 포스트", icon: "📝" },
  { value: 2, label: "Facebook", description: "다양한 형태의 소셜 미디어", icon: "📱" }
]

// 기본 해시태그 목록
const DEFAULT_HASHTAGS = [
  "라이프스타일", "일상", "맛집", "여행", "패션", "뷰티", "건강", "운동", 
  "음식", "카페", "독서", "영화", "음악", "취미", "반려동물", "요리",
  "사진", "미술", "자연", "힐링", "동기부여", "성장", "학습", "기술"
]

export default function CreatePostPage() {
  const router = useRouter()
  const { hasPermission, user } = usePermission()
  
  // 상태 관리
  const [formData, setFormData] = useState<CreatePostFormData>({
    influencer_id: "",
    board_topic: "",
    board_description: "",
    board_platform: 0,
    board_hashtag: [],
    uploaded_image: null
  })
  
  const [influencers, setInfluencers] = useState<AIInfluencer[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hashtagInput, setHashtagInput] = useState("")
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [enhancedContent, setEnhancedContent] = useState<{
    enhancement_id: string
    original_content: string
    enhanced_content: string
    status: string
  } | null>(null)
  const [isEnhancing, setIsEnhancing] = useState(false)

  // 인플루언서 데이터 로딩
  useEffect(() => {
    const fetchInfluencers = async () => {
      try {
        setLoading(true)
        const data = await ModelService.getInfluencers()
        // 사용 가능한 인플루언서만 필터링
        const availableInfluencers = data.filter(inf => inf.learning_status === 1)
        setInfluencers(availableInfluencers)
        
        // 첫 번째 인플루언서를 기본 선택
        if (availableInfluencers.length > 0) {
          setFormData(prev => ({
            ...prev,
            influencer_id: availableInfluencers[0].influencer_id
          }))
        }
      } catch (err) {
        console.error('Failed to fetch influencers:', err)
        setError('인플루언서 정보를 불러오는데 실패했습니다.')
      } finally {
        setLoading(false)
      }
    }

    fetchInfluencers()
  }, [])

  // 폼 데이터 업데이트
  const handleInputChange = (field: keyof CreatePostFormData, value: string | number | boolean | string[] | File | null) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }))
  }

  // 해시태그 추가
  const addHashtag = () => {
    if (hashtagInput.trim() && !formData.board_hashtag.includes(hashtagInput.trim())) {
      const newHashtag = hashtagInput.trim().replace(/^#/, '') // # 제거
      handleInputChange('board_hashtag', [...formData.board_hashtag, newHashtag])
      setHashtagInput("")
    }
  }

  // 기본 해시태그 추가
  const addDefaultHashtag = (hashtag: string) => {
    if (!formData.board_hashtag.includes(hashtag)) {
      handleInputChange('board_hashtag', [...formData.board_hashtag, hashtag])
    }
  }

  // 해시태그 제거
  const removeHashtag = (index: number) => {
    const newHashtags = formData.board_hashtag.filter((_, i) => i !== index)
    handleInputChange('board_hashtag', newHashtags)
  }

  // 해시태그 입력 핸들러
  const handleHashtagKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addHashtag()
    }
  }

  // 모든 필드 입력 여부 검증 (미리보기 버튼용)
  const isFormValid = () => {
    const hasImage = formData.uploaded_image !== null || imagePreview !== null
    return (
      formData.influencer_id.trim() !== '' &&
      formData.board_topic.trim() !== '' &&
      formData.board_description.trim() !== '' &&
      formData.board_hashtag.length > 0 &&
      hasImage
    )
  }

  // 이미지 파일 처리 공통 함수
  const processImageFile = (file: File) => {
    // 이미지 파일 검증
    if (!file.type.startsWith('image/')) {
      setError('이미지 파일만 업로드할 수 있습니다.')
      return
    }
    
    // 파일 크기 제한 (5MB)
    if (file.size > 5 * 1024 * 1024) {
      setError('이미지 파일 크기는 5MB 이하여야 합니다.')
      return
    }

    setError(null) // 에러 초기화
    handleInputChange('uploaded_image', file)
    
    // 이미지 미리보기 생성
    const reader = new FileReader()
    reader.onload = (e) => {
      setImagePreview(e.target?.result as string)
    }
    reader.readAsDataURL(file)
  }

  // 이미지 업로드 처리
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      processImageFile(file)
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

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    
    const files = e.dataTransfer.files
    if (files && files[0]) {
      processImageFile(files[0])
    }
  }

  // 이미지 제거
  const removeImage = () => {
    handleInputChange('uploaded_image', null)
    setImagePreview(null)
  }

  // 게시글 설명 향상
  const enhanceContent = async () => {
    if (!formData.board_description.trim()) {
      setError("향상할 게시글 설명을 입력해주세요.")
      return
    }

    setIsEnhancing(true)
    setError(null)

    try {
      const response = await fetch('/api/v1/content-enhancement/enhance', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          original_content: formData.board_description,
          influencer_id: formData.influencer_id,
          enhancement_style: "creative",
          hashtags: formData.board_hashtag,
          board_topic: formData.board_topic,
          board_platform: formData.board_platform
        })
      })

      if (!response.ok) {
        throw new Error('설명 향상에 실패했습니다.')
      }

      const data = await response.json()
      setEnhancedContent(data)
    } catch (err) {
      console.error('Content enhancement failed:', err)
      setError(err instanceof Error ? err.message : '설명 향상에 실패했습니다.')
    } finally {
      setIsEnhancing(false)
    }
  }

  // 향상된 내용 승인
  const approveEnhancement = async (approved: boolean) => {
    if (!enhancedContent) return

    try {
      const response = await fetch('/api/v1/content-enhancement/approve', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          enhancement_id: enhancedContent.enhancement_id,
          approved: approved
        })
      })

      if (!response.ok) {
        throw new Error('승인 처리에 실패했습니다.')
      }

      if (approved) {
        // 승인된 내용으로 폼 데이터 업데이트
        handleInputChange('board_description', enhancedContent.enhanced_content)
        setEnhancedContent(null)
      } else {
        // 거부 시 향상 내용 초기화
        setEnhancedContent(null)
      }
    } catch (err) {
      console.error('Approval failed:', err)
      setError(err instanceof Error ? err.message : '승인 처리에 실패했습니다.')
    }
  }


  // 폼 제출 (게시글 저장)
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // 필수 필드 검증
    if (!formData.influencer_id || !formData.board_topic || !formData.board_description) {
      setError("인플루언서, 주제, 설명을 모두 입력해주세요.")
      return
    }

    // 이미지 필수 검증
    if (!formData.uploaded_image) {
      setError("이미지를 업로드해주세요.")
      return
    }

    setSubmitting(true)
    setError(null)

    try {
      // 먼저 이미지 업로드
      const imageFormData = new FormData()
      imageFormData.append('files', formData.uploaded_image)
      
      const imageResponse = await fetch('/api/v1/boards/upload-image', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: imageFormData
      })

      if (!imageResponse.ok) {
        throw new Error('이미지 업로드에 실패했습니다.')
      }

      const imageData = await imageResponse.json()
      const imageUrl = imageData.files[0].file_url

      // 게시글 생성
      const response = await fetch('/api/v1/boards', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          influencer_id: formData.influencer_id,
          board_topic: formData.board_topic,
          board_description: formData.board_description,
          board_platform: formData.board_platform,
          board_hash_tag: formData.board_hashtag.join(' '),
          team_id: user?.teams?.[0]?.group_id || 1,
          image_url: imageUrl,
          board_status: 1 // 임시저장 상태
        })
      })

      if (!response.ok) {
        throw new Error('게시글 생성에 실패했습니다.')
      }
      
      router.push('/post_list')
    } catch (err) {
      console.error('Failed to create post:', err)
      setError(err instanceof Error ? err.message : '게시글 생성에 실패했습니다.')
    } finally {
      setSubmitting(false)
    }
  }

  // 권한 확인
  if (!hasPermission('content', 'create')) {
    return (
      <RequireAuth>
        <div className="min-h-screen bg-gray-50">
          <Navigation />
          <div className="max-w-4xl mx-auto px-4 py-8">
            <Card>
              <CardContent className="p-6 text-center">
                <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
                <h2 className="text-xl font-semibold mb-2">접근 권한이 없습니다</h2>
                <p className="text-gray-600 mb-4">게시글을 생성할 권한이 없습니다.</p>
                <Link href="/dashboard">
                  <Button>대시보드로 돌아가기</Button>
                </Link>
              </CardContent>
            </Card>
          </div>
        </div>
      </RequireAuth>
    )
  }

  return (
    <RequireAuth>
      <div className="min-h-screen bg-gray-50">
        <Navigation />

        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="mb-8">
            <Link href="/dashboard" className="inline-flex items-center text-blue-600 hover:text-blue-800 mb-4">
              <ArrowLeft className="h-4 w-4 mr-2" />
              대시보드로 돌아가기
            </Link>
            <h1 className="text-3xl font-bold text-gray-900">새 게시글 생성</h1>
            <p className="text-gray-600 mt-2">AI 인플루언서로 새로운 콘텐츠를 생성하세요</p>
          </div>

          {loading ? (
            <div className="flex justify-center items-center py-12">
              <Loader2 className="h-8 w-8 animate-spin mr-2" />
              <span>인플루언서 정보를 불러오는 중...</span>
            </div>
          ) : error ? (
            <Card>
              <CardContent className="p-6 text-center">
                <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
                <p className="text-red-600 mb-4">{error}</p>
                <Button onClick={() => window.location.reload()}>다시 시도</Button>
              </CardContent>
            </Card>
          ) : influencers.length === 0 ? (
            <Card>
              <CardContent className="p-6 text-center">
                <AlertCircle className="h-12 w-12 text-yellow-500 mx-auto mb-4" />
                <h2 className="text-xl font-semibold mb-2">사용 가능한 인플루언서가 없습니다</h2>
                <p className="text-gray-600 mb-4">
                  게시글을 생성하려면 먼저 AI 인플루언서를 생성하고 학습을 완료해야 합니다.
                </p>
                <Link href="/create-model">
                  <Button>AI 인플루언서 생성하기</Button>
                </Link>
              </CardContent>
            </Card>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-8">
              {/* 기본 설정 */}
              <Card>
                <CardHeader>
                  <CardTitle>기본 설정</CardTitle>
                  <CardDescription>게시글의 기본 정보를 설정하세요</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <Label htmlFor="influencer_id">AI 인플루언서 선택</Label>
                      <Select 
                        value={formData.influencer_id} 
                        onValueChange={(value) => handleInputChange('influencer_id', value)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="인플루언서를 선택하세요" />
                        </SelectTrigger>
                        <SelectContent>
                          {influencers.map((influencer) => (
                            <SelectItem key={influencer.influencer_id} value={influencer.influencer_id}>
                              <div className="flex items-center space-x-2">
                                <span>{influencer.influencer_name}</span>
                                <Badge variant="secondary" className="text-xs">
                                  {influencer.style_preset?.style_preset_name || 'No Preset'}
                                </Badge>
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div>
                      <Label htmlFor="board_platform">플랫폼 선택</Label>
                      <Select 
                        value={formData.board_platform.toString()} 
                        onValueChange={(value) => handleInputChange('board_platform', parseInt(value))}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="플랫폼을 선택하세요" />
                        </SelectTrigger>
                        <SelectContent>
                          {PLATFORM_OPTIONS.map((platform) => (
                            <SelectItem key={platform.value} value={platform.value.toString()}>
                              <div className="flex items-center space-x-2">
                                <span>{platform.icon}</span>
                                <div>
                                  <div className="font-medium">{platform.label}</div>
                                  <div className="text-xs text-gray-500">{platform.description}</div>
                                </div>
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div>
                    <Label htmlFor="board_topic">게시글 주제</Label>
                    <Input
                      id="board_topic"
                      placeholder="게시글의 주제를 입력하세요"
                      value={formData.board_topic}
                      onChange={(e) => handleInputChange('board_topic', e.target.value)}
                      required
                    />
                  </div>

                  <div>
                    <div className="flex items-center justify-between">
                      <Label htmlFor="board_description">게시글 설명 (선택사항)</Label>
                      {formData.board_description.trim() && !enhancedContent && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={enhanceContent}
                          disabled={isEnhancing}
                        >
                          {isEnhancing ? (
                            <>
                              <Loader2 className="h-3 w-3 animate-spin mr-1" />
                              향상 중...
                            </>
                          ) : (
                            <>
                              <Sparkles className="h-3 w-3 mr-1" />
                              AI 생성
                            </>
                          )}
                        </Button>
                      )}
                    </div>
                    <Textarea
                      id="board_description"
                      placeholder="게시글에 대한 추가 설명을 입력하세요"
                      value={formData.board_description}
                      onChange={(e) => handleInputChange('board_description', e.target.value)}
                      rows={3}
                      className="mt-2"
                    />
                    
                    {/* 향상된 내용 표시 */}
                    {enhancedContent && (
                      <div className="mt-4 space-y-4">
                        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                          <h4 className="font-medium text-blue-900 mb-2 flex items-center">
                            <Sparkles className="h-4 w-4 mr-2" />
                            원본 내용
                          </h4>
                          <div className="text-sm text-blue-800 whitespace-pre-wrap bg-white p-3 rounded border">
                            {enhancedContent.original_content}
                          </div>
                        </div>
                        
                        <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                          <h4 className="font-medium text-green-900 mb-2 flex items-center">
                            <Sparkles className="h-4 w-4 mr-2" />
                            AI가 향상한 내용
                          </h4>
                          <div className="text-sm text-green-800 whitespace-pre-wrap bg-white p-3 rounded border mb-4">
                            {enhancedContent.enhanced_content}
                          </div>
                          
                          <div className="flex space-x-2">
                            <Button
                              type="button"
                              onClick={() => approveEnhancement(true)}
                              className="flex items-center space-x-2"
                            >
                              <span>✓</span>
                              <span>승인하기</span>
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() => approveEnhancement(false)}
                              className="flex items-center space-x-2"
                            >
                              <span>✕</span>
                              <span>거부하기</span>
                            </Button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* 해시태그 설정 */}
                  <div className="space-y-4">
                    <div>
                      <Label className="flex items-center space-x-2">
                        <Hash className="h-4 w-4" />
                        <span>해시태그</span>
                      </Label>
                      <div className="flex space-x-2 mt-2">
                        <Input
                          placeholder="해시태그 입력 (Enter 또는 , 로 추가)"
                          value={hashtagInput}
                          onChange={(e) => setHashtagInput(e.target.value)}
                          onKeyDown={handleHashtagKeyDown}
                        />
                        <Button type="button" onClick={addHashtag} variant="outline">
                          추가
                        </Button>
                      </div>
                    </div>

                    {/* 기본 해시태그 목록 */}
                    <div>
                      <Label className="text-sm font-medium">추천 해시태그</Label>
                      <div className="flex flex-wrap gap-2 mt-2">
                        {DEFAULT_HASHTAGS.map((hashtag) => (
                          <Badge 
                            key={hashtag} 
                            variant="outline" 
                            className="cursor-pointer hover:bg-blue-50 hover:border-blue-300"
                            onClick={() => addDefaultHashtag(hashtag)}
                          >
                            #{hashtag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    
                    {formData.board_hashtag.length > 0 && (
                      <div>
                        <Label className="text-sm font-medium">선택된 해시태그</Label>
                        <div className="flex flex-wrap gap-2 mt-2">
                          {formData.board_hashtag.map((tag, index) => (
                            <Badge key={index} variant="secondary" className="cursor-pointer hover:bg-red-100">
                              <span>#{tag}</span>
                              <button
                                type="button"
                                onClick={() => removeHashtag(index)}
                                className="ml-1 text-red-500 hover:text-red-700"
                              >
                                ×
                              </button>
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* 이미지 업로드 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <ImageIcon className="h-5 w-5" />
                    <span>이미지 업로드</span>
                  </CardTitle>
                  <CardDescription>이미지를 업로드하거나 AI로 생성하세요</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* 이미지 업로드 영역 */}
                  <div>
                    <Label htmlFor="image_upload">이미지 파일 업로드</Label>
                    
                    {/* 업로드된 이미지가 있을 때 */}
                    {formData.uploaded_image && imagePreview ? (
                      <div className="mt-2 border-2 border-gray-200 rounded-lg p-4 bg-gray-50">
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="font-medium text-gray-900">업로드된 이미지</h4>
                          <Button 
                            type="button" 
                            variant="outline" 
                            size="sm"
                            onClick={removeImage}
                            className="text-red-600 hover:text-red-700"
                          >
                            제거
                          </Button>
                        </div>
                        <div className="flex justify-center">
                          <img 
                            src={imagePreview} 
                            alt="Uploaded" 
                            className="max-w-full max-h-64 object-contain rounded-lg border"
                          />
                        </div>
                      </div>
                    ) : (
                      /* 업로드 영역 */
                      <div 
                        className={`mt-2 border-2 border-dashed rounded-lg p-6 transition-colors ${
                          isDragOver 
                            ? 'border-blue-500 bg-blue-50' 
                            : 'border-gray-300 hover:border-gray-400'
                        }`}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                      >
                        <input
                          id="image_upload"
                          type="file"
                          accept="image/*"
                          onChange={handleImageUpload}
                          className="hidden"
                        />
                        <div className="text-center">
                          <ImageIcon className="h-12 w-12 mx-auto text-gray-400 mb-4" />
                          <p className="text-gray-600 mb-2">
                            이미지를 드래그 앤 드롭하거나 클릭하여 선택하세요
                          </p>
                          <p className="text-xs text-gray-400 mb-4">
                            JPG, PNG, GIF 파일 (최대 5MB)
                          </p>
                          <Button 
                            type="button" 
                            variant="outline" 
                            onClick={() => document.getElementById('image_upload')?.click()}
                          >
                            <ImageIcon className="h-4 w-4 mr-2" />
                            파일 선택
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>


                </CardContent>
              </Card>

              {/* 미리보기 버튼 */}
              {isFormValid() && (
                <Card>
                  <CardContent className="p-4">
                    <Button
                      type="button"
                      onClick={() => setShowPreview(true)}
                      className="w-full"
                    >
                      <ImageIcon className="h-4 w-4 mr-2" />
                      게시글 미리보기
                    </Button>
                  </CardContent>
                </Card>
              )}

              {/* 제출 버튼 */}
              <div className="flex justify-end space-x-4">
                <Link href="/dashboard">
                  <Button type="button" variant="outline">
                    취소
                  </Button>
                </Link>
                <Button 
                  type="submit" 
                  disabled={submitting || !isFormValid()}
                >
                  {submitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      저장 중...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      게시글 저장
                    </>
                  )}
                </Button>
              </div>
            </form>
          )}
        </div>

        {/* 미리보기 모달 */}
        {showPreview && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg max-w-2xl w-full max-h-[80vh] overflow-y-auto">
              <div className="p-6">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-xl font-bold">게시글 미리보기</h2>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowPreview(false)}
                  >
                    ×
                  </Button>
                </div>
                
                <div className="space-y-4">
                  {/* 플랫폼 정보 */}
                  <div className="flex items-center space-x-2">
                    <span className="text-sm text-gray-600">플랫폼:</span>
                    <Badge variant="secondary">
                      {PLATFORM_OPTIONS.find(p => p.value === formData.board_platform)?.label}
                    </Badge>
                  </div>
                  
                  {/* 인플루언서 정보 */}
                  <div className="flex items-center space-x-2">
                    <span className="text-sm text-gray-600">인플루언서:</span>
                    <Badge variant="outline">
                      {influencers.find(i => i.influencer_id === formData.influencer_id)?.influencer_name}
                    </Badge>
                  </div>
                  
                  {/* 게시글 주제 */}
                  <div>
                    <h3 className="font-semibold text-lg mb-2">{formData.board_topic}</h3>
                    <p className="text-gray-700 mb-4">{formData.board_description}</p>
                  </div>
                  
                  {/* 업로드된 이미지 */}
                  {imagePreview && (
                    <div className="my-4">
                      <div className="flex justify-center">
                        <img 
                          src={imagePreview} 
                          alt="Preview" 
                          className="max-w-full max-h-64 object-contain rounded-lg border"
                        />
                      </div>
                    </div>
                  )}
                  
                  {/* 해시태그 */}
                  <div>
                    <div className="flex flex-wrap gap-2">
                      {formData.board_hashtag.map((tag, index) => (
                        <Badge key={index} variant="secondary">
                          #{tag}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>
                
                <div className="mt-6 flex justify-end">
                  <Button onClick={() => setShowPreview(false)}>
                    확인
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </RequireAuth>
  )
}
