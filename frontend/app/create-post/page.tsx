"use client"

import { useState, useRef } from "react"
import { useRouter } from "next/navigation"
import { Navigation } from "@/components/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { PenTool, ImageIcon, Send, Lightbulb, Plus } from "lucide-react"
import type { AIModel } from "@/lib/types"

// 샘플 모델 데이터
const availableModels: AIModel[] = [
  {
    id: "1",
    name: "패션 인플루언서 AI",
    description: "20대 여성 타겟의 패션 트렌드 전문 AI 인플루언서",
    personality: "친근하고 트렌디한",
    tone: "캐주얼하고 친밀한",
    status: "ready",
    createdAt: "2024-01-15",
  },
  {
    id: "3",
    name: "피트니스 코치 AI",
    description: "운동 및 건강 관리 전문 AI 인플루언서",
    personality: "동기부여하고 에너지 넘치는",
    tone: "격려하고 활기찬",
    status: "ready",
    createdAt: "2024-01-10",
  },
]

export default function CreatePostPage() {
  const [selectedModel, setSelectedModel] = useState<string>("")
  const [postData, setPostData] = useState({
    title: "",
    content: "",
    includeContent: "",
    hashtags: "",
    platform: "",
    scheduledDate: "",
  })
  const [generatedContent, setGeneratedContent] = useState("")
  const [isGenerating, setIsGenerating] = useState(false)
  const [isPublishing, setIsPublishing] = useState(false)
  const [previewImages, setPreviewImages] = useState<string[]>([])

  const fileInputRef = useRef<HTMLInputElement>(null)
  const router = useRouter()

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files) {
      const imageUrls = Array.from(files).map((file) => URL.createObjectURL(file))
      setPreviewImages((prev) => [...prev, ...imageUrls])
    }
  }

  const triggerImageUpload = () => {
    fileInputRef.current?.click()
  }

  const handleInputChange = (field: string, value: string) => {
    setPostData((prev) => ({ ...prev, [field]: value }))
  }

  const handleGenerateContent = async () => {
    if (!selectedModel || !postData.title) return

    setIsGenerating(true)

    // AI 콘텐츠 생성 시뮬레이션 (사용자 요청 내용 포함)
    setTimeout(() => {
      const selectedModelData = availableModels.find((m) => m.id === selectedModel)

      // 사용자가 포함하고 싶은 내용을 반영한 콘텐츠 생성
      let baseContent = ""

      if (selectedModel === "1") {
        // 패션 인플루언서 AI
        baseContent = `안녕하세요 여러분! 🌟 오늘은 ${postData.title}에 대해 이야기해보려고 해요!\n\n`

        if (postData.includeContent) {
          baseContent += `${postData.includeContent}\n\n`
        }

        baseContent += `요즘 정말 핫한 트렌드인데, 저도 직접 체험해보니까 정말 만족스러웠어요! 특히 컬러감이나 디자인이 너무 예뻐서 여러분께도 꼭 추천하고 싶어요 💕\n\n여러분은 어떻게 생각하시나요? 댓글로 의견 남겨주세요!`
      } else if (selectedModel === "3") {
        // 피트니스 코치 AI
        baseContent = `${postData.title} 관련해서 정말 유용한 팁을 공유해드릴게요! ✨\n\n`

        if (postData.includeContent) {
          baseContent += `${postData.includeContent}\n\n`
        }

        baseContent += `제가 직접 경험해본 결과, 이런 포인트들이 중요한 것 같아요:\n1. 기본기가 가장 중요해요\n2. 꾸준함이 성공의 열쇠예요\n3. 자신만의 스타일을 찾는 게 중요해요\n\n여러분도 한번 시도해보시고 후기 공유해주세요! 💪`
      }

      setGeneratedContent(baseContent)
      setIsGenerating(false)

      // URL 파라미터로 새 게시글 정보를 전달하여 게시글 목록으로 이동
      const params = new URLSearchParams({
        title: postData.title,
        content: baseContent,
        model: selectedModelData?.name || '',
        platform: postData.platform || 'Instagram',
        hashtags: postData.hashtags || ''
      })
      
      router.push(`/post_list?${params.toString()}`)
    }, 2000)
  }

  const handlePublishPost = async () => {
    setIsPublishing(true)

    // 게시글 발행 시뮬레이션
    setTimeout(() => {
      setIsPublishing(false)
      alert("게시글이 성공적으로 발행되었습니다!")

      // 폼 초기화
      setPostData({
        title: "",
        content: "",
        includeContent: "",
        hashtags: "",
        platform: "",
        scheduledDate: "",
      })
      setGeneratedContent("")
    }, 1500)
  }

  const selectedModelData = availableModels.find((m) => m.id === selectedModel)

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">게시글 작성</h1>
          <p className="text-gray-600 mt-2">AI 인플루언서가 작성할 게시글을 생성하고 관리하세요</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 설정 패널 */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <PenTool className="h-5 w-5" />
                  <span>게시글 설정</span>
                </CardTitle>
                <CardDescription>게시글 생성을 위한 설정을 입력하세요</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="model-select">AI 모델</Label>
                    <Select value={selectedModel} onValueChange={setSelectedModel}>
                      <SelectTrigger>
                        <SelectValue placeholder="모델을 선택하세요" />
                      </SelectTrigger>
                      <SelectContent>
                        {availableModels.map((model) => (
                          <SelectItem key={model.id} value={model.id}>
                            {model.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {selectedModelData && (
                    <div className="p-3 bg-blue-50 rounded-lg">
                      <Badge className="bg-green-100 text-green-800 mb-2">준비완료</Badge>
                      <p className="text-xs text-gray-600">{selectedModelData.description}</p>
                    </div>
                  )}

                  <div>
                    <Label htmlFor="title">게시글 주제</Label>
                    <Input
                      id="title"
                      placeholder="예: 겨울 패션 트렌드"
                      value={postData.title}
                      onChange={(e) => handleInputChange("title", e.target.value)}
                    />
                  </div>

                  <div>
                    <Label htmlFor="include-content" className="flex items-center space-x-2">
                      <Lightbulb className="h-4 w-4" />
                      <span>포함할 내용</span>
                    </Label>
                    <Textarea
                      id="include-content"
                      placeholder="게시글에 꼭 포함되었으면 하는 내용을 입력하세요&#10;예: 특정 제품명, 할인 정보, 이벤트 안내, 개인적인 경험담 등"
                      value={postData.includeContent}
                      onChange={(e) => handleInputChange("includeContent", e.target.value)}
                      rows={4}
                    />
                    <p className="text-xs text-gray-500 mt-1">💡 AI가 이 내용을 참고하여 더 맞춤형 게시글을 생성합니다</p>
                  </div>

                  <div>
                    <Label htmlFor="platform">플랫폼</Label>
                    <Select value={postData.platform} onValueChange={(value) => handleInputChange("platform", value)}>
                      <SelectTrigger>
                        <SelectValue placeholder="플랫폼 선택" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="instagram">Instagram</SelectItem>
                        <SelectItem value="facebook">Facebook</SelectItem>
                        <SelectItem value="twitter">Twitter</SelectItem>
                        <SelectItem value="tiktok">TikTok</SelectItem>
                        <SelectItem value="youtube">YouTube</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label htmlFor="hashtags">해시태그</Label>
                    <Input
                      id="hashtags"
                      placeholder="#패션 #트렌드 #스타일"
                      value={postData.hashtags}
                      onChange={(e) => handleInputChange("hashtags", e.target.value)}
                    />
                  </div>

                  <div>
                    <Label htmlFor="scheduled-date">예약 발행</Label>
                    <Input
                      id="scheduled-date"
                      type="datetime-local"
                      value={postData.scheduledDate}
                      onChange={(e) => handleInputChange("scheduledDate", e.target.value)}
                    />
                  </div>

                  {/* 이미지 업로드 */}
                  <div className="space-y-4">
                    <div>
                      <Label className="flex items-center space-x-2">
                        <ImageIcon className="h-4 w-4" />
                        <span>이미지 업로드</span>
                      </Label>
                      <p className="text-xs text-gray-500 mt-1">게시글에 첨부할 이미지를 업로드하세요</p>
                    </div>

                    <input
                      ref={fileInputRef}
                      id="images"
                      type="file"
                      accept="image/*"
                      multiple
                      onChange={handleImageChange}
                      className="hidden"
                    />
                    
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <div 
                        className="aspect-video bg-gray-100 rounded-lg border-2 border-dashed border-gray-300 flex items-center justify-center hover:border-gray-400 transition-colors cursor-pointer"
                        onClick={triggerImageUpload}
                      >
                        <div className="text-center">
                          <Plus className="h-6 w-6 text-gray-400 mx-auto mb-1" />
                          <p className="text-xs text-gray-600">이미지 추가</p>
                        </div>
                      </div>
                      
                      {previewImages.map((src, index) => (
                        <div key={index} className="relative group">
                          <img
                            src={src}
                            alt={`preview-${index}`}
                            className="aspect-video object-cover rounded-lg border"
                          />
                          <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-50 transition-all rounded-lg flex items-center justify-center">
                            <div className="opacity-0 group-hover:opacity-100 transition-opacity flex space-x-1">
                              <Button size="sm" variant="secondary">
                                <ImageIcon className="h-3 w-3" />
                              </Button>
                              <Button 
                                size="sm" 
                                variant="destructive"
                                onClick={() => {
                                  setPreviewImages(prev => prev.filter((_, i) => i !== index))
                                }}
                              >
                                <Plus className="h-3 w-3 rotate-45" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                    
                    <p className="text-xs text-gray-500">
                      권장: 1920x1080px, JPG/PNG/WebP, 최대 10MB
                    </p>
                  </div>

                  <Button
                    onClick={handleGenerateContent}
                    disabled={!selectedModel || !postData.title || isGenerating}
                    className="w-full"
                  >
                    {isGenerating ? "생성 중..." : "콘텐츠 생성"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
          