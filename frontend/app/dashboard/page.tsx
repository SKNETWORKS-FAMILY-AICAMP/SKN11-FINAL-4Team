"use client"

import { useState } from "react"
import Link from "next/link"
import { Navigation } from "@/components/navigation"
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
import { Plus, Search, Settings, Trash2 } from "lucide-react"
import type { AIModel } from "@/lib/types"

// 샘플 데이터
const sampleModels: AIModel[] = [
  {
    id: "1",
    name: "패션 인플루언서 AI",
    description: "20대 여성 타겟의 패션 트렌드 전문 AI 인플루언서",
    personality: "친근하고 트렌디한",
    tone: "캐주얼하고 친밀한",
    status: "ready",
    createdAt: "2024-01-15",
    trainingData: { textSamples: 1500, voiceSamples: 200, imageSamples: 300 },
  },
  {
    id: "2",
    name: "뷰티 전문가 AI",
    description: "화장품 리뷰 및 뷰티 팁 전문 AI 인플루언서",
    personality: "전문적이고 신뢰할 수 있는",
    tone: "정중하고 전문적인",
    status: "training",
    createdAt: "2024-01-20",
    trainingData: { textSamples: 2000, voiceSamples: 150, imageSamples: 250 },
  },
  {
    id: "3",
    name: "피트니스 코치 AI",
    description: "운동 및 건강 관리 전문 AI 인플루언서",
    personality: "동기부여하고 에너지 넘치는",
    tone: "격려하고 활기찬",
    status: "ready",
    createdAt: "2024-01-10",
    trainingData: { textSamples: 1200, voiceSamples: 180, imageSamples: 220 },
  },
]

export default function DashboardPage() {
  const [models, setModels] = useState<AIModel[]>(sampleModels)
  const [searchTerm, setSearchTerm] = useState("")

  const filteredModels = models.filter(
    (model) =>
      model.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      model.description.toLowerCase().includes(searchTerm.toLowerCase()),
  )

  const handleDeleteModel = (modelId: string) => {
    setModels((prev) => prev.filter((model) => model.id !== modelId))
  }

  const getStatusBadge = (status: AIModel["status"]) => {
    switch (status) {
      case "ready":
        return <Badge className="bg-green-100 text-green-800">사용 가능</Badge>
      case "training":
        return <Badge className="bg-yellow-100 text-yellow-800">생성중</Badge>
      case "error":
        return <Badge className="bg-red-100 text-red-800">오류</Badge>
      default:
        return <Badge variant="secondary">알 수 없음</Badge>
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">AI 모델 대시보드</h1>
              <p className="text-gray-600 mt-2">생성된 AI 인플루언서 모델을 관리하세요</p>
            </div>
            <Link href="/create-model">
              <Button className="flex items-center space-x-2">
                <Plus className="h-4 w-4" />
                <span>새 모델 생성</span>
              </Button>
            </Link>
          </div>

          <div className="relative max-w-md mb-6">
            <Search className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
            <Input
              placeholder="모델 검색..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <Card>
              <CardContent className="p-6">
                <div className="text-center">
                  <p className="text-3xl font-bold text-blue-600">{models.length}</p>
                  <p className="text-sm text-gray-600 mt-1">전체 모델</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="text-center">
                  <p className="text-3xl font-bold text-yellow-600">
                    {models.filter((model) => model.status === "training").length}
                  </p>
                  <p className="text-sm text-gray-600 mt-1">학습 중</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <div className="text-center">
                  <p className="text-3xl font-bold text-green-600">
                    {models.filter((model) => model.status === "ready").length}
                  </p>
                  <p className="text-sm text-gray-600 mt-1">사용 가능</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredModels.map((model) => (
            <Card key={model.id} className="hover:shadow-lg transition-shadow flex flex-col">
              <CardHeader className="flex-shrink-0">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <CardTitle className="text-lg">{model.name}</CardTitle>
                    <CardDescription className="mt-2">{model.description}</CardDescription>
                  </div>
                  <div className="flex items-center space-x-2">
                    {getStatusBadge(model.status)}
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="ghost" size="sm" className="text-red-600 hover:text-red-800 hover:bg-red-50">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>모델 삭제</AlertDialogTitle>
                          <AlertDialogDescription>
                            "{model.name}" 모델을 완전히 삭제하시겠습니까?
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
                            onClick={() => handleDeleteModel(model.id)}
                            className="bg-red-600 hover:bg-red-700"
                          >
                            삭제
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex-1 flex flex-col">
                <div className="space-y-3 flex-1">
                  <div>
                    <p className="text-sm font-medium text-gray-700">성격</p>
                    <p className="text-sm text-gray-600">{model.personality}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-700">말투</p>
                    <p className="text-sm text-gray-600">{model.tone}</p>
                  </div>
                  {model.trainingData && (
                    <div>
                      <p className="text-sm font-medium text-gray-700">학습 데이터</p>
                      <div className="text-xs text-gray-600 space-y-1">
                        <p>텍스트: {model.trainingData.textSamples}개</p>
                        <p>음성: {model.trainingData.voiceSamples}개</p>
                        <p>이미지: {model.trainingData.imageSamples}개</p>
                      </div>
                    </div>
                  )}
                  <div className="flex pt-4 mt-auto">
                    <Link href={`/model/${model.id}`} className="flex-1">
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

        {filteredModels.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500 text-lg">검색 결과가 없습니다.</p>
            <p className="text-gray-400 mt-2">다른 검색어를 시도해보세요.</p>
          </div>
        )}
      </div>
    </div>
  )
}