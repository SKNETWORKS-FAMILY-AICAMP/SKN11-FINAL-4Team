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



export default function RAGGPUChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const [vectorStats, setVectorStats] = useState<VectorStats | null>(null);
  const [systemMessage, setSystemMessage] = useState(
    "당신은 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하는 AI 어시스턴트입니다."
  );
  const [influencerName, setInfluencerName] = useState("AI");
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
      // 벡터DB에서 관련 문서 검색
      const searchResults = await VectorDBService.embedAndSearch(
        input,
        topK,
        similarityThreshold
      );

      // 검색 결과를 바탕으로 AI 응답 생성
      const context = searchResults
        .map(result => result.text)
        .join('\n\n');

      const prompt = `참고 문서:\n${context}\n\n사용자 질문: ${input}\n\n위 문서를 바탕으로 정확하고 도움이 되는 답변을 제공하세요.`;

      // AI 응답 생성 (실제로는 vLLM API 호출)
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: "assistant",
        content: `검색된 관련 문서 ${searchResults.length}개를 바탕으로 답변드립니다:\n\n${prompt}`,
        timestamp: new Date(),
        sources: searchResults.map(result => ({
          text: result.text,
          score: result.score,
          type: "vector_search",
          chunk_id: result.id,
          metadata: result.metadata
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
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="systemMessage">시스템 메시지</Label>
              <Textarea
                id="systemMessage"
                value={systemMessage}
                onChange={(e) => setSystemMessage(e.target.value)}
                placeholder="AI 어시스턴트의 역할을 정의하세요"
                rows={3}
              />
            </div>
            <div>
              <Label htmlFor="influencerName">AI 캐릭터 이름</Label>
              <Input
                id="influencerName"
                value={influencerName}
                onChange={(e) => setInfluencerName(e.target.value)}
                placeholder="AI"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
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