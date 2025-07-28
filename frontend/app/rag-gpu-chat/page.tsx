"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Send, Loader2, Zap } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { apiClient } from "@/lib/api";
import { VectorDBService } from "@/lib/services/vector-db.service";

interface Message {
  id: string;
  type: "user" | "assistant";
  content: string;
  timestamp: Date;
  sources?: Array<{
    text: string;
    score: number;
    type: string;
    chunk_id: string;
    metadata: any;
  }>;
}

interface VectorStats {
  stats: {
    total_chunks: number;
    embedding_dimension: number;
    device: string;
    tensor_shape: number[] | null;
  };
  health: {
    status: string;
    device: string;
    total_chunks: number;
    embedding_model_loaded: boolean;
  };
}

interface ChatResponse {
  response: string;
  sources: Array<{
    text: string;
    score: number;
    type?: string;
    chunk_id?: string;
    metadata?: any;
  }>;
  query: string;
  search_results: any[];
}



export default function RAGGPUChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const [vectorStats, setVectorStats] = useState<VectorStats | null>(null);
  const [topK, setTopK] = useState(5);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.5);
  const [maxTokens, setMaxTokens] = useState(2048);
  const [selectedModel, setSelectedModel] = useState("gpt-4");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // 페이지 로드 시 벡터 스토어 상태 확인
    checkVectorStats();
  }, []);

  const checkVectorStats = async () => {
    try {
      const response = await VectorDBService.getStats();
      setVectorStats(response as VectorStats);
    } catch (error) {
      console.error("벡터 스토어 상태 확인 실패:", error);
    }
  };



  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      // 백엔드의 chat_gpu API 호출
      const response = await apiClient.post<ChatResponse>('/api/v1/rag/chat_gpu', {
        query: input,
        top_k: topK,
        similarity_threshold: similarityThreshold,
        include_sources: true,
        max_tokens: maxTokens,
        model: selectedModel
      });

      // AI 응답 생성
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: "assistant",
        content: response.response,
        timestamp: new Date(),
        sources: response.sources.map((source) => ({
          text: source.text,
          score: source.score,
          type: source.type || "vector_search",
          chunk_id: source.chunk_id || "unknown",
          metadata: source.metadata || {}
        })),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error: any) {
      console.error("채팅 실패:", error);
      const errorMessage = error.response?.data?.detail || error.message || "메시지 전송에 실패했습니다.";
      toast({
        title: "오류",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const clearVectorStore = async () => {
    try {
      await VectorDBService.clearVectorDB();
      setMessages([]);
      toast({
        title: "성공",
        description: "벡터DB가 정리되었습니다.",
      });
      checkVectorStats();
    } catch (error) {
      console.error("벡터DB 정리 실패:", error);
      toast({
        title: "오류",
        description: "벡터DB 정리에 실패했습니다.",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="container mx-auto p-4 max-w-6xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">VLLM GPU 벡터 검색 + OpenAI RAG 챗봇</h1>
        <p className="text-muted-foreground">
          VLLM GPU 메모리 + OpenAI 답변 생성
        </p>
      </div>

      {/* 설정 패널 */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            GPU 벡터 검색 설정
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <Label htmlFor="topK">검색 결과 수 (Top-K)</Label>
              <Input
                id="topK"
                type="number"
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                min={1}
                max={20}
              />
            </div>
            <div>
              <Label htmlFor="similarityThreshold">유사도 임계값</Label>
              <Input
                id="similarityThreshold"
                type="number"
                step="0.1"
                value={similarityThreshold}
                onChange={(e) => setSimilarityThreshold(Number(e.target.value))}
                min={0}
                max={1}
              />
            </div>
            <div>
              <Label htmlFor="maxTokens">최대 토큰 수</Label>
              <Input
                id="maxTokens"
                type="number"
                value={maxTokens}
                onChange={(e) => setMaxTokens(Number(e.target.value))}
                min={512}
                max={4096}
                step={512}
              />
            </div>
            <div>
              <Label htmlFor="selectedModel">AI 모델</Label>
              <select
                id="selectedModel"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="gpt-4">GPT-4</option>
                <option value="gpt-4-turbo">GPT-4 Turbo</option>
                <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
              </select>
            </div>
            <div className="flex items-end">
              <Button
                onClick={clearVectorStore}
                variant="outline"
                className="w-full"
              >
                벡터 스토어 정리
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 벡터 스토어 상태 */}
      {vectorStats && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>벡터 스토어 상태</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <Label>상태</Label>
                <Badge variant={vectorStats.health.status === "healthy" ? "default" : "destructive"}>
                  {vectorStats.health.status}
                </Badge>
              </div>
              <div>
                <Label>디바이스</Label>
                <p className="text-sm">{vectorStats.health.device}</p>
              </div>
              <div>
                <Label>저장된 청크</Label>
                <p className="text-sm">{vectorStats.health.total_chunks}개</p>
              </div>
              <div>
                <Label>임베딩 차원</Label>
                <p className="text-sm">{vectorStats.stats.embedding_dimension}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}



      {/* 채팅 인터페이스 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 메시지 영역 */}
        <div className="lg:col-span-2">
          <Card className="h-[600px] flex flex-col">
            <CardHeader>
              <CardTitle>채팅</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto">
              <div className="space-y-4">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex ${message.type === "user" ? "justify-end" : "justify-start"
                      }`}
                  >
                    <div
                      className={`max-w-[80%] rounded-lg p-3 ${message.type === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted"
                        }`}
                    >
                      <p className="whitespace-pre-wrap">{message.content}</p>
                      {message.sources && message.sources.length > 0 && (
                        <div className="mt-2">
                          <Separator className="my-2" />
                          <p className="text-xs font-semibold mb-1">참고 소스:</p>
                          {message.sources.map((source, index) => (
                            <div key={index} className="text-xs mb-1">
                              <Badge variant="outline" className="mr-2">
                                {source.type}
                              </Badge>
                              <span className="text-muted-foreground">
                                유사도: {(source.score * 100).toFixed(1)}%
                              </span>
                              <p className="mt-1 text-xs">{source.text}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="bg-muted rounded-lg p-3">
                      <Loader2 className="h-4 w-4 animate-spin" />
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 입력 영역 */}
        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle>메시지 입력</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="messageInput">질문</Label>
                <Textarea
                  id="messageInput"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="문서에 대해 질문하세요..."
                  rows={4}
                />
              </div>
              <Button
                onClick={handleSendMessage}
                disabled={!input.trim() || isLoading}
                className="w-full"
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Send className="h-4 w-4 mr-2" />
                )}
                전송
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
} 