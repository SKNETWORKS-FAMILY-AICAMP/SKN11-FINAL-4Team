"use client"

import type React from "react"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Navigation } from "@/components/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ModelService } from "@/lib/services/model.service"
import { useAuth } from "@/hooks/use-auth"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { Upload, ArrowLeft, Lightbulb, MessageCircle } from "lucide-react"
import Link from "next/link"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"

export default function CreateModelPage() {
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    modelType: "", // "character" 또는 "human"
    personality: "",
    tone: "",
    customTone: "",
    mbti: "",
    gender: "",
    age: "",
    imageMethod: "upload", // "upload" 또는 "prompt"
    hairStyle: "",
    mood: "",
  })
  const [files, setFiles] = useState({
    imageSamples: null as File[] | null,
  })
  const [isLoading, setIsLoading] = useState(false)
  const [showCustomInput, setShowCustomInput] = useState(false)
  const [toneTab, setToneTab] = useState("recommend")
  const router = useRouter()
  const { user } = useAuth()

  const handleInputChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  const handleFileUpload = (type: keyof typeof files, uploadedFiles: FileList | null) => {
    if (uploadedFiles) {
      setFiles((prev) => ({ ...prev, [type]: Array.from(uploadedFiles) }))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // 이미지 검증
    const hasImageUpload = files.imageSamples && files.imageSamples.length > 0
    const hasImagePrompt = formData.imageMethod === "prompt" && 
                          formData.hairStyle.trim() !== "" && 
                          formData.mood.trim() !== ""
    // 성격 및 말투 검증
    const hasPersonality = formData.personality.trim() !== ""
    const hasTone = formData.tone.trim() !== "" || formData.customTone.trim() !== ""
    
    if (!hasPersonality) {
      alert("성격을 입력해주세요.")
      return
    }
    if (!hasTone) {
      alert("말투를 선택하거나 직접 입력해주세요.")
      return
    }
    if (!hasImageUpload && !hasImagePrompt) {
      alert("이미지를 업로드하거나 이미지 생성 프롬프트를 입력해주세요.")
      return
    }
    
    setIsLoading(true)

    try {
      // 사용자 인증 확인
      if (!user || !user.teams || user.teams.length === 0) {
        alert("❌ 인플루언서 생성 권한이 없습니다.\n\n팀에 소속되어야 인플루언서를 생성할 수 있습니다.")
        setIsLoading(false)
        return
      }

      // 백엔드 API 호출 데이터 준비
      const createInfluencerData = {
        user_id: user.user_id,
        group_id: user.teams[0].group_id, // 첫 번째 팀의 group_id 사용
        style_preset_id: formData.modelType || "default", 
        mbti_id: formData.mbti ? parseInt(formData.mbti) : null,
        influencer_name: formData.name,
        influencer_description: formData.description,
        image_url: formData.imageUrl || null,
        influencer_data_url: null,
        learning_status: 0, // 초기 상태
        influencer_model_repo: "",
        chatbot_option: true
      }

      // 실제 인플루언서 생성 API 호출
      const response = await ModelService.createInfluencer(createInfluencerData)
      
      console.log('인플루언서 생성 성공:', response)
      
      // 성공 알림 표시
      alert(`🎉 AI 인플루언서 "${formData.name}"가 생성되었습니다!\n\n다음 작업이 백그라운드에서 자동으로 진행됩니다:\n• 2,000개 QA 쌍 생성\n• S3에 데이터 업로드\n• QLoRA 4비트 양자화 파인튜닝\n• Hugging Face에 모델 업로드\n\n완료 시 이메일과 웹 알림을 받으실 수 있습니다.`)
      
      setIsLoading(false)
      router.push("/dashboard")
      
    } catch (error) {
      console.error('인플루언서 생성 실패:', error)
      setIsLoading(false)
      
      // 에러 알림 표시
      alert(`❌ 인플루언서 생성에 실패했습니다.\n\n오류: ${error instanceof Error ? error.message : '알 수 없는 오류'}\n\n다시 시도해주세요.`)
    }
  }

  // 성격 기반 대화 예시 생성
  const generateConversationExamples = (personality: string) => {
    if (!personality.trim()) return []

    const personalityLower = personality.toLowerCase()

    // 성격 키워드에 따른 대화 예시
    const conversationMap: Record<string, Array<{title: string, example: string, tone: string}>> = {
      친근: [
        {
          title: "친근하고 다정한",
          example: "안녕하세요! 오늘도 좋은 하루 보내고 계시나요? 😊\n\n저는 오늘 정말 특별한 것을 발견했는데, 여러분과 함께 나누고 싶어서 급하게 글을 써봤어요!",
          tone: "친근하고 다정한"
        },
        {
          title: "편안하고 따뜻한",
          example: "여러분 안녕하세요~ 💕\n\n오늘은 정말 좋은 날씨네요! 이런 날에는 가벼운 산책이나 카페에서 여유롭게 시간을 보내는 것도 좋을 것 같아요.",
          tone: "편안하고 따뜻한"
        },
        {
          title: "가까운 친구 같은",
          example: "야! 오늘 진짜 대박인 일이 있었어! 🤩\n\n너희들도 꼭 알아야 할 것 같아서 바로 공유하는 거야. 정말 신기했어!",
          tone: "가까운 친구 같은"
        }
      ],
      전문: [
        {
          title: "정중하고 전문적인",
          example: "안녕하세요, 여러분.\n\n오늘은 [주제]에 대해 자세히 알아보겠습니다. 전문적인 관점에서 분석한 내용을 공유드리겠습니다.",
          tone: "정중하고 전문적인"
        },
        {
          title: "신뢰할 수 있는",
          example: "안녕하세요.\n\n검증된 정보를 바탕으로 [주제]에 대한 정확한 분석 결과를 말씀드리겠습니다.",
          tone: "신뢰할 수 있는"
        },
        {
          title: "지식이 풍부한",
          example: "안녕하세요.\n\n[주제]에 대한 심도 있는 연구 결과를 바탕으로 여러분께 유용한 정보를 제공하겠습니다.",
          tone: "지식이 풍부한"
        }
      ],
      활발: [
        {
          title: "에너지 넘치는",
          example: "안녕하세요 여러분! 🔥\n\n오늘은 정말 대박인 소식을 들고 왔어요! 너무 신나서 바로 공유하고 싶었어요!",
          tone: "에너지 넘치는"
        },
        {
          title: "밝고 긍정적인",
          example: "안녕하세요! ✨\n\n오늘도 정말 좋은 하루네요! 여러분과 함께 이런 좋은 정보를 나눌 수 있어서 정말 행복해요!",
          tone: "밝고 긍정적인"
        },
        {
          title: "열정적이고 활기찬",
          example: "여러분 안녕하세요! 🎉\n\n오늘은 정말 특별한 순간을 여러분과 함께 나누고 싶어요! 너무 흥미진진해요!",
          tone: "열정적이고 활기찬"
        }
      ],
      차분: [
        {
          title: "차분하고 안정적인",
          example: "안녕하세요.\n\n오늘은 [주제]에 대해 차분히 생각해보는 시간을 가져보겠습니다.",
          tone: "차분하고 안정적인"
        },
        {
          title: "신중하고 사려깊은",
          example: "안녕하세요.\n\n[주제]에 대해 깊이 있게 고민해보았습니다. 여러분과 함께 생각을 나누고 싶어요.",
          tone: "신중하고 사려깊은"
        },
        {
          title: "평온하고 여유로운",
          example: "안녕하세요.\n\n오늘은 여유롭게 [주제]에 대해 이야기해보는 시간을 가져보겠습니다.",
          tone: "평온하고 여유로운"
        }
      ],
      유머: [
        {
          title: "재치있고 유머러스한",
          example: "안녕하세요 여러분! 😄\n\n오늘은 정말 재미있는 일이 있었는데, 여러분도 웃으실 것 같아서 공유해요!",
          tone: "재치있고 유머러스한"
        },
        {
          title: "웃음을 주는",
          example: "여러분 안녕하세요! 😂\n\n오늘은 정말 웃음이 나오는 상황을 겪었어요. 여러분도 함께 웃어주세요!",
          tone: "웃음을 주는"
        },
        {
          title: "밝고 재미있는",
          example: "안녕하세요! 🎭\n\n오늘은 정말 재미있는 이야기를 들고 왔어요! 여러분도 즐거워하실 것 같아요!",
          tone: "밝고 재미있는"
        }
      ]
    }

    // 성격에서 키워드 찾기
    const matchedConversations: Array<{title: string, example: string, tone: string}> = []
    Object.keys(conversationMap).forEach((key) => {
      if (personalityLower.includes(key)) {
        matchedConversations.push(...conversationMap[key])
      }
    })

    // 매칭되는 것이 없으면 기본 예시 제공
    if (matchedConversations.length === 0) {
      return [
        {
          title: "친근하고 다정한",
          example: "안녕하세요! 오늘도 좋은 하루 보내고 계시나요? 😊\n\n저는 오늘 정말 특별한 것을 발견했는데, 여러분과 함께 나누고 싶어서 급하게 글을 써봤어요!",
          tone: "친근하고 다정한"
        },
        {
          title: "정중하고 전문적인",
          example: "안녕하세요, 여러분.\n\n오늘은 [주제]에 대해 자세히 알아보겠습니다. 전문적인 관점에서 분석한 내용을 공유드리겠습니다.",
          tone: "정중하고 전문적인"
        },
        {
          title: "밝고 긍정적인",
          example: "안녕하세요! ✨\n\n오늘도 정말 좋은 하루네요! 여러분과 함께 이런 좋은 정보를 나눌 수 있어서 정말 행복해요!",
          tone: "밝고 긍정적인"
        }
      ]
    }

    // 중복 제거하고 최대 3개까지
    const uniqueConversations = matchedConversations.filter((item, index, self) => 
      index === self.findIndex(t => t.title === item.title)
    )
    return uniqueConversations.slice(0, 3)
  }

  const conversationExamples = generateConversationExamples(formData.personality)

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <Link href="/dashboard" className="inline-flex items-center text-blue-600 hover:text-blue-800 mb-4">
            <ArrowLeft className="h-4 w-4 mr-2" />
            대시보드로 돌아가기
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">새 AI 인플루언서 생성</h1>
          <p className="text-gray-600 mt-2">AI 인플루언서의 특성과 학습 데이터를 설정하세요</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-8">
          {/* 기본 정보 */}
          <Card>
            <CardHeader>
              <CardTitle>기본 정보</CardTitle>
              <CardDescription>AI 인플루언서의 기본적인 정보를 입력하세요</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="name">모델 이름</Label>
                <Input
                  id="name"
                  placeholder="예: 패션 인플루언서 AI"
                  value={formData.name}
                  onChange={(e) => handleInputChange("name", e.target.value)}
                  required
                />
              </div>

              <div>
                <Label htmlFor="description">설명</Label>
                <Textarea
                  id="description"
                  placeholder="AI 인플루언서에 대한 상세한 설명을 입력하세요"
                  value={formData.description}
                  onChange={(e) => handleInputChange("description", e.target.value)}
                  rows={3}
                  required
                />
              </div>

              <div>
                <Label htmlFor="modelType">모델 유형</Label>
                <Select value={formData.modelType} onValueChange={(value) => handleInputChange("modelType", value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="모델 유형을 선택하세요" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="character">캐릭터형 (애니메이션, 만화 스타일)</SelectItem>
                    <SelectItem value="human">사람형 (실제 사람과 유사한 형태)</SelectItem>
                    <SelectItem value="objects">사물형 (사물과 유사한 형태)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-gray-500 mt-1">
                  💡 캐릭터형은 애니메이션이나 만화 스타일로, 사람형은 실제 사람과 유사하게 생성됩니다
                </p>
              </div>

              <div className="space-y-4">
                <h4 className="font-medium text-gray-900">추가 설정 (선택사항)</h4>
                <p className="text-sm text-gray-600">
                  아래 설정들은 모두 선택사항입니다. 필요한 경우에만 설정하세요.
                </p>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <Label htmlFor="mbti">MBTI (선택사항)</Label>
                    <Select value={formData.mbti} onValueChange={(value) => handleInputChange("mbti", value)}>
                      <SelectTrigger>
                        <SelectValue placeholder="MBTI 선택 (선택사항)" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">선택 안함</SelectItem>
                        <SelectItem value="ENFP">ENFP - 재기발랄한 활동가</SelectItem>
                        <SelectItem value="ENFJ">ENFJ - 정의로운 사회운동가</SelectItem>
                        <SelectItem value="ENTP">ENTP - 뜨거운 논쟁을 즐기는 변론가</SelectItem>
                        <SelectItem value="ENTJ">ENTJ - 대담한 통솔자</SelectItem>
                        <SelectItem value="ESFP">ESFP - 자유로운 영혼의 연예인</SelectItem>
                        <SelectItem value="ESFJ">ESFJ - 사교적인 외교관</SelectItem>
                        <SelectItem value="ESTP">ESTP - 모험을 즐기는 사업가</SelectItem>
                        <SelectItem value="ESTJ">ESTJ - 엄격한 관리자</SelectItem>
                        <SelectItem value="INFP">INFP - 열정적인 중재자</SelectItem>
                        <SelectItem value="INFJ">INFJ - 선의의 옹호자</SelectItem>
                        <SelectItem value="INTP">INTP - 논리적인 사색가</SelectItem>
                        <SelectItem value="INTJ">INTJ - 용의주도한 전략가</SelectItem>
                        <SelectItem value="ISFP">ISFP - 호기심 많은 예술가</SelectItem>
                        <SelectItem value="ISFJ">ISFJ - 용감한 수호자</SelectItem>
                        <SelectItem value="ISTP">ISTP - 만능 재주꾼</SelectItem>
                        <SelectItem value="ISTJ">ISTJ - 현실주의자</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label htmlFor="gender">성별 (선택사항)</Label>
                    <Select value={formData.gender} onValueChange={(value) => handleInputChange("gender", value)}>
                      <SelectTrigger>
                        <SelectValue placeholder="성별 선택 (선택사항)" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">선택 안함</SelectItem>
                        <SelectItem value="male">남성</SelectItem>
                        <SelectItem value="female">여성</SelectItem>
                        <SelectItem value="other">기타</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label htmlFor="age">나이 (선택사항)</Label>
                    <Input
                      id="age"
                      type="number"
                      placeholder="나이 입력 (선택사항)"
                      value={formData.age}
                      onChange={(e) => handleInputChange("age", e.target.value)}
                      min="1"
                      max="100"
                    />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 성격 및 말투 설정 */}
          <Card>
            <CardHeader>
              <CardTitle>성격 및 말투</CardTitle>
              <CardDescription>AI 인플루언서의 성격과 커뮤니케이션 스타일을 정의하세요</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <Label htmlFor="personality">성격</Label>
                <Input
                  id="personality"
                  placeholder="예: 친근하고 트렌디한, 전문적이고 신뢰할 수 있는, 활발하고 에너지 넘치는"
                  value={formData.personality}
                  onChange={(e) => handleInputChange("personality", e.target.value)}
                  required
                />
                <p className="text-xs text-gray-500 mt-1">💡 성격을 입력하면 아래 대화 예시가 자동으로 생성됩니다</p>
              </div>

              <div>
                <Label className="text-base font-medium">말투 선택</Label>
                <p className="text-sm text-gray-600 mb-4">성격에 맞는 말투를 선택하거나 직접 입력하세요</p>
                <Tabs value={toneTab} onValueChange={setToneTab} className="w-full mb-4">
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="recommend">추천 말투 선택</TabsTrigger>
                    <TabsTrigger value="custom">직접 입력</TabsTrigger>
                  </TabsList>
                  <TabsContent value="recommend">
                    {conversationExamples.length > 0 ? (
                      <div className="space-y-4 mb-4">
                        <div className="flex items-center space-x-2 text-sm text-blue-600">
                          <Lightbulb className="h-4 w-4" />
                          <span>성격 기반 추천 말투</span>
                        </div>
                        <div className="grid grid-cols-1 gap-4">
                          {conversationExamples.map((example, index) => (
                            <Card
                              key={index}
                              className={`cursor-pointer transition-all hover:shadow-md ${formData.tone === example.tone ? 'ring-2 ring-blue-500 bg-blue-50' : ''}`}
                              onClick={() => {
                                handleInputChange("tone", example.tone)
                                handleInputChange("customTone", "")
                              }}
                            >
                              <CardHeader className="pb-3">
                                <div className="flex items-center space-x-2">
                                  <MessageCircle className="h-4 w-4 text-blue-600" />
                                  <CardTitle className="text-sm">{example.title}</CardTitle>
                                </div>
                              </CardHeader>
                              <CardContent className="pt-0">
                                <p className="text-xs text-gray-600 whitespace-pre-line">
                                  {example.example}
                                </p>
                              </CardContent>
                            </Card>
                          ))}
                        </div>
                        {formData.tone && (
                          <div className="mt-2 text-xs text-green-700">선택된 말투: {formData.tone}</div>
                        )}
                      </div>
                    ) : (
                      <div className="mt-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                        <div className="flex items-center space-x-2">
                          <Lightbulb className="h-4 w-4 text-yellow-600" />
                          <span className="text-sm text-yellow-800">
                            성격을 입력해주세요. 입력된 성격을 기반으로 말투를 생성합니다.
                          </span>
                        </div>
                      </div>
                    )}
                  </TabsContent>
                  <TabsContent value="custom">
                    <div>
                      <Label htmlFor="customTone">사용자 정의 말투</Label>
                      <Input
                        id="customTone"
                        placeholder="예: 캐주얼하고 친밀한, 정중하고 전문적인"
                        value={formData.customTone}
                        onChange={(e) => {
                          handleInputChange("customTone", e.target.value)
                          handleInputChange("tone", "")
                        }}
                      />
                      {formData.customTone && (
                        <div className="mt-2 text-xs text-green-700">입력된 말투: {formData.customTone}</div>
                      )}
                    </div>
                  </TabsContent>
                </Tabs>
              </div>
            </CardContent>
          </Card>

          {/* 이미지 설정 */}
          <Card>
            <CardHeader>
              <CardTitle>이미지 설정</CardTitle>
              <CardDescription>
                AI 인플루언서의 이미지를 설정하세요.<br/>
                설정하지 않으면 기본 이미지가 자동으로 생성됩니다.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* 이미지 생성 방법 탭 */}
              <div>
                <Label className="text-base font-medium mb-3 block">이미지 생성 방법</Label>
                <Tabs value={formData.imageMethod} onValueChange={(value) => handleInputChange("imageMethod", value)} className="w-full">
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="upload">이미지 업로드</TabsTrigger>
                    <TabsTrigger value="prompt">이미지 생성</TabsTrigger>
                  </TabsList>
                  
                  <TabsContent value="upload" className="mt-4">
                    <div>
                      <Label className="text-base font-medium mb-3 block">이미지 파일 업로드</Label>
                      <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors">
                        <Upload className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                        <p className="text-sm text-gray-600 mb-2">이미지 파일을 드래그하거나 클릭하여 업로드</p>
                        <input
                          type="file"
                          multiple
                          accept=".jpg,.jpeg,.png,.webp"
                          onChange={(e) => handleFileUpload("imageSamples", e.target.files)}
                          className="hidden"
                          id="image-upload"
                        />
                        <Label htmlFor="image-upload" className="cursor-pointer">
                          <Button type="button" variant="outline" size="sm">
                            파일 선택
                          </Button>
                        </Label>
                        {files.imageSamples && (
                          <p className="text-xs text-green-600 mt-2">{files.imageSamples.length}개 파일 선택됨</p>
                        )}
                      </div>
                    </div>
                  </TabsContent>

                  <TabsContent value="prompt" className="mt-4">
                    <div className="space-y-4">
                      <Label className="text-base font-medium block">이미지 생성 프롬프트</Label>
                      
                      <div>
                        <Label htmlFor="hairStyle">헤어스타일</Label>
                        <Input
                          id="hairStyle"
                          placeholder="예: 긴 생머리, 숏컷, 웨이브 머리, 포니테일"
                          value={formData.hairStyle}
                          onChange={(e) => handleInputChange("hairStyle", e.target.value)}
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          💡 원하는 헤어스타일을 자세히 설명해주세요
                        </p>
                      </div>

                      <div>
                        <Label htmlFor="mood">분위기/스타일</Label>
                        <Input
                          id="mood"
                          placeholder="예: 밝고 친근한, 세련되고 우아한, 캐주얼하고 편안한"
                          value={formData.mood}
                          onChange={(e) => handleInputChange("mood", e.target.value)}
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          💡 원하는 분위기나 스타일을 설명해주세요
                        </p>
                      </div>
                    </div>
                  </TabsContent>
                </Tabs>
              </div>
            </CardContent>
          </Card>

          {/* 제출 버튼 */}
          <div className="flex justify-end space-x-4">
            <Link href="/dashboard">
              <Button type="button" variant="outline">
                취소
              </Button>
            </Link>
            <Button 
              type="submit" 
              disabled={
                isLoading || 
                !formData.name || 
                !formData.description || 
                !formData.modelType ||
                !formData.personality ||
                (!formData.tone && !formData.customTone) ||
                (!(files.imageSamples && files.imageSamples.length > 0) && 
                 !(formData.imageMethod === "prompt" && formData.hairStyle.trim() !== "" && formData.mood.trim() !== ""))
              }
            >
              {isLoading ? "생성 중..." : "AI 모델 생성"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}