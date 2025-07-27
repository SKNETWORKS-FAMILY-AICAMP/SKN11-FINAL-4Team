import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'RAG 챗봇 테스트',
  description: '문서 기반 질의응답 시스템 테스트 페이지',
};

export default function RAGChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background">
      {children}
    </div>
  );
} 