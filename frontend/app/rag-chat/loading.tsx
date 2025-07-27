import { Loader2 } from 'lucide-react';

export default function RAGChatLoading() {
  return (
    <div className="container mx-auto p-4 max-w-4xl">
      <div className="flex items-center justify-center h-[600px]">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin" />
          <p className="text-muted-foreground">RAG 챗봇을 로딩 중...</p>
        </div>
      </div>
    </div>
  );
} 