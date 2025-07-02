"use client"

import { useState, useMemo, useEffect } from "react"
import Link from "next/link"
import { Navigation } from "@/components/navigation"
import { RequireAuth } from "@/components/auth/protected-route"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Plus, Search, Settings, Trash2, Loader2 } from "lucide-react"
import { usePermission } from "@/hooks/use-auth"
import { ModelService, type AIInfluencer } from "@/lib/services/model.service"

export default function DashboardPage() {
  const [influencers, setInfluencers] = useState<AIInfluencer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState("")
  const { canAccessModel, hasPermission, user } = usePermission()

  // API에서 인플루언서 데이터 가져오기
  useEffect(() => {
    const fetchInfluencers = async () => {
      try {
        setLoading(true)
        const data = await ModelService.getInfluencers()
        setInfluencers(data)
      } catch (err) {
        console.error('Failed to fetch influencers:', err)
        setError('인플루언서 정보를 불러오는데 실패했습니다.')
      } finally {
        setLoading(false)
      }
    }

    fetchInfluencers()
  }, [])

  const filteredInfluencers = influencers.filter(
    (influencer) =>
      influencer.influencer_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (influencer.style_preset?.style_preset_name || '').toLowerCase().includes(searchTerm.toLowerCase()),
  )

  const handleDeleteInfluencer = async (influencerId: string) => {
    const influencer = influencers.find(i => i.influencer_id === influencerId)
    if (influencer && (hasPermission('model', 'delete') || influencer.user_id === user?.user_id)) {
      try {
        await ModelService.deleteInfluencer(influencerId)
        setInfluencers((prev) => prev.filter((inf) => inf.influencer_id !== influencerId))
      } catch (err) {
        console.error('Failed to delete influencer:', err)
        setError('인플루언서 삭제에 실패했습니다.')
      }
    }
  }

  const canDeleteInfluencer = (influencer: AIInfluencer) => {
    return hasPermission('model', 'delete') || influencer.user_id === user?.user_id
  }

  const getStatusBadge = (learning_status: number) => {
    switch (learning_status) {
      case 1:
        return <Badge className="bg-green-100 text-green-800">사용 가능</Badge>
      case 0:
        return <Badge className="bg-yellow-100 text-yellow-800">생성 중</Badge>
      case 2:
        return <Badge className="bg-red-100 text-red-800">오류</Badge>
      default:
        return <Badge variant="secondary">알 수 없음</Badge>
    }
  }

  return (
    <RequireAuth blockGroup={2}>
      <div className="min-h-screen bg-gray-50">
        <Navigation />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            {loading ? (
              <div className="flex justify-center items-center py-12">
                <Loader2 className="h-8 w-8 animate-spin" />
                <span className="ml-2">인플루언서 정보를 불러오는 중...</span>
              </div>
            ) : error ? (
              <div className="text-center py-12">
                <p className="text-red-500 text-lg">{error}</p>
                <Button onClick={() => window.location.reload()} className="mt-4">
                  다시 시도
                </Button>
              </div>
            ) : (
              <>
                <div className="mb-8">
                  <div className="flex justify-between items-center mb-6">
                    <div>
                      <h1 className="text-3xl font-bold text-gray-900">AI 인플루언서 대시보드</h1>
                      <p className="text-gray-600 mt-2">생성된 AI 인플루언서를 관리하세요</p>
                    </div>
                  </div>

                  <div className="flex justify-between items-center mb-6">
                  <div className="relative max-w-md">
                    <Search className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                    <Input
                      placeholder="인플루언서 검색..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                  
                  {hasPermission('model', 'create') && (
                    <Link href="/create-model">
                      <Button className="flex items-center space-x-2">
                        <Plus className="h-4 w-4" />
                        <span>새 AI 인플루언서 생성</span>
                      </Button>
                    </Link>
                  )}
                </div>  
                
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                    <Card>
                      <CardContent className="p-6">
                        <div className="text-center">
                          <p className="text-3xl font-bold text-blue-600">{influencers.length}</p>
                          <p className="text-sm text-gray-600 mt-1">전체 인플루언서</p>
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-6">
                        <div className="text-center">
                          <p className="text-3xl font-bold text-yellow-600">
                            {influencers.filter((inf) => inf.learning_status === 0).length}
                          </p>
                          <p className="text-sm text-gray-600 mt-1">생성 중</p>
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-6">
                        <div className="text-center">
                          <p className="text-3xl font-bold text-green-600">
                            {influencers.filter((inf) => inf.learning_status === 1).length}
                          </p>
                          <p className="text-sm text-gray-600 mt-1">사용 가능</p>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </div>
                
                

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {filteredInfluencers.map((influencer) => (
                    <Card key={influencer.influencer_id} className="hover:shadow-lg transition-shadow flex flex-col">
                      <CardHeader className="flex-shrink-0">
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <CardTitle className="text-lg">{influencer.influencer_name}</CardTitle>
                            <CardDescription className="mt-2">
                              {influencer.style_preset?.style_preset_name || '스타일 프리셋 없음'}
                            </CardDescription>
                          </div>
                          <div className="flex items-center space-x-2">
                            {getStatusBadge(influencer.learning_status)}
                            {canDeleteInfluencer(influencer) && (
                              <AlertDialog>
                                <AlertDialogTrigger asChild>
                                  <Button variant="ghost" size="sm" className="text-red-600 hover:text-red-800 hover:bg-red-50">
                                    <Trash2 className="h-4 w-4" />
                                  </Button>
                                </AlertDialogTrigger>
                                <AlertDialogContent>
                                  <AlertDialogHeader>
                                    <AlertDialogTitle>인플루언서 삭제</AlertDialogTitle>
                                    <AlertDialogDescription>
                                      "{influencer.influencer_name}" 인플루언서를 완전히 삭제하시겠습니까?
                                      <br />
                                      <br />
                                      <strong>이 작업은 되돌릴 수 없으며, 다음 데이터가 모두 삭제됩니다:</strong>
                                      <br />• 모든 게시글 및 콘텐츠
                                      <br />• API 키 및 설정
                                      <br />• 학습 데이터 및 모델 정보
                                      <br />• 분석 데이터 및 통계
                                    </AlertDialogDescription>
                                  </AlertDialogHeader>
                                  <AlertDialogFooter>
                                    <AlertDialogCancel>취소</AlertDialogCancel>
                                    <AlertDialogAction
                                      onClick={() => handleDeleteInfluencer(influencer.influencer_id)}
                                      className="bg-red-600 hover:bg-red-700"
                                    >
                                      삭제
                                    </AlertDialogAction>
                                  </AlertDialogFooter>
                                </AlertDialogContent>
                              </AlertDialog>
                            )}
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="flex-1 flex flex-col">
                        <div className="space-y-3 flex-1">
                          <div>
                            <p className="text-sm font-medium text-gray-700">성격</p>
                            <p className="text-sm text-gray-600">
                              {influencer.style_preset?.influencer_personality || '-'}
                            </p>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-gray-700">말투</p>
                            <p className="text-sm text-gray-600">
                              {influencer.style_preset?.influencer_speech || '-'}
                            </p>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-gray-700">MBTI</p>
                            <p className="text-sm text-gray-600">{influencer.mbti?.mbti_name || '-'}</p>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-gray-700">챗봇 옵션</p>
                            <p className="text-sm text-gray-600">
                              {influencer.chatbot_option ? '활성화' : '비활성화'}
                            </p>
                          </div>
                          <div className="flex pt-4 mt-auto">
                            <Link href={`/model/${influencer.influencer_id}`} className="flex-1">
                              <Button variant="outline" size="sm" className="w-full">
                                <Settings className="h-4 w-4 mr-2" />
                                관리
                              </Button>
                            </Link>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                {filteredInfluencers.length === 0 && !loading && (
                  <div className="text-center py-12">
                    <p className="text-gray-500 text-lg">검색 결과가 없습니다.</p>
                    <p className="text-gray-400 mt-2">다른 검색어를 시도해보세요.</p>
                  </div>
                )}
              </>
            )}
          </div>
      </div>
    </RequireAuth>
  )
}