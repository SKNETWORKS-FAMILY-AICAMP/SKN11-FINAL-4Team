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
      console.log('Sending request:', JSON.stringify(request, null, 2))
      
      const data = await ModelService.multiChat(request)
      
      // 응답 로그 추가
      console.log('Received response:', JSON.stringify(data, null, 2))
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

  // 모델 데이터 로드 (GET /api/v1/influencers)
  useEffect(() => {
    const fetchModels = async () => {
      try {
        setModelsLoading(true)
        const data = await ModelService.getInfluencers()
        setAvailableModels(data)
      } catch (error) {
        console.error('Error fetching models:', error)
        setAvailableModels([])
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
                <CardDescription>테스트할 AI 인플루언서들을 선택하세요 (3개까지 선택 가능)</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {maxModelWarning && (
                  <div className="text-xs text-red-500 mb-2">최대 3개까지 선택할 수 있습니다.</div>
                )}
                {modelsLoading ? (
                  <div className="text-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto"></div>
                    <p className="text-sm text-gray-600 mt-2">인플루언서를 불러오는 중...</p>
                  </div>
                ) : (
                  <>
                    <div className="space-y-3 max-h-[700px] overflow-y-auto pr-1">
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
                            className="mt-1"
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
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <MessageSquare className="h-5 w-5" />
                  <span>AI 챗</span>
                </CardTitle>
                <CardDescription>선택한 인플루언서들과 대화를 나눠보세요</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="mb-4">
                  <Textarea
                    value={message}
                    onChange={e => setMessage(e.target.value)}
                    onKeyDown={handleKeyPress}
                    placeholder="메시지를 입력하세요"
                    rows={3}
                    disabled={isLoading}
                  />
                  <div className="flex justify-end mt-2">
                    <Button onClick={handleSendMessage} disabled={isLoading || !message.trim() || selectedModels.length === 0}>
                      <Send className="h-4 w-4 mr-2" /> 전송
                    </Button>
                  </div>
                </div>
                <div className="space-y-4 max-h-[500px] overflow-y-auto">
                  {chatHistory.map((msg) => (
                    <div key={msg.id} className={`flex ${msg.type === "user" ? "justify-end" : "justify-start"}`}>
                      <div className={`rounded-lg px-4 py-2 max-w-[70%] ${msg.type === "user" ? "bg-blue-100 text-right" : "bg-gray-100 text-left"}`}>
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
                    <div className="text-center text-gray-400">AI 응답 생성 중...</div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
