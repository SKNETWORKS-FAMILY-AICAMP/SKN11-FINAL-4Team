"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { Navigation } from "@/components/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { MessageSquare, Send, Bot, User } from "lucide-react"
import type { AIModel } from "@/lib/types"
import { ModelService, type AIInfluencer } from "@/lib/services/model.service"
import { tokenUtils } from "@/lib/auth"

interface ChatMessage {
  id: string
  type: "user" | "ai"
  content: string
  timestamp: string
  modelId?: string
  modelName?: string
}

// 모델별 응답 스타일
const getModelResponses = (modelId: string, userMessage: string) => {
  const responseMap: Record<string, string[]> = {
    "1": [
      // 패션 인플루언서 AI
      "안녕하세요! 오늘의 패션 트렌드에 대해 이야기해볼까요? 요즘 레이어드 룩이 정말 인기예요! 🌟",
      "와, 정말 좋은 질문이네요! 이번 시즌 컬러는 파스텔 톤이 대세라고 생각해요. 특히 라벤더와 민트 컬러가 예쁘더라고요 💜",
      "패션은 자신감이 가장 중요한 액세서리라고 생각해요! 어떤 스타일이든 본인이 편하고 자신 있게 입는 게 최고예요 ✨",
      "오늘 날씨에 딱 맞는 코디 추천해드릴게요! 가벼운 니트에 데님 재킷 어떠세요? 캐주얼하면서도 세련된 느낌이에요 👗",
    ],
    "2": [
      // 뷰티 전문가 AI
      "안녕하세요. 뷰티에 관한 질문이시군요. 전문적인 조언을 드리겠습니다. 먼저 피부 타입을 파악하는 것이 중요합니다.",
      "해당 제품에 대해 상세히 분석해드리겠습니다. 성분을 보면 히알루론산과 나이아신아마이드가 함유되어 있어 보습과 미백에 효과적입니다.",
      "올바른 스킨케어 루틴을 추천드리겠습니다. 클렌징 → 토너 → 에센스 → 크림 순서로 진행하시면 됩니다.",
      "계절별 뷰티 팁을 말씀드리면, 겨울철에는 보습에 더욱 신경 쓰시고, 여름철에는 자외선 차단이 핵심입니다.",
    ],
    "3": [
      // 피트니스 코치 AI
      "안녕하세요! 운동에 대한 열정이 느껴지네요! 💪 목표 달성을 위해 함께 노력해봐요!",
      "정말 좋은 질문이에요! 운동은 꾸준함이 가장 중요해요. 매일 조금씩이라도 움직이는 습관을 만들어보세요!",
      "운동 전 워밍업은 필수예요! 부상 예방과 운동 효과를 높이는 데 정말 중요하답니다. 화이팅! 🔥",
      "식단 관리도 운동만큼 중요해요! 단백질 섭취를 늘리고 충분한 수분 섭취를 잊지 마세요. 여러분 모두 할 수 있어요!",
    ],
  }

  const responses = responseMap[modelId] || ["죄송합니다. 응답을 생성할 수 없습니다."]
  return responses[Math.floor(Math.random() * responses.length)]
}

export default function TestModelPage() {
  const [selectedModels, setSelectedModels] = useState<string[]>([])
  const [message, setMessage] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([])
  const [availableModels, setAvailableModels] = useState<AIInfluencer[]>([])
  const [modelsLoading, setModelsLoading] = useState(true)

  const handleModelToggle = (modelId: string) => {
    setSelectedModels((prev) => (prev.includes(modelId) ? prev.filter((id) => id !== modelId) : [...prev, modelId]))
  }

  const handleSendMessage = async () => {
    if (!message.trim() || selectedModels.length === 0) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: "user",
      content: message,
      timestamp: new Date().toLocaleTimeString(),
    }

    setChatHistory((prev) => [...prev, userMessage])
    setMessage("")
    setIsLoading(true)

    // 각 선택된 모델에 대해 응답 생성
    setTimeout(() => {
      const aiMessages: ChatMessage[] = selectedModels.map((modelId, index) => {
        const model = availableModels.find((m) => m.influencer_id === modelId)
        const response = getModelResponses(modelId, userMessage.content)

        return {
          id: (Date.now() + index + 1).toString(),
          type: "ai" as const,
          content: response,
          timestamp: new Date().toLocaleTimeString(),
          modelId,
          modelName: model?.influencer_name || "Unknown Model",
        }
      })

      setChatHistory((prev) => [...prev, ...aiMessages])
      setIsLoading(false)
    }, 1500)
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  // 모델 데이터 로드
  useEffect(() => {
    const fetchModels = async () => {
      try {
        setModelsLoading(true)
        const data = await ModelService.getInfluencers()
        console.log('Fetched models:', data) // 디버깅용 로그
        setAvailableModels(data)
      } catch (error) {
        console.error('Failed to fetch models:', error)
      } finally {
        setModelsLoading(false)
      }
    }

    fetchModels()
  }, [])

  const selectedModelData = availableModels.filter((model) => selectedModels.includes(model.influencer_id))

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">AI 인플루언서 테스트</h1>
          <p className="text-gray-600 mt-2">여러 AI 인플루언서와 동시에 대화하고 응답을 비교해보세요</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 모델 선택 및 정보 */}
          <div className="lg:col-span-1">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Bot className="h-5 w-5" />
                  <span>인플루언서 선택</span>
                </CardTitle>
                <CardDescription>테스트할 AI 인플루언서들을 선택하세요 (다중 선택 가능)</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {modelsLoading ? (
                  <div className="text-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto"></div>
                    <p className="text-sm text-gray-600 mt-2">인플루언서를 불러오는 중...</p>
                  </div>
                ) : (
                <div className="space-y-3">
                  {availableModels.map((model) => {
                    const isAvailable = model.learning_status === 1
                    return (
                      <div 
                        key={model.influencer_id} 
                        className={`flex items-start space-x-3 p-3 border rounded-lg transition-colors ${
                          isAvailable 
                            ? 'hover:bg-gray-50 cursor-pointer' 
                            : 'opacity-50 bg-gray-100 cursor-not-allowed'
                        }`}
                        onClick={() => isAvailable && handleModelToggle(model.influencer_id)}
                      >
                        <Checkbox
                          id={model.influencer_id}
                          checked={selectedModels.includes(model.influencer_id)}
                          onCheckedChange={() => isAvailable && handleModelToggle(model.influencer_id)}
                          className="mt-1"
                          disabled={!isAvailable}
                        />
                        <div className="flex-1 min-w-0">
                          <Label 
                            htmlFor={model.influencer_id} 
                            className={`text-sm font-medium ${isAvailable ? 'cursor-pointer' : 'cursor-not-allowed'}`}
                          >
                            {model.influencer_name}
                          </Label>
                          <p className="text-xs text-gray-600 mt-1 truncate">
                            {model.influencer_description || 'AI 인플루언서'}
                          </p>
                          <div className="flex items-center space-x-2 mt-2">
                            <Badge className={isAvailable ? "bg-green-100 text-green-800 text-xs" : "bg-yellow-100 text-yellow-800 text-xs"}>
                              {isAvailable ? "사용 가능" : "생성 중"}
                            </Badge>
                            {!isAvailable && (
                              <span className="text-xs text-gray-500">선택 불가</span>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
                )}

                {selectedModelData.length > 0 && (
                  <div className="pt-4 border-t">
                    <h4 className="text-sm font-medium text-gray-700 mb-3">
                      선택된 인플루언서 ({selectedModelData.length}개)
                    </h4>
                    <div className="space-y-2">
                      {selectedModelData.map((model) => (
                        <div key={model.influencer_id} className="p-2 bg-blue-50 rounded text-xs">
                          <p className="font-medium text-blue-900">{model.influencer_name}</p>
                          <p className="text-blue-700 truncate">{model.influencer_description || 'AI 인플루언서'}</p>
                          <p className="text-blue-700">상태: {model.learning_status === 1 ? '사용 가능' : '생성 중'}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* 채팅 인터페이스 */}
          <div className="lg:col-span-2">
            <Card className="h-[600px] flex flex-col">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <MessageSquare className="h-5 w-5" />
                  <span>여러 인플루언서 대화 테스트</span>
                </CardTitle>
                <CardDescription>
                  {selectedModels.length > 0
                    ? `${selectedModels.length}개 모델과 대화 중`
                    : "모델을 선택하여 대화를 시작하세요"}
                </CardDescription>
              </CardHeader>

              {/* 채팅 메시지 영역 */}
              <CardContent className="flex-1 flex flex-col">
                <div className="flex-1 overflow-y-auto space-y-4 mb-4 p-4 bg-gray-50 rounded-lg">
                  {chatHistory.length === 0 ? (
                    <div className="text-center text-gray-500 py-8">
                      <MessageSquare className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                      <p>여러 AI 인플루언서와 대화를 시작해보세요!</p>
                      <p className="text-sm mt-2">각 인플루언서의 다른 응답 스타일을 비교할 수 있습니다.</p>
                    </div>
                  ) : (
                    chatHistory.map((msg) => (
                      <div key={msg.id} className={`flex ${msg.type === "user" ? "justify-end" : "justify-start"}`}>
                        <div
                          className={`max-w-[80%] rounded-lg px-4 py-2 ${
                            msg.type === "user" ? "bg-blue-600 text-white" : "bg-white border border-gray-200"
                          }`}
                        >
                          <div className="flex items-center space-x-2 mb-1">
                            {msg.type === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                            <span className="text-xs opacity-70">
                              {msg.type === "ai" && msg.modelName ? msg.modelName : "사용자"}
                            </span>
                            <span className="text-xs opacity-50">{msg.timestamp}</span>
                          </div>
                          <p className="text-sm">{msg.content}</p>
                        </div>
                      </div>
                    ))
                  )}

                  {isLoading && (
                    <div className="space-y-3">
                      {selectedModels.map((modelId) => {
                        const model = availableModels.find((m) => m.influencer_id === modelId)
                        return (
                          <div key={modelId} className="flex justify-start">
                            <div className="bg-white border border-gray-200 rounded-lg px-4 py-2">
                              <div className="flex items-center space-x-2">
                                <Bot className="h-4 w-4" />
                                <span className="text-xs text-gray-600">{model?.influencer_name}</span>
                                <div className="flex space-x-1">
                                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                                  <div
                                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                                    style={{ animationDelay: "0.1s" }}
                                  ></div>
                                  <div
                                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                                    style={{ animationDelay: "0.2s" }}
                                  ></div>
                                </div>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>

                {/* 메시지 입력 영역 */}
                <div className="flex space-x-2">
                  <Textarea
                    placeholder={
                      selectedModels.length > 0
                        ? `${selectedModels.length}명의 인플루언서에게 메시지를 보내세요...`
                        : "먼저 인플루언서를 선택하세요"
                    }
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    disabled={selectedModels.length === 0 || isLoading}
                    rows={2}
                    className="flex-1"
                  />
                  <Button
                    onClick={handleSendMessage}
                    disabled={!message.trim() || selectedModels.length === 0 || isLoading}
                    size="sm"
                    className="self-end"
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                </div>

                {selectedModels.length > 0 && (
                  <div className="mt-2 text-xs text-gray-500 text-center">
                    {selectedModels.length}명의 인플루언서가 각각 응답합니다
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
