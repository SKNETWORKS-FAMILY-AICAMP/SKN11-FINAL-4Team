"use client"

import type React from "react"

import { useState, useEffect, useRef } from "react"
import { Navigation } from "@/components/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { MessageSquare, Send, Bot, User, RotateCcw } from "lucide-react"
import type { AIModel } from "@/lib/types"
import { ModelService, type AIInfluencer, type MultiChatRequest, type MultiChatResponse } from "@/lib/services/model.service"

interface ChatMessage {
  id: string
  type: "user" | "ai"
  content: string
  timestamp: string
  modelId?: string
  modelName?: string
}

export default function TestModelPage() {
  const [selectedModels, setSelectedModels] = useState<string[]>([])
  const [message, setMessage] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([])
  const [availableModels, setAvailableModels] = useState<AIInfluencer[]>([])
  const [modelsLoading, setModelsLoading] = useState(true)
  const [maxModelWarning, setMaxModelWarning] = useState(false)
  const isFetchingRef = useRef(false)

  const handleModelToggle = (modelId: string) => {
    setSelectedModels((prev) => {
      if (prev.includes(modelId)) {
        setMaxModelWarning(false)
        return prev.filter((id) => id !== modelId)
      } else {
        if (prev.length >= 3) {
          return prev
        } else {
          return [...prev, modelId]
        }
      }
    })
    setMaxModelWarning((prevSelected) => {
      return selectedModels.length >= 2 && !selectedModels.includes(modelId)
    })
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

    try {
      const request: MultiChatRequest = {
        influencers: selectedModels.map((modelId) => {
          const model = availableModels.find((m) => m.influencer_id === modelId)
          return {
            influencer_id: modelId,
            influencer_model_repo: model?.influencer_model_repo || "",
          }
        }),
        message,
      }

      // 디버깅을 위한 로그 추가

      const data = await ModelService.multiChat(request)

      // 응답 로그 추가
      const aiMessages: ChatMessage[] = data.results.map((result, index) => ({
        id: (Date.now() + index + 1).toString(),
        type: "ai" as const,
        content: result.response,
        timestamp: new Date().toLocaleTimeString(),
        modelId: result.influencer_id,
        modelName: availableModels.find((m) => m.influencer_id === result.influencer_id)?.influencer_name || "Unknown Model",
      }))
      setChatHistory((prev) => [...prev, ...aiMessages])
    } catch (error) {
      console.error('Error sending message:', error)
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: "ai",
        content: "죄송합니다. 메시지 전송 중 오류가 발생했습니다. 다시 시도해주세요.",
        timestamp: new Date().toLocaleTimeString(),
        modelId: "error",
        modelName: "Error",
      }
      setChatHistory((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleClearChat = () => {
    setChatHistory([])
  }

  // 모델 데이터 로드 (GET /api/v1/influencers)
  useEffect(() => {
    const fetchModels = async () => {
      if (isFetchingRef.current) return
      
      try {
        isFetchingRef.current = true
        setModelsLoading(true)
        const data = await ModelService.getInfluencers()
        setAvailableModels(data)
      } catch (error) {
        console.error('Error fetching models:', error)
        setAvailableModels([])
      } finally {
        setModelsLoading(false)
        isFetchingRef.current = false
      }
    }
    fetchModels()
  }, [])

  const selectedModelData = availableModels.filter((model) => selectedModels.includes(model.influencer_id))

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">AI 인플루언서 테스트</h1>
          <p className="text-gray-600 mt-2">여러 AI 인플루언서와 동시에 대화하고 응답을 비교해보세요</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8" style={{ height: 'calc(100vh - 250px)' }}>
          {/* 모델 선택 및 정보 */}
          <div className="lg:col-span-1 h-full">
            <Card className="h-full flex flex-col overflow-hidden">
              <CardHeader className="flex-shrink-0">
                <CardTitle className="flex items-center space-x-2">
                  <img src="/favicon.ico" alt="AI Influencer" className="h-5 w-5" />
                  <span>AI 인플루언서 선택</span>
                </CardTitle>
                <CardDescription>테스트할 AI 인플루언서들을 선택하세요 (3개까지 선택 가능)</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 flex-1 flex flex-col min-h-0 overflow-hidden">
                {maxModelWarning && (
                  <div className="text-xs text-red-500 mb-2">최대 3개까지 선택할 수 있습니다.</div>
                )}
                {modelsLoading ? (
                  <div className="text-center py-8 flex-1 flex items-center justify-center">
                    <div>
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
                      <p className="text-sm text-gray-600 mt-2">인플루언서를 불러오는 중...</p>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="space-y-3 flex-1 overflow-y-auto pr-1 min-h-0">
                      {availableModels.filter(model => model.learning_status === 1).map((model) => (
                        <div
                          key={model.influencer_id}
                          className="flex items-start space-x-3 p-3 border rounded-lg transition-colors hover:bg-gray-50 cursor-pointer"
                          onClick={() => handleModelToggle(model.influencer_id)}
                        >
                          <Checkbox
                            id={model.influencer_id}
                            checked={selectedModels.includes(model.influencer_id)}
                            onCheckedChange={() => handleModelToggle(model.influencer_id)}
                            className="mt-1 data-[state=checked]:bg-blue-500 data-[state=checked]:border-blue-500"
                          />
                          <div className="flex-1 min-w-0">
                            <Label
                              htmlFor={model.influencer_id}
                              className="text-sm font-medium cursor-pointer"
                            >
                              {model.influencer_name}
                            </Label>
                            <p className="text-xs text-gray-600 mt-1 truncate">
                              {model.influencer_description || 'AI 인플루언서'}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          {/* 채팅 영역 */}
          <div className="lg:col-span-2 h-full">
            <Card className="h-full flex flex-col overflow-hidden">
              <CardHeader className="flex-shrink-0">
                <CardTitle className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <MessageSquare className="h-5 w-5" />
                    <span>AI 인플루언서 채팅 테스트</span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleClearChat}
                    disabled={chatHistory.length === 0}
                    className="flex items-center space-x-1"
                  >
                    <RotateCcw className="h-4 w-4" />
                    <span>초기화</span>
                  </Button>
                </CardTitle>
                <CardDescription>선택한 인플루언서들과 대화를 나눠보세요</CardDescription>
                {selectedModels.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {selectedModelData.map((model) => (
                      <Badge key={model.influencer_id} variant="default" className="text-xs bg-blue-500 hover:bg-blue-600">
                        {model.influencer_name}
                      </Badge>
                    ))}
                  </div>
                )}
              </CardHeader>
              <CardContent className="space-y-4 flex-1 flex flex-col min-h-0 overflow-hidden">
                <div className="space-y-4 flex-1 overflow-y-auto min-h-0 border rounded-lg p-4 bg-gray-50" style={{ maxHeight: 'calc(100vh - 450px)' }}>
                  {chatHistory.length === 0 ? (
                    <div className="text-center text-gray-500 py-8">
                      <MessageSquare className="h-12 w-12 mx-auto mb-2 text-gray-300" />
                      <p>대화를 시작해보세요!</p>
                    </div>
                  ) : (
                    <>
                      {chatHistory.map((msg) => (
                        <div key={msg.id} className={`flex ${msg.type === "user" ? "justify-end" : "justify-start"}`}>
                          <div className={`rounded-lg px-4 py-2 max-w-[70%] ${msg.type === "user" ? "bg-blue-500 text-white text-right" : "bg-white text-left border"}`}>
                            {msg.type === "ai" && (
                              <div className="mb-1 text-xs text-gray-500 font-semibold">
                                {msg.modelName || msg.modelId}
                              </div>
                            )}
                            <div>{msg.content}</div>
                            <div className="mt-1 text-[10px] text-gray-400 text-right">{msg.timestamp}</div>
                          </div>
                        </div>
                      ))}
                      {isLoading && (
                        <div className="text-center text-gray-400">
                          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500 mx-auto mb-2"></div>
                          AI 응답 생성 중... (환경에 따라 최대 5분 소요될 수 있습니다)
                        </div>
                      )}
                    </>
                  )}
                </div>
                <div className="flex-shrink-0 mt-4">
                  <div className="flex gap-2">
                    <Textarea
                      value={message}
                      onChange={e => setMessage(e.target.value)}
                      onKeyDown={handleKeyPress}
                      placeholder="메시지를 입력하세요"
                      rows={3}
                      disabled={isLoading}
                      className="flex-1 "
                    />
                    <Button
                      onClick={handleSendMessage}
                      disabled={isLoading || !message.trim() || selectedModels.length === 0}
                      className="self-end bg-blue-500 hover:bg-blue-600"
                    >
                      <Send className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
