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
import { apiClient, influencerToneAPI } from "@/lib/api"
import {
  ArrowLeft,
  Save,
  Image as ImageIcon,
  Hash,
  Sparkles,
  AlertCircle,
  Loader2,
  User
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
  const [generated, setGenerated] = useState<{ content: string, hashtags: string[] } | null>(null)
  const [isEnhancing, setIsEnhancing] = useState(false)
  const [converted, setConverted] = useState<string | null>(null)
  const [isConverting, setIsConverting] = useState(false)
  const [showFullPreview, setShowFullPreview] = useState(false)

  // 발행 설정 상태
  const [publishType, setPublishType] = useState<'immediate' | 'scheduled'>('immediate')
  const [scheduledDate, setScheduledDate] = useState('')
  const [scheduledTime, setScheduledTime] = useState('')

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
    const basicFieldsValid = (
      formData.influencer_id.trim() !== '' &&
      formData.board_topic.trim() !== '' &&
      formData.board_description.trim() !== '' &&
      formData.board_hashtag.length > 0 &&
      hasImage
    )

    // 예약 발행이 선택된 경우 날짜/시간 검증
    if (publishType === 'scheduled') {
      return basicFieldsValid && scheduledDate !== '' && scheduledTime !== ''
    }

    return basicFieldsValid
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
  const isGenerateEnabled = !!formData.influencer_id && !!formData.board_topic && !!formData.board_description.trim();

  const generateContent = async () => {
    if (!formData.influencer_id) {
      setError('AI 인플루언서를 선택하세요.');
      return;
    }
    if (!formData.board_topic) {
      setError('게시글 주제를 입력하세요.');
      return;
    }
    if (!formData.board_description || !formData.board_description.trim()) {
      setError('게시글 설명을 입력하세요.');
      return;
    }
    setIsEnhancing(true);
    setError(null);
    try {
      // 선택한 인플루언서에서 group_id 추출
      const selectedInfluencer = influencers.find(
        (inf) => inf.influencer_id === formData.influencer_id
      );
      // /full-enhance 엔드포인트로 요청
      const res: any = await apiClient.post('/api/v1/boards/full-enhance', {
        topic: formData.board_topic,
        platform: PLATFORM_OPTIONS[formData.board_platform].label.toLowerCase(),
        include_content: formData.board_description,
        influencer_id: formData.influencer_id,
        team_id: selectedInfluencer?.group_id, // group_id를 team_id로 보냄
        user_id: user?.user_id, // 로그인한 유저의 user_id를 body에 포함
      });
      setGenerated({
        content: res.social_media_content,
        hashtags: res.hashtags,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI 생성에 실패했습니다.');
    } finally {
      setIsEnhancing(false);
    }
  };

  // 인플루언서 말투 변환 함수
  const convertToInfluencerStyle = async () => {
    if (!generated?.content || !formData.influencer_id) return;
    setIsConverting(true);
    setError(null);

    // 인플루언서 정보 가져오기
    const selectedInfluencer = influencers.find(
      (inf) => inf.influencer_id === formData.influencer_id
    );
    if (!selectedInfluencer) {
      setError("인플루언서를 찾을 수 없습니다.");
      setIsConverting(false);
      return;
    }

    const modelRepo = selectedInfluencer.influencer_model_repo;

    try {
      const response = await apiClient.post('/api/v1/model-test/multi-chat', {
        influencers: [
          {
            influencer_id: selectedInfluencer.influencer_id,
            influencer_model_repo: modelRepo,
          },
        ],
        message: generated.content,
      });
      setConverted((response as any).results?.[0]?.response || "");
    } catch (err) {
      setError("인플루언서 말투 변환에 실패했습니다.");
    } finally {
      setIsConverting(false);
    }
  };

  // AI 생성 승인
  const approveGenerated = () => {
    if (!generated) return;
    handleInputChange('board_description', generated.content);
    handleInputChange('board_hashtag', generated.hashtags.map((tag: string) => tag.replace(/^#+/, '')));
  };

  // 인플루언서 말투 변환 승인
  // - 변환된 텍스트를 설명란(board_description)에 적용
  // - 해시태그도 폼에 반영
  // - 이미지 업로드 상태는 절대 변경하지 않음
  const approveConverted = () => {
    if (!converted) return;
    // 해시태그 제거 후 설명란에 적용
    const cleanContent = converted.replace(/#\w+/g, '').replace(/\s{2,}/g, ' ').trim();
    handleInputChange('board_description', cleanContent);
    // AI 생성에서 받은 해시태그도 함께 폼에 추가
    if (generated?.hashtags) {
      handleInputChange('board_hashtag', generated.hashtags.map((tag: string) => tag.replace(/^#+/, '')));
    }
    // 이미지 업로드 상태(formData.uploaded_image)는 절대 변경하지 않음
  };

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

    // 예약 발행 시 날짜/시간 검증
    if (publishType === 'scheduled') {
      if (!scheduledDate || !scheduledTime) {
        setError("예약 발행을 선택했다면 날짜와 시간을 모두 선택해주세요.")
        return
      }

      const scheduledDateTime = new Date(`${scheduledDate}T${scheduledTime}`)
      const now = new Date()

      if (scheduledDateTime <= now) {
        setError("예약 시간은 현재 시간보다 이후여야 합니다.")
        return
      }
    }

    setSubmitting(true)
    setError(null)

    try {
      // 백엔드 URL 가져오기
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://localhost:8000';
      console.log('Backend URL:', backendUrl);

      // 먼저 GET 테스트
      console.log('Testing GET connection...');
      const getTestResponse = await fetch(`${backendUrl}/api/v1/boards/upload-test-get`, {
        method: 'GET'
      });
      console.log('GET test result:', await getTestResponse.json());

      // POST 테스트
      console.log('Testing POST connection...');
      const testResponse = await fetch(`${backendUrl}/api/v1/boards/upload-test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({})
      });
      console.log('POST test result:', await testResponse.json());

      // 인증 토큰 확인
      const token = localStorage.getItem('access_token');
      console.log('Token exists:', !!token);
      console.log('Token preview:', token ? token.substring(0, 20) + '...' : 'null');

      // 이미지 업로드
      const imageFormData = new FormData()
      imageFormData.append('file', formData.uploaded_image)  // 단일 파일로 변경

      console.log('Uploading image...', formData.uploaded_image);
      console.log('FormData entries:', Array.from(imageFormData.entries()));

      const imageResponse = await fetch(`${backendUrl}/api/v1/boards/upload-image-simple`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
          // Content-Type을 명시적으로 설정하지 않음 (브라우저가 자동으로 boundary 설정)
        },
        body: imageFormData
      })

      console.log('Image upload response status:', imageResponse.status);

      if (!imageResponse.ok) {
        const errorText = await imageResponse.text();
        console.error('Image upload error:', errorText);
        throw new Error(`이미지 업로드에 실패했습니다: ${imageResponse.status} - ${errorText}`);
      }

      const imageData = await imageResponse.json()
      console.log('Image upload response:', imageData);
      const imageUrl = imageData.file_url // 백엔드에서 반환된 실제 파일 URL 사용
      console.log('Image URL:', imageUrl);

      // 발행 상태 결정
      let boardStatus = 1; // 기본값: 임시저장
      if (publishType === 'immediate') {
        boardStatus = 3; // 즉시 발행
      } else if (publishType === 'scheduled') {
        boardStatus = 2; // 예약 발행
      }

      // 게시글 데이터 준비
      const boardData = {
        influencer_id: formData.influencer_id,
        board_topic: formData.board_topic,
        board_description: formData.board_description,
        board_platform: formData.board_platform,
        board_hash_tag: formData.board_hashtag.join(' '),
        team_id: user?.teams?.[0]?.group_id || 1,
        image_url: imageUrl,
        board_status: boardStatus,
        // 예약 발행 시 스케줄 정보 추가
        ...(publishType === 'scheduled' && {
          scheduled_at: `${scheduledDate}T${scheduledTime}:00`
        })
      };

      console.log('Sending board data:', boardData);

      // 게시글 생성
      const response = await fetch(`${backendUrl}/api/v1/boards`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify(boardData)
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
                      <div className="flex space-x-2">
                        {isGenerateEnabled && (
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={generateContent}
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
                    </div>
                    <Textarea
                      id="board_description"
                      placeholder="게시글에 대한 추가 설명을 입력하세요"
                      value={formData.board_description}
                      onChange={(e) => handleInputChange('board_description', e.target.value)}
                      rows={3}
                      className="mt-2"
                    />
                    {generated && (
                      <div className="mt-4 space-y-4">
                        <div className="p-4 bg-green-50 border border-green-200 rounded-lg relative">
                          <h4 className="font-medium text-green-900 mb-2 flex items-center">AI가 생성한 본문</h4>
                          <div className="text-sm text-green-800 whitespace-pre-wrap bg-white p-3 rounded border mb-4 max-h-60 overflow-y-auto leading-relaxed">
                            {generated.content}
                          </div>
                          <h5 className="font-medium text-green-800 mb-2 flex items-center">자동 생성 해시태그</h5>
                          <div className="flex flex-wrap gap-2">
                            {generated.hashtags.map((tag: string, index: number) => (
                              <Badge key={index} variant="secondary" className="bg-green-100 text-green-800 border-green-300">{tag}</Badge>
                            ))}
                          </div>
                          <span className="text-xs text-green-600 block mt-2">{generated.content.length}자 • 스크롤 또는 전체 보기로 확인</span>
                          <div className="flex flex-wrap justify-end items-center gap-2 mt-6">
                            <Button 
                              type="button" 
                              onClick={() => setShowFullPreview(true)} 
                              variant="outline"
                              size="sm"
                              className="flex items-center gap-1 border-blue-300 hover:border-blue-500 hover:bg-blue-50 transition-colors"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                              전체 보기
                            </Button>
                            <Button
                              onClick={convertToInfluencerStyle}
                              disabled={isConverting}
                              variant="outline"
                              size="sm"
                              className="flex items-center gap-1 font-semibold border-blue-400 hover:border-blue-600 hover:bg-blue-50 transition-colors"
                            >
                              {isConverting ? (
                                <>
                                  <Loader2 className="h-4 w-4 animate-spin mr-1" />
                                  변환 중...
                                </>
                              ) : (
                                <>
                                  <User className="h-5 w-5 mr-1" />
                                  <span className="tracking-wide">✨ 인플루언서 말투로 변환</span>
                                </>
                              )}
                            </Button>
                          </div>
                        </div>
                      </div>
                    )}
                    {converted && (
                      <div className="mt-4 space-y-4">
                        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg relative">
                          <h4 className="font-medium text-blue-900 mb-2 flex items-center">인플루언서 말투 미리보기</h4>
                          <div className="text-sm text-blue-800 whitespace-pre-wrap bg-white p-3 rounded border mb-4 max-h-60 overflow-y-auto leading-relaxed">
                            {converted}
                          </div>
                          <span className="text-xs text-blue-600 block mt-2">{converted.length}자 • 스크롤 또는 전체 보기로 확인</span>
                          <div className="flex flex-wrap justify-end items-center gap-2 mt-6">
                            <Button 
                              type="button" 
                              onClick={() => setShowFullPreview(true)} 
                              variant="outline"
                              size="sm"
                              className="flex items-center gap-1 border-blue-300 hover:border-blue-500 hover:bg-blue-50 transition-colors"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                              전체 보기
                            </Button>
                            <Button type="button" onClick={approveConverted} variant="outline" className="flex items-center space-x-2 border-blue-400 hover:border-blue-600 hover:bg-blue-50 transition-colors">
                              <span>✓</span>
                              <span>폼에 적용 (해시태그 포함)</span>
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
                        className={`mt-2 border-2 border-dashed rounded-lg p-6 transition-colors ${isDragOver
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

              {/* 발행 설정 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <svg className="h-5 w-5 text-black" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z" clipRule="evenodd" />
                    </svg>
                    <span>발행 설정</span>
                  </CardTitle>
                  <CardDescription>게시글을 언제 발행할지 선택하세요</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* 발행 옵션 */}
                  <div className="grid grid-cols-2 gap-4">
                    {/* 즉시 발행 */}
                    <div
                      className={`border-2 rounded-lg p-4 cursor-pointer transition-all ${publishType === 'immediate'
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                        }`}
                      onClick={() => {
                        setPublishType('immediate')
                        setScheduledDate('')
                        setScheduledTime('')
                      }}
                    >
                      <div className="text-center space-y-2">
                        <div className="text-lg font-medium">즉시 발행</div>
                        <div className="text-sm text-gray-600">게시글이 즉시 발행됩니다</div>
                      </div>
                    </div>

                    {/* 스케줄 발행 */}
                    <div
                      className={`border-2 rounded-lg p-4 cursor-pointer transition-all ${publishType === 'scheduled'
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                        }`}
                      onClick={() => setPublishType('scheduled')}
                    >
                      <div className="text-center space-y-2">
                        <div className="text-lg font-medium">스케줄 발행</div>
                        <div className="text-sm text-gray-600">원하는 시간에 발행</div>
                      </div>
                    </div>
                  </div>

                  {/* 스케줄 발행 선택 시 날짜/시간 입력 */}
                  {publishType === 'scheduled' && (
                    <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
                      <Label className="text-sm font-medium text-blue-900 mb-2 block">예약 날짜 및 시간</Label>
                      <Input
                        type="datetime-local"
                        value={scheduledDate && scheduledTime ? `${scheduledDate}T${scheduledTime}` : ''}
                        onChange={(e) => {
                          const value = e.target.value
                          if (value) {
                            const [date, time] = value.split('T')
                            setScheduledDate(date)
                            setScheduledTime(time)
                          }
                        }}
                        min={new Date().toISOString().slice(0, 16)}
                        className="w-full border-blue-300 focus:border-blue-500"
                      />
                      {scheduledDate && scheduledTime && (
                        <div className="mt-2 text-sm text-blue-700">
                          📅 예약 시간: {new Date(`${scheduledDate}T${scheduledTime}`).toLocaleString('ko-KR', {
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                            weekday: 'long'
                          })}
                        </div>
                      )}
                    </div>
                  )}
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

        {/* 전체 미리보기 모달 */}
        {showFullPreview && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
              <div className="p-6">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-xl font-bold">전체 내용 미리보기</h2>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowFullPreview(false)}
                  >
                    ×
                  </Button>
                </div>

                <div className="space-y-6">
                  {converted && (
                    <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                      <h3 className="font-medium text-blue-900 mb-3">인플루언서 말투 변환 결과</h3>
                      <div className="text-sm text-blue-800 whitespace-pre-wrap bg-white p-4 rounded border leading-relaxed">
                        {converted}
                      </div>
                    </div>
                  )}
                  
                  {generated && (
                    <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                      <h3 className="font-medium text-green-900 mb-3">AI 생성 원본</h3>
                      <div className="text-sm text-green-800 whitespace-pre-wrap bg-white p-4 rounded border leading-relaxed">
                        {generated.content}
                      </div>
                      <div className="mt-3">
                        <h4 className="font-medium text-green-800 mb-2">생성된 해시태그</h4>
                        <div className="flex flex-wrap gap-2">
                          {generated.hashtags.map((tag: string, index: number) => (
                            <Badge key={index} variant="secondary" className="bg-green-100 text-green-800 border-green-300">
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                <div className="mt-6 flex justify-end">
                  <Button onClick={() => setShowFullPreview(false)}>
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
