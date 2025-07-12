"use client"

import { useState, useEffect, useRef } from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent } from "@/components/ui/card"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { tokenUtils } from "@/lib/auth"
import { ModelService } from "@/lib/services/model.service"
import {
  Send,
  Bot,
  User,
  MessageSquare,
  Loader2,
} from "lucide-react"

interface Message {
  id: string
  content: string
  sender: "user" | "bot"
  timestamp: Date
}

interface ChatModel {
  id: string
  name: string
  description: string
  learning_status: number
  chatbot_option: boolean
  influencer_model_repo: string
  group_id: string
}

export default function ChatPage() {
  const params = useParams()
  const [model, setModel] = useState<ChatModel | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [inputMessage, setInputMessage] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isModelLoading, setIsModelLoading] = useState(true)
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  // 모델 데이터 로드
  const loadModelData = async () => {
    setIsModelLoading(true)
    try {
      const data = await ModelService.getInfluencer(params.id as string)
      setModel({
        id: data.influencer_id,
        name: data.influencer_name,
        description: data.influencer_description || '',
        learning_status: data.learning_status,
        chatbot_option: data.chatbot_option,
        influencer_model_repo: data.influencer_model_repo || '',
        group_id: String(data.group_id || '')
      })
    } catch (error) {
      console.error("Error loading model data:", error)
    } finally {
      setIsModelLoading(false)
    }
  }

  // WebSocket 연결 관리
  useEffect(() => {
    if (!model) return;
    if (!model.id) return;
    
    const accessToken = tokenUtils.getToken();
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'ws://localhost:8000';
    
    // lora_repo를 base64로 인코딩
    const loraRepoEncoded = btoa(model.influencer_model_repo);
    
    const ws = new WebSocket(
      `${apiBaseUrl}/api/v1/chatbot/chatbot/${loraRepoEncoded}?group_id=${model.group_id}&influencer_id=${model.id}&token=${accessToken}`
    );
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("WebSocket 연결 성공");
      setConnectionStatus('connected');
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        content: "안녕하세요! 저는 " + model.name + "입니다. 무엇을 도와드릴까요?",
        sender: "bot",
        timestamp: new Date(),
      }]);
    };

    ws.onmessage = (event) => {
      // 타임아웃 해제
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      
      setIsLoading(false); // 응답 수신 시 로딩 상태 해제
      try {
        const data = JSON.parse(event.data);
        if (data.error_code) {
          // 에러 응답 처리
          setMessages(prev => [...prev, {
            id: Date.now().toString(),
            content: `오류: ${data.message || '알 수 없는 오류가 발생했습니다.'}`,
            sender: "bot",
            timestamp: new Date(),
          }]);
        } else {
          // 정상 응답 처리
          setMessages(prev => [...prev, {
            id: Date.now().toString(),
            content: event.data,
            sender: "bot",
            timestamp: new Date(),
          }]);
        }
      } catch (e) {
        // JSON 파싱 실패 시 일반 텍스트로 처리
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          content: event.data,
          sender: "bot",
          timestamp: new Date(),
        }]);
      }
    };

    ws.onerror = (e) => {
      console.error("WebSocket 에러:", e);
      setConnectionStatus('error');
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        content: "서버와의 연결에 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
        sender: "bot",
        timestamp: new Date(),
      }]);
    };

    ws.onclose = () => {
      console.log("WebSocket 연결 종료");
      setConnectionStatus('disconnected');
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [model]);

  // 재연결 함수
  const reconnect = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    setConnectionStatus('connecting');
    // useEffect가 다시 실행되어 새로운 연결을 시도합니다
  };

  // 메시지 전송
  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading || connectionStatus !== 'connected') return;
    
    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputMessage,
      sender: "user",
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    setInputMessage("");
    setIsLoading(true);
    
    // 타임아웃 설정 (30초)
    timeoutRef.current = setTimeout(() => {
      setIsLoading(false);
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        content: "응답 시간이 초과되었습니다. 다시 시도해주세요.",
        sender: "bot",
        timestamp: new Date(),
      }]);
    }, 30000);
    
    try {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(inputMessage);
      } else {
        clearTimeout(timeoutRef.current);
        setConnectionStatus('disconnected');
        setMessages(prev => [...prev, {
          id: (Date.now() + 1).toString(),
          content: "서버와의 연결이 끊어졌습니다. 재연결 버튼을 눌러주세요.",
          sender: "bot",
          timestamp: new Date(),
        }]);
        setIsLoading(false);
      }
    } catch (error) {
      clearTimeout(timeoutRef.current);
      console.error("메시지 전송 오류:", error);
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        content: "메시지 전송 중 오류가 발생했습니다. 다시 시도해주세요.",
        sender: "bot",
        timestamp: new Date(),
      }]);
      setIsLoading(false);
    }
  };

  // Enter 키로 메시지 전송, Shift+Enter로 줄바꿈
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (connectionStatus === 'connected' && !isLoading) {
        sendMessage()
      }
    }
  }

  // 스크롤을 맨 아래로 이동
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    loadModelData()
  }, [params.id])

  if (isModelLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex justify-center items-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
          <span>모델 정보를 불러오는 중...</span>
        </div>
      </div>
    )
  }

  if (!model) {
    return (
      <div className="min-h-screen bg-gray-50 flex justify-center items-center">
        <div className="text-center">
          <p className="text-red-500 text-lg">모델을 찾을 수 없습니다.</p>
        </div>
      </div>
    )
  }

  if (model.learning_status !== 1) {
    return (
      <div className="min-h-screen bg-gray-50 flex justify-center items-center">
        <div className="text-center">
          <p className="text-yellow-600 text-lg">
            {model.learning_status === 0 ? "모델이 아직 생성 중입니다." : "모델에 오류가 발생했습니다."}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen bg-gray-50">
      <div className="h-full flex flex-col p-4 max-w-3xl mx-auto">

        {/* 채팅 영역 */}
        <Card className="flex-1 flex flex-col min-h-0">
          <CardContent className="flex-1 flex flex-col p-0 h-full">
            {/* 인플루언서 정보 헤더 */}
            <div className="border-b p-4 bg-gray-50 flex-shrink-0">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <Avatar className="h-10 w-10">
                    <AvatarFallback className="bg-green-500 text-white">
                      <Bot className="h-5 w-5" />
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <h3 className="font-semibold text-gray-900">{model.name}</h3>
                    <p className="text-sm text-gray-600">{model.description}</p>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  {/* 연결 상태 표시 */}
                  <div className="flex items-center space-x-1">
                    <div className={`w-2 h-2 rounded-full ${
                      connectionStatus === 'connected' ? 'bg-green-500' :
                      connectionStatus === 'connecting' ? 'bg-yellow-500' :
                      connectionStatus === 'error' ? 'bg-red-500' : 'bg-gray-400'
                    }`} />
                    <span className="text-xs text-gray-600">
                      {connectionStatus === 'connected' ? '연결됨' :
                       connectionStatus === 'connecting' ? '연결 중' :
                       connectionStatus === 'error' ? '연결 오류' : '연결 끊김'}
                    </span>
                  </div>
                  {/* 재연결 버튼 */}
                  {connectionStatus !== 'connected' && (
                    <Button
                      onClick={reconnect}
                      size="sm"
                      variant="outline"
                      disabled={connectionStatus === 'connecting'}
                    >
                      {connectionStatus === 'connecting' ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        '재연결'
                      )}
                    </Button>
                  )}
                </div>
              </div>
            </div>
            
            {/* 메시지 영역 */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4 min-h-0">
              {messages.length === 0 ? (
                <div className="text-center py-12">
                  <MessageSquare className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                  <p className="text-gray-500 text-lg">대화를 시작해보세요!</p>
                  <p className="text-gray-400 mt-2">AI 인플루언서와 자유롭게 대화할 수 있습니다.</p>
                </div>
              ) : (
                messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex ${message.sender === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div className={`flex items-start space-x-3 max-w-[70%] ${message.sender === "user" ? "flex-row-reverse space-x-reverse" : ""}`}>
                      <Avatar className="h-8 w-8">
                        <AvatarFallback className={message.sender === "user" ? "bg-blue-500 text-white" : "bg-green-500 text-white"}>
                          {message.sender === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                        </AvatarFallback>
                      </Avatar>
                      <div className={`rounded-lg px-4 py-2 ${
                        message.sender === "user" 
                          ? "bg-blue-500 text-white" 
                          : "bg-gray-100 text-gray-900"
                      }`}>
                        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                        <p className={`text-xs mt-1 ${
                          message.sender === "user" ? "text-blue-100" : "text-gray-500"
                        }`}>
                          {message.timestamp.toLocaleTimeString('ko-KR', { 
                            hour: '2-digit', 
                            minute: '2-digit' 
                          })}
                        </p>
                      </div>
                    </div>
                  </div>
                ))
              )}
              
              {isLoading && (
                <div className="flex justify-start">
                  <div className="flex items-start space-x-3 max-w-[70%]">
                    <Avatar className="h-8 w-8">
                      <AvatarFallback className="bg-green-500 text-white">
                        <Bot className="h-4 w-4" />
                      </AvatarFallback>
                    </Avatar>
                    <div className="bg-gray-100 rounded-lg px-4 py-2">
                      <div className="flex items-center space-x-2">
                        <Loader2 className="h-4 w-4 animate-spin text-gray-500" />
                        <span className="text-sm text-gray-500">답변을 생성하고 있습니다...</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>

            {/* 입력 영역 */}
            <div className="border-t p-4 flex-shrink-0">
              {connectionStatus !== 'connected' ? (
                <div className="text-center py-4">
                  <p className="text-gray-500 text-sm">
                    {connectionStatus === 'connecting' ? '서버에 연결 중입니다...' :
                     connectionStatus === 'error' ? '연결에 실패했습니다. 재연결 버튼을 눌러주세요.' :
                     '연결이 끊어졌습니다. 재연결 버튼을 눌러주세요.'}
                  </p>
                </div>
              ) : (
                <>
                  <div className="flex space-x-2">
                    <Textarea
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={handleKeyPress}
                      placeholder={
                        connectionStatus === 'connected' ? "메시지를 입력하세요..." :
                        connectionStatus === 'connecting' ? "연결 중입니다..." :
                        "연결이 필요합니다..."
                      }
                      className="flex-1 resize-none"
                      rows={1}
                      disabled={isLoading || connectionStatus !== 'connected'}
                    />
                    <Button 
                      onClick={sendMessage} 
                      disabled={!inputMessage.trim() || isLoading || connectionStatus !== 'connected'}
                      size="sm"
                      className="self-end"
                    >
                      <Send className="h-4 w-4" />
                    </Button>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">
                    Enter로 전송, Shift+Enter로 줄바꿈
                  </p>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
} 