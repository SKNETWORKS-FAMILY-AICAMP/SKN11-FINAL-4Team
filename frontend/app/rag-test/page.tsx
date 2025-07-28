'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Upload, Search, MessageSquare, FileText, AlertCircle } from 'lucide-react'

export default function RAGTestPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [chatMessage, setChatMessage] = useState('')
  const [uploadResult, setUploadResult] = useState<any>(null)
  const [searchResult, setSearchResult] = useState<any>(null)
  const [chatResult, setChatResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

  // 테스트용 토큰 (실제 환경에서는 제거)
  const TEST_TOKEN = 'test-token-for-development'

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file && file.type === 'application/pdf') {
      setSelectedFile(file)
    } else {
      alert('PDF 파일만 업로드 가능합니다.')
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) {
      alert('파일을 선택해주세요.')
      return
    }

    setLoading(true)
    setAuthError(null)
    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('group_id', '1') // 테스트용 그룹 ID
      formData.append('max_qa_pairs', '10')

      const response = await fetch(`${API_BASE_URL}/api/v1/rag/upload_file`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${TEST_TOKEN}` // 테스트용 토큰
        },
        body: formData
      })

      if (response.status === 401) {
        setAuthError('인증이 필요합니다. 백엔드 서버를 확인해주세요.')
        return
      }

      const result = await response.json()
      setUploadResult(result)
    } catch (error) {
      console.error('Upload error:', error)
      setUploadResult({ error: '업로드 실패' })
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      alert('검색어를 입력해주세요.')
      return
    }

    setLoading(true)
    setAuthError(null)
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/rag/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${TEST_TOKEN}` // 테스트용 토큰
        },
        body: JSON.stringify({
          query: searchQuery,
          top_k: 3,
          min_score: 0.7,
          include_context: true
        })
      })

      if (response.status === 401) {
        setAuthError('인증이 필요합니다. 백엔드 서버를 확인해주세요.')
        return
      }

      const result = await response.json()
      setSearchResult(result)
    } catch (error) {
      console.error('Search error:', error)
      setSearchResult({ error: '검색 실패' })
    } finally {
      setLoading(false)
    }
  }

  const handleChat = async () => {
    if (!chatMessage.trim()) {
      alert('메시지를 입력해주세요.')
      return
    }

    setLoading(true)
    setAuthError(null)
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/rag/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${TEST_TOKEN}` // 테스트용 토큰
        },
        body: JSON.stringify({
          query: chatMessage,
          group_id: 1,
          include_sources: true
        })
      })

      if (response.status === 401) {
        setAuthError('인증이 필요합니다. 백엔드 서버를 확인해주세요.')
        return
      }

      const result = await response.json()
      setChatResult(result)
    } catch (error) {
      console.error('Chat error:', error)
      setChatResult({ error: '채팅 실패' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="text-center">
        <h1 className="text-3xl font-bold mb-2">RAG 기능 테스트</h1>
        <p className="text-gray-600">백엔드 RAG 기능을 테스트할 수 있는 페이지입니다.</p>
      </div>

      {/* 인증 에러 표시 */}
      {authError && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-red-700">
              <AlertCircle className="h-5 w-5" />
              <span className="font-semibold">인증 에러:</span>
              <span>{authError}</span>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* 파일 업로드 테스트 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-5 w-5" />
              문서 업로드
            </CardTitle>
            <CardDescription>PDF 파일을 업로드하여 RAG에 저장합니다.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              type="file"
              accept=".pdf"
              onChange={handleFileSelect}
              className="cursor-pointer"
            />
            <Button 
              onClick={handleUpload} 
              disabled={!selectedFile || loading}
              className="w-full"
            >
              {loading ? '업로드 중...' : '업로드'}
            </Button>
            
            {uploadResult && (
              <div className="mt-4 p-3 bg-gray-50 rounded">
                <h4 className="font-semibold mb-2">결과:</h4>
                <pre className="text-sm overflow-auto">
                  {JSON.stringify(uploadResult, null, 2)}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>

        {/* 검색 테스트 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="h-5 w-5" />
              문서 검색
            </CardTitle>
            <CardDescription>업로드된 문서에서 관련 내용을 검색합니다.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              placeholder="검색어를 입력하세요..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <Button 
              onClick={handleSearch} 
              disabled={!searchQuery.trim() || loading}
              className="w-full"
            >
              {loading ? '검색 중...' : '검색'}
            </Button>
            
            {searchResult && (
              <div className="mt-4 p-3 bg-gray-50 rounded">
                <h4 className="font-semibold mb-2">검색 결과:</h4>
                <pre className="text-sm overflow-auto">
                  {JSON.stringify(searchResult, null, 2)}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>

        {/* 채팅 테스트 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              RAG 채팅
            </CardTitle>
            <CardDescription>RAG 기반으로 질문에 답변합니다.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              placeholder="질문을 입력하세요..."
              value={chatMessage}
              onChange={(e) => setChatMessage(e.target.value)}
              rows={3}
            />
            <Button 
              onClick={handleChat} 
              disabled={!chatMessage.trim() || loading}
              className="w-full"
            >
              {loading ? '처리 중...' : '질문하기'}
            </Button>
            
            {chatResult && (
              <div className="mt-4 p-3 bg-gray-50 rounded">
                <h4 className="font-semibold mb-2">답변:</h4>
                <pre className="text-sm overflow-auto">
                  {JSON.stringify(chatResult, null, 2)}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 상태 정보 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            시스템 상태
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <Badge variant="outline">백엔드</Badge>
              <p className="text-sm text-gray-600 mt-1">연결됨</p>
            </div>
            <div className="text-center">
              <Badge variant="outline">VLLM</Badge>
              <p className="text-sm text-gray-600 mt-1">팀원 작업 중</p>
            </div>
            <div className="text-center">
              <Badge variant="outline">RAG</Badge>
              <p className="text-sm text-gray-600 mt-1">Mock 모드</p>
            </div>
            <div className="text-center">
              <Badge variant="outline">테스트</Badge>
              <p className="text-sm text-gray-600 mt-1">진행 중</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
} 