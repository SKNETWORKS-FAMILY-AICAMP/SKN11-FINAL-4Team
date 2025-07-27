"use client";

import React, { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Loader2, Send, Upload, FileText, MessageSquare, Settings } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { RAGService, RAGChatRequest, RAGChatResponse, RAGPipelineInfo } from '@/lib/services/rag.service';

interface ChatMessage {
  id: string;
  type: 'user' | 'ai';
  content: string;
  timestamp: string;
  sources?: Array<{
    text: string;
    score: number;
    source: string;
    page: number;
  }>;
  context_preview?: string;
}



export default function RAGChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [pipelineInfo, setPipelineInfo] = useState<RAGPipelineInfo | null>(null);
  const [groupId, setGroupId] = useState(1);
  const [showSources, setShowSources] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  // 자동 스크롤
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 초기 메시지
  useEffect(() => {
    setMessages([
      {
        id: '1',
        type: 'ai',
        content: '안녕하세요! 저는 RAG 챗봇입니다. 먼저 PDF 문서를 업로드해주세요.',
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);
  }, []);

  // 문서 업로드
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.pdf')) {
      toast({
        title: "파일 형식 오류",
        description: "PDF 파일만 업로드 가능합니다.",
        variant: "destructive",
      });
      return;
    }

    setIsUploading(true);
    try {
      // RAGService를 사용한 파일 업로드
      const data = await RAGService.uploadFile(
        file,
        groupId,
        "당신은 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하는 AI 어시스턴트입니다.",
        "AI"
      );
      
      // 파이프라인 정보 설정
      setPipelineInfo(data.pipeline_info);

      // 성공 메시지 추가
      setMessages(prev => [
        ...prev,
        {
          id: Date.now().toString(),
          type: 'ai',
          content: `✅ 문서 업로드 완료! ${data.pipeline_info.qa_count}개의 QA 쌍이 생성되었습니다. 이제 질문해주세요!`,
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);

      toast({
        title: "업로드 성공",
        description: "문서가 성공적으로 업로드되었습니다.",
      });

    } catch (error) {
      console.error('Upload error:', error);
      toast({
        title: "업로드 실패",
        description: "문서 업로드 중 오류가 발생했습니다.",
        variant: "destructive",
      });
    } finally {
      setIsUploading(false);
    }
  };

  // 메시지 전송
  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: inputMessage,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      // RAGService를 사용한 채팅
      const data = await RAGService.chat({
        query: inputMessage,
        group_id: groupId,
        include_sources: showSources,
      });

      const aiMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'ai',
        content: data.response,
        timestamp: new Date().toLocaleTimeString(),
        sources: data.sources,
        context_preview: data.context_preview,
      };

      setMessages(prev => [...prev, aiMessage]);

    } catch (error) {
      console.error('Chat error:', error);
      
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'ai',
        content: '죄송합니다. 응답 생성 중 오류가 발생했습니다. 다시 시도해주세요.',
        timestamp: new Date().toLocaleTimeString(),
      };

      setMessages(prev => [...prev, errorMessage]);

      toast({
        title: "오류 발생",
        description: "채팅 중 오류가 발생했습니다.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Enter 키 처리
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="container mx-auto p-4 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">RAG 챗봇 테스트</h1>
          <p className="text-muted-foreground">문서 기반 질의응답 시스템</p>
        </div>
        
        <div className="flex items-center gap-2">
          <Badge variant={pipelineInfo ? "default" : "secondary"}>
            {pipelineInfo ? "문서 로드됨" : "문서 필요"}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowSources(!showSources)}
          >
            <Settings className="w-4 h-4 mr-2" />
            {showSources ? "출처 숨기기" : "출처 보기"}
          </Button>
        </div>
      </div>

      {/* 문서 업로드 섹션 */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="w-5 h-5" />
            문서 업로드
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <Input
              type="file"
              accept=".pdf"
              onChange={handleFileUpload}
              disabled={isUploading}
              className="flex-1"
            />
            <Button disabled={isUploading}>
              {isUploading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  업로드 중...
                </>
              ) : (
                <>
                  <FileText className="w-4 h-4 mr-2" />
                  PDF 선택
                </>
              )}
            </Button>
          </div>
          
          {pipelineInfo && (
            <div className="mt-4 p-3 bg-muted rounded-lg">
              <h4 className="font-semibold mb-2">파이프라인 정보</h4>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>문서: {pipelineInfo.pdf_path}</div>
                <div>QA 쌍: {pipelineInfo.qa_count}개</div>
                <div>캐릭터: {pipelineInfo.influencer_name}</div>
                <div>생성: {new Date(pipelineInfo.created_at).toLocaleString()}</div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 채팅 영역 */}
      <Card className="h-[600px] flex flex-col">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5" />
            채팅
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-1 flex flex-col">
          {/* 메시지 영역 */}
          <ScrollArea className="flex-1 mb-4">
            <div className="space-y-4">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg p-3 ${
                      message.type === 'user'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted'
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{message.content}</div>
                    
                    {/* 출처 정보 */}
                    {message.sources && showSources && message.sources.length > 0 && (
                      <div className="mt-3 pt-3 border-t">
                        <div className="text-xs font-semibold mb-2">참고 문서:</div>
                        {message.sources.slice(0, 3).map((source, index) => (
                          <div key={index} className="text-xs mb-1 p-2 bg-background rounded">
                            <div className="font-medium">
                              {source.source} (페이지 {source.page})
                            </div>
                            <div className="text-muted-foreground">
                              {source.text.substring(0, 100)}...
                            </div>
                            <div className="text-xs text-muted-foreground">
                              유사도: {(source.score * 100).toFixed(1)}%
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    
                    <div className="text-xs opacity-70 mt-2">
                      {message.timestamp}
                    </div>
                  </div>
                </div>
              ))}
              
              {isLoading && (
                <div className="flex justify-start">
                  <div className="bg-muted rounded-lg p-3">
                    <div className="flex items-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>응답 생성 중...</span>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>

          {/* 입력 영역 */}
          <Separator className="mb-4" />
          <div className="flex gap-2">
            <Input
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="질문을 입력하세요..."
              disabled={isLoading || !pipelineInfo}
              className="flex-1"
            />
            <Button
              onClick={handleSendMessage}
              disabled={isLoading || !inputMessage.trim() || !pipelineInfo}
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
} 