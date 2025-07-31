"use client"

import { useState, useEffect, useRef } from "react"
import { useParams, useSearchParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent } from "@/components/ui/card"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { tokenUtils } from "@/lib/auth"
import { useAuth } from "@/hooks/use-auth"
import { useTTS } from "@/hooks/use-tts"
import webSocketManager from "@/lib/websocket-manager"

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
  Volume2,
  VolumeX,
  Pause,
  Play,
} from "lucide-react"

interface Message {
  id: string
  content: string
  sender: "user" | "bot"
  timestamp: Date
  isStreaming?: boolean // 스트리밍 중인 메시지를 위한 속성
  audioData?: string // base64 오디오 데이터
  audioFormat?: string // 오디오 포맷 (mp3, wav 등)
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
  const { speak, stop, pause, resume, status: ttsStatus, isSupported: ttsSupported } = useTTS()
  const [model, setModel] = useState<ChatModel | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [inputMessage, setInputMessage] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isModelLoading, setIsModelLoading] = useState(true)
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting')
  const [isDescriptionExpanded, setIsDescriptionExpanded] = useState(false)
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null)
  const [currentAudio, setCurrentAudio] = useState<HTMLAudioElement | null>(null)
  const [isTTSEnabled, setIsTTSEnabled] = useState(true) // TTS 음소거 켜기/끄기
  const [playingMessageId, setPlayingMessageId] = useState<string | null>(null) // 현재 재생 중인 메시지 ID

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)
  const lastBotMessageIdRef = useRef<string | null>(null) // 마지막 봇 메시지 ID 추적

  // 인증 상태 확인
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [authLoading, isAuthenticated, router])

  // 모델 데이터 로드 (간소화 - influencer_id만 사용)
  const loadModelData = async () => {
    if (!isAuthenticated) return
    
    setIsModelLoading(true)
    try {
      // URL의 influencer_id를 직접 사용
      const influencerId = params.id as string
      console.log(`🔍 Influencer ID 사용: ${influencerId}`);
      
      // 기본 모델 정보 설정 (백엔드에서 필요한 정보는 WebSocket 연결 시 처리)
      setModel({
        id: influencerId,
        name: 'AI 인플루언서', // 기본 이름 (필요시 백엔드에서 받아올 수 있음)
        description: '',
        learning_status: 1, // 채팅 가능 상태로 가정
        chatbot_option: true,
        influencer_model_repo: '',
        group_id: '1', // 기본값 (백엔드에서 처리)
        image_url: undefined,
      })
      console.log('✅ 모델 정보 설정 완료');
    } finally {
      setIsModelLoading(false)
    }
  }

  // WebSocket 연결 관리
  useEffect(() => {
    if (!model || !model.id) return;

    const wsKey = `chat-${model.id}`;
    
    const connectWebSocket = async () => {
      // 이미 연결이 있는지 확인
      const existingWs = webSocketManager.getConnection(wsKey);
      if (existingWs) {
        console.log(`🔌 WebSocket 이미 연결되어 있음: ${wsKey}`);
        return;
      }

      // 이미 연결 시도 중인지 확인
      if (webSocketManager.isConnecting(wsKey)) {
        console.log(`🔌 WebSocket 이미 연결 시도 중: ${wsKey}`);
        return;
      }

      // 연결 시도 시작
      webSocketManager.setConnecting(wsKey, true);
      console.log(`🔌 WebSocket 연결 시작: ${wsKey}`);

    const accessToken = tokenUtils.getToken();
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
    
    // HTTP URL을 WebSocket URL로 변환 (이미지 생성 페이지와 동일한 방식)
    const wsProtocol = backendUrl.startsWith('https') ? 'wss:' : 'ws:';
    const wsHost = backendUrl.replace(/^https?:\/\//, '');
    const wsUrl = `${wsProtocol}//${wsHost}`;

    // influencer_id를 base64로 인코딩 (model_repo 대신 influencer_id 사용)
    const influencerIdEncoded = btoa(model.id);

    const wsFullUrl = `${wsUrl}/api/v1/chatbot/chatbot/${influencerIdEncoded}?influencer_id=${model.id}&token=${accessToken}`;
    
    console.log('🔌 WebSocket 연결 시도');
    console.log(`- Backend URL: ${backendUrl}`);
    console.log(`- WS URL: ${wsUrl}`);
    console.log(`- Full URL: ${wsFullUrl}`);
    console.log(`- Influencer ID: ${model.id}`);
    console.log(`- Influencer ID (encoded): ${influencerIdEncoded}`);
    console.log(`- Token 존재: ${accessToken ? 'Yes' : 'No'}`);
    console.log(`- Token 길이: ${accessToken?.length || 0}`);
    
    const ws = new WebSocket(wsFullUrl);
    webSocketManager.setConnection(wsKey, ws);

    ws.onopen = () => {
      console.log("WebSocket 연결 성공");
      console.log(`연결 URL: ${ws.url}`);
      console.log(`연결 상태: ${ws.readyState}`);
      setConnectionStatus('connected');
      webSocketManager.setConnecting(wsKey, false);
    };

    ws.onmessage = (event) => {
      console.log('📨 WebSocket 메시지 수신:', event.data);
      
      // 타임아웃 해제
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }

      setIsLoading(false); // 응답 수신 시 로딩 상태 해제
      try {
        const data = JSON.parse(event.data);
        console.log('📋 파싱된 메시지:', data);

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
              const newMessageId = Date.now().toString();
              newMessages.push({
                id: newMessageId,
                content: data.content,
                sender: "bot",
                timestamp: new Date(),
                isStreaming: true
              });
              // 마지막 봇 메시지 ID 저장
              lastBotMessageIdRef.current = newMessageId;
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
            logout()
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
        } else if (data.type === "audio") {
          // 음성 데이터 응답 처리 - 메시지에 저장
          console.log("🔊 음성 데이터 수신:", {
            hasBase64: !!data.audio_base64,
            hasUrl: !!data.audio_url,
            duration: data.duration,
            format: data.format,
            message: data.message,
            base64Length: data.audio_base64 ? data.audio_base64.length : 0
          });
          setIsLoading(false);
          
          // 마지막 봇 메시지에 오디오 데이터 추가
          if (data.audio_base64 && lastBotMessageIdRef.current) {
            setMessages(prev => {
              return prev.map(msg => {
                if (msg.id === lastBotMessageIdRef.current) {
                  return {
                    ...msg,
                    audioData: data.audio_base64,
                    audioFormat: data.format || 'mp3'
                  };
                }
                return msg;
              });
            });
            console.log("✅ 메시지에 TTS 음성 데이터 저장 완료");
          }
        } else if (data.type === "influencer_info") {
          // 인플루언서 정보 업데이트
          console.log("👤 인플루언서 정보 수신:", data.data);
          console.log("👤 이미지 URL:", data.data?.image_url);
          if (data.data) {
            setModel(prev => {
              if (!prev) return prev;
              const updatedModel = {
                ...prev,
                name: data.data.name || prev.name,
                description: data.data.description || prev.description,
                image_url: data.data.image_url || prev.image_url
              };
              console.log("👤 모델 업데이트 완료:", updatedModel);
              return updatedModel;
            });
          }
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
      console.error(`WebSocket 에러 상세:`);
      console.error(`- Type: ${e.type}`);
      console.error(`- Target: ${e.target}`);
      console.error(`- ReadyState: ${ws.readyState}`);
      console.error(`- URL: ${ws.url}`);
      console.error(`- Protocol: ${ws.protocol}`);
      console.error(`- Extensions: ${ws.extensions}`);
      console.error(`- Binary Type: ${ws.binaryType}`);
      console.error(`- Buffered Amount: ${ws.bufferedAmount}`);
      
      setConnectionStatus('error');
      webSocketManager.setConnecting(wsKey, false);
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        content: "서버와의 연결에 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
        sender: "bot",
        timestamp: new Date(),
      }]);
    };

    ws.onclose = (event) => {
      console.log("WebSocket 연결 종료");
      console.log(`- Code: ${event.code}`);
      console.log(`- Reason: ${event.reason}`);
      console.log(`- Was Clean: ${event.wasClean}`);
      console.log(`- ReadyState: ${ws.readyState}`);
      
      if (event.code === 1006) {
        console.error("비정상적인 연결 종료 - 서버가 연결을 거부했거나 네트워크 문제가 있습니다.");
      }
      
      setConnectionStatus('disconnected');
      webSocketManager.setConnecting(wsKey, false);
    };

    };

    connectWebSocket();

    return () => {
      console.log(`🔌 WebSocket cleanup 시작: ${wsKey}`);
      webSocketManager.closeConnection(wsKey);
      
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [model?.id]); // model 대신 model.id만 의존성으로 사용

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
      // WebSocket으로 메시지 전송 (백엔드에서 RAG, MCP 처리를 포함한 모든 로직 처리)
      const wsKey = `chat-${model?.id}`;
      const ws = webSocketManager.getConnection(wsKey);
      
      if (connectionStatus === 'connected' && ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(currentMessage);
          
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
          console.error("WebSocket 메시지 전송 중 오류:", error);
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

      // WebSocket 연결 불가
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

  // 메시지에 저장된 오디오 재생
  const playMessageAudio = (messageId: string, audioData: string, audioFormat: string) => {
    // 음소거 상태면 재생하지 않음
    if (!isTTSEnabled) {
      console.log("음소거 상태입니다.");
      return;
    }

    try {
      // 이전 오디오가 재생 중이면 정지
      if (currentAudio) {
        currentAudio.pause();
        currentAudio.src = '';
        setCurrentAudio(null);
        setPlayingMessageId(null);
      }

      // 같은 메시지를 다시 클릭하면 정지
      if (playingMessageId === messageId) {
        setPlayingMessageId(null);
        return;
      }

      // Base64를 Blob으로 변환
      const byteCharacters = atob(audioData);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: `audio/${audioFormat}` });
      
      // Blob URL 생성
      const audioUrl = URL.createObjectURL(blob);
      
      // Audio 객체 생성 및 재생
      const audio = new Audio(audioUrl);
      audio.volume = 0.8; // 볼륨 설정
      
      // 재생 완료 후 URL 정리
      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        setCurrentAudio(null);
        setPlayingMessageId(null);
      };

      // 에러 처리
      audio.onerror = () => {
        console.error("오디오 재생 오류");
        URL.revokeObjectURL(audioUrl);
        setCurrentAudio(null);
        setPlayingMessageId(null);
      };
      
      // 현재 오디오 저장
      setCurrentAudio(audio);
      setPlayingMessageId(messageId);
      
      // 재생
      audio.play().catch(err => {
        console.error("음성 재생 실패:", err);
        setCurrentAudio(null);
        setPlayingMessageId(null);
      });
      
    } catch (error) {
      console.error("음성 데이터 처리 중 오류:", error);
    }
  };

  // TTS 제어 함수들 (브라우저 TTS용)
  const handleSpeak = (messageId: string, text: string) => {
    if (!ttsSupported) {
      alert('이 브라우저는 음성 출력을 지원하지 않습니다.')
      return
    }

    // 이미 재생 중인 경우
    if (speakingMessageId === messageId) {
      if (ttsStatus === 'speaking') {
        pause()
      } else if (ttsStatus === 'paused') {
        resume()
      }
    } else {
      // 다른 메시지 재생
      stop()
      setSpeakingMessageId(messageId)
      speak(text)
    }
  }

  const handleStopSpeaking = () => {
    stop()
    setSpeakingMessageId(null)
  }

  // TTS 상태가 idle로 변경되면 speakingMessageId 초기화
  useEffect(() => {
    if (ttsStatus === 'idle') {
      setSpeakingMessageId(null)
    }
  }, [ttsStatus])

  useEffect(() => {
    if (isAuthenticated) {
      loadModelData()
    }
  }, [params.id, isAuthenticated])

  // 컴포넌트 언마운트 시 오디오 정리
  useEffect(() => {
    return () => {
      if (currentAudio) {
        currentAudio.pause();
        currentAudio.src = '';
      }
    };
  }, [currentAudio])

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
                      <>
                        {console.log("🖼️ Avatar 이미지 렌더링:", model.image_url)}
                        <AvatarImage src={model.image_url} alt={model.name} />
                      </>
                    ) : (
                      <>
                        {console.log("🖼️ Avatar 폴백 렌더링, image_url:", model.image_url)}
                        <AvatarFallback 
                            className={`text-white font-semibold ${model.name.length % 4 === 0 ? 'bg-gradient-to-br from-purple-500 to-pink-500' :
                            model.name.length % 4 === 1 ? 'bg-gradient-to-br from-blue-500 to-cyan-500' :
                            model.name.length % 4 === 2 ? 'bg-gradient-to-br from-green-500 to-emerald-500' :
                            'bg-gradient-to-br from-orange-500 to-red-500'
                          }`}
                        >
                          {model.name.charAt(0).toUpperCase()}
                        </AvatarFallback>
                      </>
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
                  {/* 음소거 토글 */}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setIsTTSEnabled(!isTTSEnabled);
                      // 음소거 시 현재 재생 중인 오디오 정지
                      if (isTTSEnabled && currentAudio) {
                        currentAudio.pause();
                        currentAudio.src = '';
                        setCurrentAudio(null);
                        setPlayingMessageId(null);
                      }
                    }}
                    className={`p-1 ${isTTSEnabled ? 'text-blue-600' : 'text-red-500'}`}
                    title={isTTSEnabled ? "음성 켜짐" : "음소거"}
                  >
                    {isTTSEnabled ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
                  </Button>
                  
                  {/* 현재 재생 중인 오디오 정지 버튼 */}
                  {currentAudio && playingMessageId && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        if (currentAudio) {
                          currentAudio.pause();
                          currentAudio.src = '';
                          setCurrentAudio(null);
                          setPlayingMessageId(null);
                        }
                      }}
                      className="p-1 text-red-500"
                      title="재생 정지"
                    >
                      <Pause className="h-4 w-4" />
                    </Button>
                  )}
                  
                  {/* 연결 상태 표시 */}
                  <div className="flex items-center space-x-2">
                    <div className={`w-2 h-2 rounded-full ${connectionStatus === 'connected' ? 'bg-green-500' :
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
                  className={`flex ${message.sender === "user" ? "justify-end" : "justify-start"
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
                      {/* TTS 버튼 - 봇 메시지에만 표시 */}
                      {message.sender === "bot" && !message.isStreaming && (
                        <>
                          {/* 서버에서 생성된 음성이 있는 경우 */}
                          {message.audioData && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => playMessageAudio(message.id, message.audioData!, message.audioFormat!)}
                              className={`ml-2 p-1 h-7 w-7 ${!isTTSEnabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                              disabled={!isTTSEnabled}
                              title={
                                !isTTSEnabled ? '음소거 상태입니다' :
                                playingMessageId === message.id ? '정지' : '재생'
                              }
                            >
                              {playingMessageId === message.id ? (
                                <Pause className="h-3.5 w-3.5" />
                              ) : (
                                <Play className="h-3.5 w-3.5" />
                              )}
                            </Button>
                          )}
                          {/* 브라우저 TTS 버튼 (서버 음성이 없는 경우) */}
                          {!message.audioData && ttsSupported && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleSpeak(message.id, message.content)}
                              className="ml-2 p-1 h-7 w-7"
                              title={
                                speakingMessageId === message.id && ttsStatus === 'speaking' ? '일시정지' :
                                speakingMessageId === message.id && ttsStatus === 'paused' ? '재개' :
                                '읽어주기'
                              }
                            >
                              {speakingMessageId === message.id ? (
                                ttsStatus === 'speaking' ? (
                                  <Pause className="h-3.5 w-3.5" />
                                ) : ttsStatus === 'paused' ? (
                                  <Play className="h-3.5 w-3.5" />
                                ) : (
                                  <Volume2 className="h-3.5 w-3.5" />
                                )
                              ) : (
                                <Volume2 className="h-3.5 w-3.5" />
                              )}
                            </Button>
                          )}
                        </>
                      )}
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
                      onKeyDown={handleKeyPress}
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