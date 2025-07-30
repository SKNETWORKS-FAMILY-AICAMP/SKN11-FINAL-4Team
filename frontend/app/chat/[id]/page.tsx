"use client"

import { useState, useEffect, useRef } from "react"
import { useParams, useSearchParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent } from "@/components/ui/card"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { tokenUtils } from "@/lib/auth"
import { ModelService } from "@/lib/services/model.service"
import MCPService, { MCPChatResponse } from '@/lib/services/mcp.service'
import { RAGService, RAGChatRequest } from '@/lib/services/rag.service'
import { useAuth } from "@/hooks/use-auth"

import {
  Send,
  Loader2,
  AlertCircle,
  CheckCircle,
  XCircle,
  ChevronUp,
  ChevronDown,
  MessageSquare,
  User,
  Bot,
} from "lucide-react"

interface Message {
  id: string
  content: string
  sender: "user" | "bot"
  timestamp: Date
  isStreaming?: boolean // 스트리밍 중인 메시지를 위한 속성
}

interface ChatModel {
  id: string
  name: string
  description: string
  learning_status: number
  chatbot_option: boolean
  influencer_model_repo: string // 백엔드에서 자동으로 설정됨
  group_id: string
  image_url?: string // 인플루언서 이미지 URL
}

export default function ChatPage() {
  const params = useParams()
  const searchParams = useSearchParams()
  const router = useRouter()
  const { user, isAuthenticated, isLoading: authLoading, logout } = useAuth()
  const [model, setModel] = useState<ChatModel | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [inputMessage, setInputMessage] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isModelLoading, setIsModelLoading] = useState(true)
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting')
  const [isDescriptionExpanded, setIsDescriptionExpanded] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  // 인증 상태 확인
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [authLoading, isAuthenticated, router])

  // 모델 데이터 로드
  const loadModelData = async () => {
    if (!isAuthenticated) return
    
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
        group_id: String(data.group_id || ''),
        image_url: data.image_url || undefined, // 올바른 필드명 사용
      })
    } catch (error: any) {
      console.error("Error loading model data:", error)
      
      // 토큰 검증 실패로 인한 401/403 에러 시 로그아웃
      if (error?.status === 401 || error?.status === 403) {
        console.log("토큰 검증 실패로 인한 로그아웃 처리")
        await logout()
        router.push('/login')
        return
      }
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

    // influencer_id를 base64로 인코딩 (model_repo 대신 influencer_id 사용)
    const influencerIdEncoded = btoa(model.id);

    const ws = new WebSocket(
      `${apiBaseUrl}/api/v1/chatbot/chatbot/${influencerIdEncoded}?group_id=${model.group_id}&influencer_id=${model.id}&token=${accessToken}`
    );
    wsRef.current = ws;

    ws.onopen = () => {
      // console.log("WebSocket 연결 성공");
      setConnectionStatus('connected');
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

        if (data.type === "token") {
          // 스트리밍 토큰 처리
          setMessages(prev => {
            const newMessages = [...prev];
            const lastMessage = newMessages[newMessages.length - 1];

            if (lastMessage && lastMessage.sender === "bot" && lastMessage.isStreaming) {
              // 기존 스트리밍 메시지에 토큰 추가 (중복 제거)
              const newContent = data.content;
              const currentContent = lastMessage.content;

              // 중복 제거: 새로운 토큰이 기존 내용의 끝과 중복되지 않는지 확인
              if (!currentContent.endsWith(newContent)) {
                lastMessage.content += newContent;
              }
            } else {
              // 새로운 스트리밍 메시지 생성
              newMessages.push({
                id: Date.now().toString(),
                content: data.content,
                sender: "bot",
                timestamp: new Date(),
                isStreaming: true
              });
            }

            return newMessages;
          });
        } else if (data.type === "complete") {
          // 스트리밍 완료
          setIsLoading(false);
          setMessages(prev => {
            const newMessages = [...prev];
            const lastMessage = newMessages[newMessages.length - 1];
            if (lastMessage && lastMessage.isStreaming) {
              lastMessage.isStreaming = false;
            }
            return newMessages;
          });
        } else if (data.type === "error") {
          // 에러 처리
          setIsLoading(false);
          setMessages(prev => [...prev, {
            id: Date.now().toString(),
            content: `오류: ${data.message || '알 수 없는 오류가 발생했습니다.'}`,
            sender: "bot",
            timestamp: new Date(),
          }]);
        } else if (data.error_code) {
          // 기존 에러 응답 처리 (하위 호환성)
          setIsLoading(false);
          
          // 토큰 관련 오류 시 로그아웃 처리
          if (data.error_code === "INVALID_TOKEN" || data.error_code === "TOKEN_VERIFICATION_FAILED") {
            console.log("WebSocket 토큰 검증 실패로 인한 로그아웃 처리")
            await logout()
            router.push('/login')
            return
          }
          
          setMessages(prev => [...prev, {
            id: Date.now().toString(),
            content: `오류: ${data.message || '알 수 없는 오류가 발생했습니다.'}`,
            sender: "bot",
            timestamp: new Date(),
          }]);
        } else if (data.type === "history") {
          // 히스토리 응답 처리 - 백그라운드에서만 관리
          console.log("✅ 히스토리 로드 성공:", data.data);
        } else if (data.type === "history_cleared") {
          // 히스토리 초기화 응답 처리 - 백그라운드에서만 관리
          console.log("✅ 히스토리 초기화 성공");
        } else {
          // 기존 일반 응답 처리 (하위 호환성)
          setIsLoading(false);
          setMessages(prev => [...prev, {
            id: Date.now().toString(),
            content: event.data,
            sender: "bot",
            timestamp: new Date(),
          }]);
        }
      } catch (e) {
        // JSON 파싱 실패 시 일반 텍스트로 처리 (하위 호환성)
        setIsLoading(false);
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
      // console.log("WebSocket 연결 종료");
      setConnectionStatus('disconnected');
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [model]);

  // 메시지 전송
  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputMessage,
      sender: "user",
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    const currentMessage = inputMessage;
    setInputMessage("");
    setIsLoading(true);

    try {
      // 1단계: RAG 분기처리 (문서 검색)
      let ragResult: string | null = null;
      try {
        const ragRequest: RAGChatRequest = {
          message: currentMessage,  // query를 message로 변경
          include_sources: true
        };
        
        const ragResponse = await RAGService.chat(ragRequest);
        if (ragResponse && ragResponse.response && ragResponse.response.trim()) {
          ragResult = ragResponse.response.trim();
          console.log("✅ RAG 처리 성공:", ragResult.substring(0, 100) + "...");
        } else {
          console.log("❌ RAG 처리 실패 또는 문서 없음, MCP로 전환");
        }
      } catch (error: any) {
        console.log("❌ RAG 처리 중 오류:", error.message);
        
        // 토큰 검증 실패로 인한 401/403 에러 시 로그아웃
        if (error?.status === 401 || error?.status === 403) {
          console.log("RAG 서비스 토큰 검증 실패로 인한 로그아웃 처리")
          await logout()
          router.push('/login')
          return
        }
        // RAG 오류는 MCP로 fallback
      }

      // 2단계: RAG 결과가 있으면 SLLM으로 자연스러운 답변 생성
      if (ragResult && connectionStatus === 'connected' && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        try {
          const prompt = `사용자 질문: ${currentMessage}\n참고 문서 내용: ${ragResult}\n위 문서 내용을 바탕으로 답변해 주세요.`;
          wsRef.current.send(prompt);
          
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
          return;
        } catch (error) {
          console.error("RAG 결과 처리 중 오류:", error);
          // RAG 결과 처리 실패 시 MCP로 fallback
        }
      }

      // 3단계: MCP 분기처리 (도구 사용)
      let mcpResult: string | null = null;
      try {
        const mcpResponse: MCPChatResponse = await MCPService.processMessage({ 
          message: currentMessage, 
          influencer_id: model?.id || '' 
        });
        if (mcpResponse && mcpResponse.response && mcpResponse.response.trim()) {
          mcpResult = mcpResponse.response.trim();
          console.log("✅ MCP 처리 성공:", mcpResult.substring(0, 100) + "...");
        } else {
          console.log("❌ MCP 처리 실패 또는 도구 불필요, SLLM으로 전환");
        }
      } catch (error: any) {
        console.log("❌ MCP 처리 중 오류:", error.message);
        
        // 토큰 검증 실패로 인한 401/403 에러 시 로그아웃
        if (error?.status === 401 || error?.status === 403) {
          console.log("MCP 서비스 토큰 검증 실패로 인한 로그아웃 처리")
          await logout()
          router.push('/login')
          return
        }
        // MCP 오류는 SLLM으로 fallback
      }

      // 4단계: MCP 결과가 있으면 SLLM으로 자연스러운 답변 생성
      if (mcpResult && connectionStatus === 'connected' && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        try {
          const prompt = `사용자 질문: ${currentMessage}\n도구 결과: ${mcpResult}\n위 정보를 바탕으로 답변해 주세요.`;
          wsRef.current.send(prompt);
          
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
          return;
        } catch (error) {
          console.error("MCP 결과 처리 중 오류:", error);
          // MCP 결과 처리 실패 시 SLLM으로 fallback
        }
      }

      // 5단계: SLLM fallback (일반 대화)
      if (connectionStatus === 'connected' && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        try {
          wsRef.current.send(currentMessage);
          
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
        } catch (error) {
          console.error("SLLM 처리 중 오류:", error);
          setIsLoading(false);
          setMessages(prev => [...prev, {
            id: (Date.now() + 1).toString(),
            content: "메시지 전송에 실패했습니다. 다시 시도해주세요.",
            sender: "bot",
            timestamp: new Date(),
          }]);
        }
        return;
      }

      // 6단계: WebSocket 연결 불가
      setIsLoading(false);
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        content: "서버와의 연결이 끊어졌습니다. 재연결 버튼을 눌러주세요.",
        sender: "bot",
        timestamp: new Date(),
      }]);

    } catch (error) {
      console.error("메시지 처리 중 오류:", error);
      setIsLoading(false);
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        content: "메시지 처리 중 오류가 발생했습니다. 다시 시도해주세요.",
        sender: "bot",
        timestamp: new Date(),
      }]);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    if (isAuthenticated) {
      loadModelData()
    }
  }, [params.id, isAuthenticated])

  // 인증 상태 로딩 중
  if (authLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex justify-center items-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
          <span>인증 확인 중...</span>
        </div>
      </div>
    )
  }

  // 인증되지 않은 사용자
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex justify-center items-center">
        <div className="text-center">
          <p className="text-red-500 text-lg">로그인이 필요합니다.</p>
        </div>
      </div>
    )
  }

  // 로딩 상태 렌더링
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

  // 모델이 없는 경우 렌더링
  if (!model) {
    return (
      <div className="min-h-screen bg-gray-50 flex justify-center items-center">
        <div className="text-center">
          <p className="text-red-500 text-lg">모델을 찾을 수 없습니다.</p>
        </div>
      </div>
    )
  }

  // 모델 학습 상태 체크
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

  // 메인 채팅 UI 렌더링
  return (
    <div className="h-screen bg-gray-50">
      <div className="h-full flex flex-col p-4 max-w-3xl mx-auto">

        {/* 채팅 영역 */}
        <Card className="flex-1 flex flex-col min-h-0">
          <CardContent className="flex-1 flex flex-col p-0 h-full">
            {/* 인플루언서 정보 헤더 */}
            <div className="border-b p-4 bg-gray-50 flex-shrink-0">
              <div className="flex items-center justify-between min-w-0">
                <div className="flex items-center space-x-3 min-w-0 flex-1">
                  <Avatar className="h-10 w-10 flex-shrink-0">
                    {model.image_url ? (
                      <AvatarImage src={model.image_url} alt={model.name} />
                    ) : (
                      <AvatarFallback 
                        className={`text-white font-semibold ${
                          model.name.length % 4 === 0 ? 'bg-gradient-to-br from-purple-500 to-pink-500' :
                          model.name.length % 4 === 1 ? 'bg-gradient-to-br from-blue-500 to-cyan-500' :
                          model.name.length % 4 === 2 ? 'bg-gradient-to-br from-green-500 to-emerald-500' :
                          'bg-gradient-to-br from-orange-500 to-red-500'
                        }`}
                      >
                        {model.name.charAt(0).toUpperCase()}
                      </AvatarFallback>
                    )}
                  </Avatar>
                  <div className="min-w-0 flex-1">
                    <h3 className="font-semibold text-gray-900 truncate">{model.name}</h3>
                    {model.description && (
                      <div className="flex items-center space-x-1">
                        <p className={`text-sm text-gray-600 ${isDescriptionExpanded ? '' : 'truncate'}`}>
                          {model.description}
                        </p>
                        {model.description.length > 50 && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setIsDescriptionExpanded(!isDescriptionExpanded)}
                            className="h-4 w-4 p-0 flex-shrink-0"
                          >
                            {isDescriptionExpanded ? (
                              <ChevronUp className="h-3 w-3" />
                            ) : (
                              <ChevronDown className="h-3 w-3" />
                            )}
                          </Button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center space-x-2 flex-shrink-0 ml-4">
                  {/* 연결 상태 표시 */}
                  <div className="flex items-center space-x-2">
                    <div className={`w-2 h-2 rounded-full ${
                      connectionStatus === 'connected' ? 'bg-green-500' :
                      connectionStatus === 'connecting' ? 'bg-yellow-500' :
                      connectionStatus === 'error' ? 'bg-red-500' : 'bg-gray-400'
                    }`} />
                    <span className="text-xs text-gray-500">
                      {connectionStatus === 'connected' ? '연결됨' :
                       connectionStatus === 'connecting' ? '연결 중' :
                       connectionStatus === 'error' ? '오류' : '연결 끊김'}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* 메시지 영역 */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${
                    message.sender === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[70%] rounded-lg px-4 py-2 ${
                      message.sender === "user"
                        ? "bg-blue-500 text-white"
                        : "bg-gray-100 text-gray-900"
                    }`}
                  >
                    <div className="flex items-start space-x-2">
                      <Avatar className="h-6 w-6 flex-shrink-0">
                        <AvatarFallback className={`text-xs ${
                          message.sender === "user" ? "bg-blue-600 text-white" : "bg-gray-200 text-gray-700"
                        }`}>
                          {message.sender === "user" ? <User className="h-3 w-3" /> : <Bot className="h-3 w-3" />}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1">
                        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                        {message.isStreaming && (
                          <div className="flex items-center mt-1">
                            <Loader2 className="h-3 w-3 animate-spin mr-1" />
                            <span className="text-xs text-gray-500">생성 중...</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* 입력 영역 */}
            <div className="border-t p-4 flex-shrink-0">
              {connectionStatus !== 'connected' ? (
                <div className="text-center py-4">
                  <p className="text-gray-500 text-sm">
                    {connectionStatus === 'connecting' ? '서버에 연결 중입니다...' :
                      connectionStatus === 'error' ? '연결에 실패했습니다.' :
                        '연결이 끊어졌습니다.'}
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