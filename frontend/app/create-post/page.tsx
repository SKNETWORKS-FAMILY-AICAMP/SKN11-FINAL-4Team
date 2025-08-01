"use client"

import { useState, useEffect, useRef } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Navigation } from "@/components/navigation"
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
  User,
  Upload,
  Instagram,
  BookOpen,
  Facebook
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
  uploaded_images: File[] // 단일 이미지에서 다중 이미지로 변경
}


interface PlatformOption {
  value: number
  label: string
  description: string
  icon: React.ComponentType<{ className?: string }>
}

const PLATFORM_OPTIONS: PlatformOption[] = [
  { value: 0, label: "Instagram", description: "이미지 중심의 소셜 미디어", icon: Instagram }
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
    uploaded_images: [] // 단일 이미지에서 다중 이미지로 변경
  })

  const [influencers, setInfluencers] = useState<AIInfluencer[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hashtagInput, setHashtagInput] = useState("")
  const [imagePreviews, setImagePreviews] = useState<string[]>([])  // 다중 이미지 미리보기
  const [isDragOver, setIsDragOver] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [generated, setGenerated] = useState<{ content: string, hashtags: string[] } | null>(null)
  const [isEnhancing, setIsEnhancing] = useState(false)
  const [converted, setConverted] = useState<string | null>(null)
  const [isConverting, setIsConverting] = useState(false)
  const [imageInfo, setImageInfo] = useState<{
    originalSize: { width: number; height: number } | null;
    resizedSize: { width: number; height: number } | null;
    isResized: boolean;
  } | null>(null)

  const isFetchingRef = useRef(false)


  // 발행 설정 상태
  const [publishType, setPublishType] = useState<'immediate' | 'scheduled'>('immediate')
  const [scheduledDate, setScheduledDate] = useState('')
  const [scheduledTime, setScheduledTime] = useState('')

  // 인플루언서 데이터 로딩
  useEffect(() => {
    if (isFetchingRef.current) return

    const fetchInfluencers = async () => {
      try {
        isFetchingRef.current = true
        setLoading(true)
        const data = await ModelService.getInfluencers()
        // 사용 가능하고 인스타그램 계정과 연동된 인플루언서만 필터링
        const availableInfluencers = data.filter(inf =>
          inf.learning_status === 1 &&
          inf.instagram_is_active === true &&
          inf.instagram_username &&
          inf.instagram_username.trim() !== '' &&
          inf.instagram_id &&
          inf.instagram_id.trim() !== ''
        )
        setInfluencers(availableInfluencers)

        // 첫 번째 인플루언서를 기본 선택
        if (availableInfluencers.length > 0) {
          setFormData(prev => ({
            ...prev,
            influencer_id: availableInfluencers[0].influencer_id
          }))
        }
      } catch (err) {
        // console.error('Failed to fetch influencers:', err)
        setError('인플루언서 정보를 불러오는데 실패했습니다.')
      } finally {
        setLoading(false)
        isFetchingRef.current = false
      }
    }

    fetchInfluencers()
  }, [])

  // 폼 데이터 업데이트
  const handleInputChange = async (field: keyof CreatePostFormData, value: string | number | boolean | string[] | File | File[] | null) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }))

    // 플랫폼이 Instagram으로 변경되고 이미지가 있는 경우 이미지 재처리
    if (field === 'board_platform' && value === 0 && formData.uploaded_images.length > 0) {
      try {
        await processImageFile(formData.uploaded_images[0])
      } catch (error) {
        // console.error('Image reprocessing error:', error)
      }
    }
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
    const hasImage = formData.uploaded_images.length > 0
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



  // Instagram 비율에 맞게 이미지 패딩 처리 (픽셀 크기 조정 없음)
  const padImageForInstagram = (file: File): Promise<{ file: File; originalSize: { width: number; height: number }; paddedSize: { width: number; height: number } }> => {
    return new Promise((resolve, reject) => {
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')
      const img = new Image()

      img.onload = () => {
        const { width, height } = img
        const originalSize = { width, height }
        const aspectRatio = width / height

        // Instagram 요구사항에 맞는 비율 계산 (픽셀 크기는 조정하지 않음)
        // 정사각형: 1:1 비율
        // 세로형: 4:5 비율
        // 가로형: 1.91:1 비율

        let targetWidth = width
        let targetHeight = height

        if (aspectRatio > 1.91) {
          // 가로형이 너무 긴 경우 - 높이를 늘려서 1.91:1 비율 맞춤
          targetWidth = width
          targetHeight = Math.round(width / 1.91)
        } else if (aspectRatio < 0.8) {
          // 세로형이 너무 긴 경우 - 너비를 늘려서 4:5 비율 맞춤
          targetWidth = Math.round(height * 0.8)
          targetHeight = height
        } else if (aspectRatio > 1.2) {
          // 가로형 - 높이를 늘려서 1.91:1 비율 맞춤
          targetWidth = width
          targetHeight = Math.round(width / 1.91)
        } else if (aspectRatio < 0.8) {
          // 세로형 - 너비를 늘려서 4:5 비율 맞춤
          targetWidth = Math.round(height * 0.8)
          targetHeight = height
        }
        // 정사각형은 그대로 사용

        const paddedSize = { width: targetWidth, height: targetHeight }

        canvas.width = targetWidth
        canvas.height = targetHeight

        // 배경을 검은색으로 설정
        ctx!.fillStyle = '#000000'
        ctx!.fillRect(0, 0, targetWidth, targetHeight)

        // 이미지를 중앙에 배치하고 패딩 처리
        const offsetX = (targetWidth - width) / 2
        const offsetY = (targetHeight - height) / 2

        ctx?.drawImage(img, offsetX, offsetY, width, height)

        // Canvas를 Blob으로 변환
        canvas.toBlob((blob) => {
          if (blob) {
            const paddedFile = new File([blob], file.name, {
              type: file.type,
              lastModified: Date.now()
            })
            resolve({ file: paddedFile, originalSize, paddedSize })
          } else {
            reject(new Error('이미지 패딩 처리에 실패했습니다.'))
          }
        }, file.type, 0.9) // 품질 90%
      }

      img.onerror = () => reject(new Error('이미지 로드에 실패했습니다.'))
      img.src = URL.createObjectURL(file)
    })
  }

  // 이미지 파일 처리 공통 함수
  const processImageFile = async (file: File) => {
    // 이미지 개수 제한 (5장)
    if (formData.uploaded_images.length >= 5) {
      setError('이미지는 최대 5장까지 업로드할 수 있습니다.')
      return
    }

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

    try {
      let processedFile = file
      let originalSize = null
      let resizedSize = null
      let isResized = false

      // Instagram 플랫폼인 경우 비율에 맞게 패딩 처리
      if (formData.board_platform === 0) { // Instagram
        const result = await padImageForInstagram(file)
        processedFile = result.file
        originalSize = result.originalSize
        resizedSize = result.paddedSize
        isResized = true
      } else {
        // 다른 플랫폼은 원본 그대로 사용
        const img = new Image()
        img.onload = () => {
          const originalSize = { width: img.width, height: img.height }
          setImageInfo({ originalSize, resizedSize: null, isResized: false })
        }
        img.src = URL.createObjectURL(file)
      }

      handleInputChange('uploaded_images', [...formData.uploaded_images, processedFile])

      // 이미지 미리보기 생성 (패딩 처리된 이미지 사용)
      const reader = new FileReader()
      reader.onload = (e) => {
        setImagePreviews(prev => [...prev, e.target?.result as string])
      }
      reader.readAsDataURL(processedFile)

      // 이미지 정보 저장
      if (isResized) {
        setImageInfo({ originalSize, resizedSize, isResized })
      } else {
        setImageInfo({ originalSize, resizedSize: null, isResized: false })
      }
    } catch (error) {
      setError('이미지 처리 중 오류가 발생했습니다.')
      // console.error('Image processing error:', error)
    }
  }

  // 이미지 업로드 처리
  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files) {
      // 다중 파일 처리
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        if (file.type.startsWith("image/")) {
          await processImageFile(file)
        }
      }
      setError("")
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
    if (files) {
      // 다중 파일 처리
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        if (file.type.startsWith("image/")) {
          await processImageFile(file)
        }
      }
    }
  }

  // 이미지 제거
  const removeImage = (index: number) => {
    setFormData(prev => ({
      ...prev,
      uploaded_images: prev.uploaded_images.filter((_, i) => i !== index)
    }))
    // 미리보기도 함께 제거
    setImagePreviews(prev => prev.filter((_, i) => i !== index))
  }

  // AI 생성 버튼 활성화 조건: 인플루언서 선택 + 주제 입력 + (설명 또는 이미지 중 하나 이상)
  const isGenerateEnabled = !!formData.influencer_id &&
    !!formData.board_topic &&
    (!!formData.board_description.trim() || formData.uploaded_images.length > 0);

  // 파일을 base64로 변환하는 함수
  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => {
        const result = reader.result as string;
        // data:image/jpeg;base64, 부분 제거하고 base64만 반환
        const base64 = result.split(',')[1];
        resolve(base64);
      };
      reader.onerror = error => reject(error);
    });
  };

  const generateContent = async () => {
    if (!formData.board_topic || !formData.influencer_id) {
      setError("주제와 인플루언서를 선택해주세요.");
      return;
    }

    setIsEnhancing(true);
    setError(null);

    // 인플루언서 정보 가져오기
    const selectedInfluencer = influencers.find(
      (inf) => inf.influencer_id === formData.influencer_id
    );
    if (!selectedInfluencer) {
      setError("인플루언서를 찾을 수 없습니다.");
      setIsEnhancing(false);
      return;
    }

    try {
      // 업로드된 이미지들을 base64로 변환
      const imageBase64List: string[] = [];
      if (formData.uploaded_images.length > 0) {
        console.log(`총 ${formData.uploaded_images.length}개의 이미지를 처리합니다.`);
        for (let i = 0; i < formData.uploaded_images.length; i++) {
          const file = formData.uploaded_images[i];
          try {
            console.log(`이미지 ${i + 1}/${formData.uploaded_images.length} 변환 중: ${file.name}`);
            const base64 = await fileToBase64(file);
            imageBase64List.push(base64);
            console.log(`이미지 ${i + 1} 변환 완료: ${base64.length}자`);
          } catch (error) {
            console.error(`이미지 ${i + 1} base64 변환 실패:`, error);
          }
        }
        console.log(`총 ${imageBase64List.length}개의 이미지 변환 완료`);
      }

      // AI 생성에 활용될 정보 로깅
      console.log('=== AI 생성 요청 정보 ===');
      console.log('주제:', formData.board_topic);
      console.log('플랫폼:', formData.board_platform);
      console.log('텍스트 내용:', formData.board_description);
      console.log('해시태그:', formData.board_hashtag.join(' '));
      console.log('이미지 개수:', imageBase64List.length);
      console.log('=== AI 생성 요청 정보 끝 ===');

      // /generate-content 엔드포인트로 요청 (DB 저장 안 함)
      console.log('API 요청 데이터:', {
        board_topic: formData.board_topic,
        board_platform: formData.board_platform,
        influencer_id: formData.influencer_id,
        team_id: selectedInfluencer?.group_id || user?.teams?.[0]?.group_id || 1,
        include_content: formData.board_description,
        hashtags: formData.board_hashtag.join(' '),
        image_base64_list: imageBase64List.length > 0 ? `${imageBase64List.length}개 이미지` : '없음',
      });

      const res: any = await apiClient.post('/api/v1/boards/generate-content', {
        board_topic: formData.board_topic,
        board_platform: formData.board_platform,
        influencer_id: formData.influencer_id,
        team_id: selectedInfluencer?.group_id || user?.teams?.[0]?.group_id || 1,
        include_content: formData.board_description,
        hashtags: formData.board_hashtag.join(' '),
        image_base64_list: imageBase64List.length > 0 ? imageBase64List : undefined,
      });

      console.log('API 응답:', res);

      if (!res.generated_content) {
        throw new Error('AI 생성 결과가 없습니다.');
      }

      const generatedContent = {
        content: res.generated_content,
        hashtags: res.generated_hashtags || [],
      };
      setGenerated(generatedContent);

      // 생성된 본문으로 바로 말투 변환 실행
      if (generatedContent.content && selectedInfluencer) {
        try {
          const response = await apiClient.post('/api/v1/content-enhancement/influencer-tone', {
            influencer_id: selectedInfluencer.influencer_id,
            content: generatedContent.content,
          });
          setConverted((response as any).transformed_content || "");
        } catch (convertErr) {
          // console.error("말투 변환 실패:", convertErr);
          // 말투 변환 실패해도 본문 생성은 성공으로 처리
        }
      }
    } catch (err) {
      console.error('AI 생성 실패:', err);
      if (err instanceof Error) {
        setError(`AI 생성에 실패했습니다: ${err.message}`);
      } else {
        setError('AI 생성에 실패했습니다. 콘솔을 확인해주세요.');
      }
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

    try {
      const response = await apiClient.post('/api/v1/content-enhancement/influencer-tone', {
        influencer_id: selectedInfluencer.influencer_id,
        content: generated.content,  // AI 생성 결과 사용
        platform: "instagram"
      });
      setConverted((response as any).transformed_content || "");
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
  const approveConverted = () => {
    if (!converted) return;
    // 해시태그 제거 후 설명란에 적용
    const cleanContent = converted.replace(/#\w+/g, '').replace(/\s{2,}/g, ' ').trim();
    handleInputChange('board_description', cleanContent);
    // AI 생성에서 받은 해시태그도 함께 폼에 추가
    if (generated?.hashtags) {
      handleInputChange('board_hashtag', generated.hashtags.map((tag: string) => tag.replace(/^#+/, '')));
    }
  };

  // 폼 제출 (게시글 저장)
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // 필수 필드 검증
    if (!formData.influencer_id || !formData.board_topic || !formData.board_description) {
      setError("인플루언서, 주제, 설명을 모두 입력해주세요.")
      return
    }

    // 이미지 업로드 검증
    if (formData.uploaded_images.length === 0) {
      setError("최소 하나의 이미지를 업로드해주세요.")
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
      // 발행 상태 결정
      let boardStatus = 1; // 기본값: 임시저장
      if (publishType === 'immediate') {
        boardStatus = 3; // 즉시 발행
      } else if (publishType === 'scheduled') {
        boardStatus = 2; // 예약 발행
      }

      // 게시글 데이터 준비
      const teamId = user?.teams?.[0]?.group_id || 1

      if (!teamId) {
        setError("팀 정보를 찾을 수 없습니다.")
        setSubmitting(false)
        return
      }

      const boardData = {
        influencer_id: formData.influencer_id,
        board_topic: formData.board_topic,
        board_description: formData.board_description,
        board_platform: formData.board_platform,
        board_hash_tag: formData.board_hashtag.join(' '),
        team_id: teamId,
        board_status: boardStatus,
        // 예약 발행 시 스케줄 정보 추가
        ...(publishType === 'scheduled' && {
          scheduled_at: `${scheduledDate}T${scheduledTime}:00`
        })
      };

      console.log('게시글 데이터:', boardData)
      console.log('이미지 개수:', formData.uploaded_images.length)
      console.log('팀 ID:', teamId)
      console.log('사용자 정보:', user)

      // 통합 API 사용: 게시글과 이미지를 함께 생성
      const formDataToSend = new FormData()
      formDataToSend.append('board_data', JSON.stringify(boardData))

      // 다중 이미지 추가
      formData.uploaded_images.forEach((image, index) => {
        formDataToSend.append("files", image)
      })

      console.log('FormData 내용:')
      for (let [key, value] of formDataToSend.entries()) {
        console.log(`${key}:`, value)
      }

      await apiClient.post('/api/v1/boards/create-with-image', formDataToSend)

      router.push('/post_list')
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '게시글 생성에 실패했습니다.'

      // 인스타그램 업로드 관련 에러인 경우 특별 처리
      if (errorMessage.includes('인스타그램') || errorMessage.includes('Instagram')) {
        setError('게시글이 생성되었지만 인스타그램 업로드에 실패했습니다. 인스타그램 계정 설정을 확인해주세요.')
      } else {
        setError(errorMessage)
      }
    } finally {
      setSubmitting(false)
    }
  }

  // 권한 확인
  if (!hasPermission('content', 'create')) {
    return (
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
    )
  }

  return (
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
              <h2 className="text-xl font-semibold mb-2">인스타그램 연동 인플루언서가 없습니다</h2>
              <p className="text-gray-600 mb-4">
                게시글을 생성하려면 먼저 AI 인플루언서를 생성하고, 학습을 완료한 후 인스타그램 계정과 연동해야 합니다.
              </p>
              <div className="space-y-3">
                <Link href="/create-model">
                  <Button>AI 인플루언서 생성하기</Button>
                </Link>
                <div className="text-sm text-gray-500">
                  또는 기존 인플루언서에 인스타그램 계정을 연동하세요
                </div>
              </div>
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
                        <SelectValue placeholder="인플루언서를 선택하세요">
                          {formData.influencer_id && (
                            <div className="flex items-center space-x-2">
                              <span>{influencers.find(inf => inf.influencer_id === formData.influencer_id)?.influencer_name}</span>
                              <Instagram className="h-4 w-4 text-pink-500" />
                              <span className="text-xs text-gray-500">
                                @{influencers.find(inf => inf.influencer_id === formData.influencer_id)?.instagram_username}
                              </span>
                            </div>
                          )}
                        </SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        {influencers.map((influencer) => (
                          <SelectItem key={influencer.influencer_id} value={influencer.influencer_id}>
                            <div className="flex flex-col space-y-1">
                              <div className="flex items-center space-x-2">
                                <span className="font-medium">{influencer.influencer_name}</span>
                                <Instagram className="h-4 w-4 text-pink-500" />
                              </div>
                              <div className="text-xs text-gray-500">
                                @{influencer.instagram_username}
                              </div>
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
                        {PLATFORM_OPTIONS.map((platform) => {
                          const IconComponent = platform.icon;
                          return (
                            <SelectItem key={platform.value} value={platform.value.toString()}>
                              <div className="flex items-center space-x-2">
                                <IconComponent className="w-5 h-5 text-gray-600" />
                                <div>
                                  <div className="font-medium">{platform.label}</div>
                                  <div className="text-xs text-gray-500">{platform.description}</div>
                                </div>
                              </div>
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* 이미지 업로드 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <ImageIcon className="h-5 w-5" />
                  <span>게시글 내용 및 이미지</span>
                </CardTitle>
                <CardDescription>게시글의 내용을 작성하고 이미지를 업로드하세요</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">

                {/* 이미지 업로드 영역 */}
                <div>
                  <Label htmlFor="image_upload">이미지 파일 업로드</Label>

                  {/* 업로드된 이미지가 있을 때 */}
                  {formData.uploaded_images.length > 0 && (
                    <div className="mt-2 border-2 border-gray-200 rounded-lg p-4 bg-gray-50">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-sm font-medium text-gray-700">
                          업로드된 이미지 ({formData.uploaded_images.length}개)
                        </h4>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => setFormData(prev => ({ ...prev, uploaded_images: [] }))}
                          className="text-red-600 hover:text-red-700"
                        >
                          모두 제거
                        </Button>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        {formData.uploaded_images.map((image, index) => (
                          <div key={index} className="relative">
                            <img
                              src={URL.createObjectURL(image)}
                              alt={`Uploaded ${index + 1}`}
                              className="max-w-full max-h-32 object-cover rounded-md border"
                            />
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => removeImage(index)}
                              className="absolute top-1 right-1 text-red-600 hover:text-red-700 bg-white"
                            >
                              ×
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 업로드 영역 */}
                  <div
                    className={`relative group transition-all duration-300 ${isDragOver
                      ? "scale-105"
                      : formData.uploaded_images.length >= 5
                        ? "opacity-50 cursor-not-allowed"
                        : "hover:scale-[1.02]"
                      }`}
                    onDragOver={formData.uploaded_images.length >= 5 ? undefined : handleDragOver}
                    onDragLeave={formData.uploaded_images.length >= 5 ? undefined : handleDragLeave}
                    onDrop={formData.uploaded_images.length >= 5 ? undefined : handleDrop}
                  >
                    <div className={`
                        relative overflow-hidden rounded-xl border-2 border-dashed transition-all duration-300
                        ${isDragOver
                        ? "border-blue-500 bg-gradient-to-br from-blue-50 to-indigo-50 shadow-lg shadow-blue-100"
                        : formData.uploaded_images.length >= 5
                          ? "border-gray-200 bg-gray-50"
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
                            ${isDragOver
                            ? "bg-blue-100 shadow-lg shadow-blue-200"
                            : "bg-gray-100 group-hover:bg-blue-100 group-hover:shadow-lg group-hover:shadow-blue-200"
                          }
                          `}>
                          <Upload className={`
                              h-8 w-8 transition-all duration-300
                              ${isDragOver
                              ? "text-blue-600 scale-110"
                              : "text-gray-500 group-hover:text-blue-600 group-hover:scale-110"
                            }
                            `} />
                          {/* 애니메이션 효과 */}
                          {isDragOver && (
                            <div className="absolute inset-0 rounded-full border-2 border-blue-300 animate-ping"></div>
                          )}
                        </div>

                        {/* 텍스트 영역 */}
                        <div className="space-y-3">
                          <h3 className={`
                              text-xl font-semibold transition-colors duration-300
                              ${isDragOver ? "text-blue-700" : formData.uploaded_images.length >= 5 ? "text-gray-500" : "text-gray-800 group-hover:text-blue-700"}
                            `}>
                            {isDragOver ? "여기에 놓으세요!" : formData.uploaded_images.length >= 5 ? "최대 개수 도달" : "이미지 업로드"}
                          </h3>
                          <p className={`
                              text-sm transition-colors duration-300 max-w-md mx-auto
                              ${isDragOver ? "text-blue-600" : formData.uploaded_images.length >= 5 ? "text-gray-500" : "text-gray-600 group-hover:text-blue-600"}
                            `}>
                            {formData.uploaded_images.length >= 5
                              ? "이미지 5장이 모두 업로드되었습니다. 추가 업로드를 원하면 기존 이미지를 제거하세요."
                              : "게시글에 사용할 이미지를 드래그하여 놓거나 클릭하여 선택하세요"
                            }
                          </p>
                          <p className="text-xs text-gray-500">
                            지원 형식: JPG, PNG, GIF, WebP (최대 5MB)
                          </p>
                          <p className="text-xs text-blue-600 mt-2">
                            💡 이미지를 업로드하면 AI가 이미지와 텍스트를 모두 분석하여 더 정확한 게시글을 생성합니다
                          </p>
                          <p className="text-xs text-orange-600 mt-1">
                            ⚠️ 최대 5장까지 업로드 가능합니다 ({formData.uploaded_images.length}/5)
                          </p>
                        </div>

                        {/* 파일 선택 버튼 */}
                        <div className="mt-6">
                          <input
                            id="image_upload"
                            type="file"
                            accept="image/*"
                            multiple
                            onChange={handleImageUpload}
                            className="hidden"
                            disabled={formData.uploaded_images.length >= 5}
                          />
                          <label htmlFor="image_upload">
                            <Button
                              className={`
                                  transition-all duration-300 cursor-pointer
                                  ${isDragOver
                                  ? "bg-blue-600 hover:bg-blue-700 text-white shadow-lg"
                                  : formData.uploaded_images.length >= 5
                                    ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                                    : "bg-white hover:bg-blue-50 text-gray-700 border-gray-300 hover:border-blue-400 hover:text-blue-700 shadow-sm hover:shadow-md"
                                }
                                `}
                              asChild
                              disabled={formData.uploaded_images.length >= 5}
                            >
                              <span className="flex items-center gap-2">
                                <Upload className="h-4 w-4" />
                                {formData.uploaded_images.length >= 5 ? "최대 개수 도달" : "파일 선택"}
                              </span>
                            </Button>
                          </label>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 게시글 주제 */}
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

                {/* 게시글 내용 */}
                <div>
                  <div className="flex items-center justify-between">
                    <Label htmlFor="board_description">게시글 내용</Label>
                    <div className="flex space-x-2">
                      {isGenerateEnabled && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={generateContent}
                          disabled={isEnhancing}
                          className="flex items-center gap-1"
                        >
                          {isEnhancing ? (
                            <>
                              <Loader2 className="h-3 w-3 animate-spin" />
                              생성 중...
                            </>
                          ) : (
                            <>
                              <Sparkles className="h-3 w-3" />
                              AI 생성
                              {formData.uploaded_images.length > 0 && formData.board_description.trim() && (
                                <span className="ml-1 text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full">
                                  {formData.uploaded_images.length}개 이미지 + 텍스트 분석
                                </span>
                              )}
                              {formData.uploaded_images.length > 0 && !formData.board_description.trim() && (
                                <span className="ml-1 text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full">
                                  {formData.uploaded_images.length}개 이미지 분석
                                </span>
                              )}
                              {formData.uploaded_images.length === 0 && formData.board_description.trim() && (
                                <span className="ml-1 text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full">
                                  텍스트 기반 생성
                                </span>
                              )}
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
                        <h4 className="font-medium text-green-900 mb-2 flex items-center">
                          <Sparkles className="h-4 w-4 mr-2" />
                          AI가 생성한 본문
                          {formData.uploaded_images.length > 0 && (
                            <span className="ml-2 text-xs bg-green-200 text-green-800 px-2 py-1 rounded-full">
                              {formData.uploaded_images.length}개 이미지 + 텍스트 기반
                            </span>
                          )}
                        </h4>
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
                            onClick={convertToInfluencerStyle}
                            variant="outline"
                            className="flex items-center space-x-2 border-purple-400 hover:border-purple-600 hover:bg-purple-50 transition-colors"
                            disabled={isConverting}
                          >
                            {isConverting ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <User className="h-4 w-4" />
                            )}
                            <span>{isConverting ? "변환 중..." : "인플루언서 말투로 변환"}</span>
                          </Button>
                          <Button type="button" onClick={approveGenerated} variant="outline" className="flex items-center space-x-2 border-green-400 hover:border-green-600 hover:bg-green-50 transition-colors">
                            <span>✓</span>
                            <span>본문 적용</span>
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                  {converted && (
                    <div className="mt-4 space-y-4">
                      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg relative">
                        <h4 className="font-medium text-blue-900 mb-2 flex items-center">
                          <User className="h-4 w-4 mr-2" />
                          인플루언서 말투로 변환된 본문
                        </h4>
                        <div className="text-sm text-blue-800 whitespace-pre-wrap bg-white p-3 rounded border mb-4 max-h-60 overflow-y-auto leading-relaxed">
                          {converted}
                        </div>
                        <span className="text-xs text-blue-600 block mt-2">{converted.length}자 • 스크롤 또는 전체 보기로 확인</span>
                        <div className="flex flex-wrap justify-end items-center gap-2 mt-6">
                          <Button type="button" onClick={approveConverted} variant="outline" className="flex items-center space-x-2 border-blue-400 hover:border-blue-600 hover:bg-blue-50 transition-colors">
                            <span>✓</span>
                            <span>본문 적용 (해시태그 포함)</span>
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
                    className="w-full bg-blue-500 hover:bg-blue-600"
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
                className="bg-blue-500 hover:bg-blue-600"
              >
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    저장 중...
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4 mr-2" />
                    게시글 발행
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
                {imagePreviews.length > 0 && (
                  <div className="my-4">
                    <h4 className="font-medium text-gray-700 mb-2">업로드된 이미지 ({imagePreviews.length}개)</h4>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                      {imagePreviews.map((preview, index) => (
                        <div key={index} className="relative group">
                          <img
                            src={preview}
                            alt={`Preview ${index + 1}`}
                            className="w-full h-32 object-cover rounded-lg border"
                          />
                          <button
                            type="button"
                            onClick={() => removeImage(index)}
                            className="absolute top-1 right-1 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                    {/* 이미지 정보 표시 */}
                    {imageInfo && (
                      <div className="mt-2 text-xs text-gray-600 text-center">
                        {imageInfo.isResized ? (
                          <div className="space-y-1">
                            <div>
                              <span>원본: {imageInfo.originalSize?.width}×{imageInfo.originalSize?.height}</span>
                              <span className="mx-2">→</span>
                              <span className="text-blue-600 font-medium">패딩 처리: {imageInfo.resizedSize?.width}×{imageInfo.resizedSize?.height}</span>
                            </div>
                            <div className="text-blue-600">
                              💡 Instagram 비율에 맞게 자동 패딩 처리됨
                            </div>
                          </div>
                        ) : (
                          <span>크기: {imageInfo.originalSize?.width}×{imageInfo.originalSize?.height}</span>
                        )}
                      </div>
                    )}
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

      {/* 전체 미리보기 모달 제거 */}
    </div>
  )
}
