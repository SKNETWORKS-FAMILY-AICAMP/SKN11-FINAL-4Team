"use client"

import type React from "react"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Navigation } from "@/components/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Upload, ArrowLeft, Lightbulb } from "lucide-react"
import Link from "next/link"

export default function CreateModelPage() {
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    personality: "",
    tone: "",
    customTone: "",
  })
  const [files, setFiles] = useState({
    imageSamples: null as File[] | null,
  })
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()

  const handleInputChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  const handleFileUpload = (type: keyof typeof files, uploadedFiles: FileList | null) => {
    if (uploadedFiles) {
      setFiles((prev) => ({ ...prev, [type]: Array.from(uploadedFiles) }))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    // 실제 모델 생성 로직 시뮬레이션
    setTimeout(() => {
      setIsLoading(false)
      router.push("/dashboard")
    }, 2000)
  }

  // 성격 기반 말투 예시 생성
  const generateToneExamples = (personality: string) => {
    if (!personality.trim()) return []

    const personalityLower = personality.toLowerCase()

    // 성격 키워드에 따른 말투 예시
    const toneMap: Record<string, string[]> = {
      친근: ["친밀하고 다정한", "편안하고 따뜻한", "가까운 친구 같은"],
      전문: ["정중하고 전문적인", "신뢰할 수 있는", "지식이 풍부한"],
      활발: ["에너지 넘치는", "밝고 긍정적인", "열정적이고 활기찬"],
      차분: ["차분하고 안정적인", "신중하고 사려깊은", "평온하고 여유로운"],
      유머: ["재치있고 유머러스한", "웃음을 주는", "밝고 재미있는"],
      세련: ["우아하고 세련된", "품격있는", "고급스러운"],
      솔직: ["직설적이고 솔직한", "진실한", "꾸밈없는"],
      창의: ["창의적이고 독창적인", "예술적인", "상상력이 풍부한"],
    }

    // 성격에서 키워드 찾기
    const matchedTones: string[] = []
    Object.keys(toneMap).forEach((key) => {
      if (personalityLower.includes(key)) {
        matchedTones.push(...toneMap[key])
      }
    })

    // 매칭되는 것이 없으면 기본 예시 제공
    if (matchedTones.length === 0) {
      return ["친근하고 다정한", "정중하고 전문적인", "밝고 긍정적인"]
    }

    // 중복 제거하고 최대 3개까지
    return [...new Set(matchedTones)].slice(0, 3)
  }

  const toneExamples = generateToneExamples(formData.personality)

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <Link href="/dashboard" className="inline-flex items-center text-blue-600 hover:text-blue-800 mb-4">
            <ArrowLeft className="h-4 w-4 mr-2" />
            대시보드로 돌아가기
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">새 AI 인플루언서 생성</h1>
          <p className="text-gray-600 mt-2">AI 인플루언서의 특성과 학습 데이터를 설정하세요</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-8">
          {/* 기본 정보 */}
          <Card>
            <CardHeader>
              <CardTitle>기본 정보</CardTitle>
              <CardDescription>AI 인플루언서의 기본적인 정보를 입력하세요</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="name">모델 이름</Label>
                <Input
                  id="name"
                  placeholder="예: 패션 인플루언서 AI"
                  value={formData.name}
                  onChange={(e) => handleInputChange("name", e.target.value)}
                  required
                />
              </div>

              <div>
                <Label htmlFor="description">설명</Label>
                <Textarea
                  id="description"
                  placeholder="AI 인플루언서에 대한 상세한 설명을 입력하세요"
                  value={formData.description}
                  onChange={(e) => handleInputChange("description", e.target.value)}
                  rows={3}
                  required
                />
              </div>
            </CardContent>
          </Card>

          {/* 성격 및 말투 설정 */}
          <Card>
            <CardHeader>
              <CardTitle>성격 및 말투</CardTitle>
              <CardDescription>AI 인플루언서의 성격과 커뮤니케이션 스타일을 정의하세요</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <Label htmlFor="personality">성격</Label>
                <Input
                  id="personality"
                  placeholder="예: 친근하고 트렌디한, 전문적이고 신뢰할 수 있는, 활발하고 에너지 넘치는"
                  value={formData.personality}
                  onChange={(e) => handleInputChange("personality", e.target.value)}
                  required
                />
                <p className="text-xs text-gray-500 mt-1">💡 성격을 입력하면 아래 말투 예시가 자동으로 생성됩니다</p>
              </div>

              <div>
                <Label className="text-base font-medium">말투</Label>
                <p className="text-sm text-gray-600 mb-4">성격에 맞는 말투를 선택하거나 직접 입력하세요</p>

                {toneExamples.length > 0 && (
                  <div className="space-y-3 mb-4">
                    <div className="flex items-center space-x-2 text-sm text-blue-600">
                      <Lightbulb className="h-4 w-4" />
                      <span>성격 기반 추천 말투</span>
                    </div>
                    <RadioGroup value={formData.tone} onValueChange={(value) => handleInputChange("tone", value)}>
                      {toneExamples.map((example, index) => (
                        <div key={index} className="flex items-center space-x-2">
                          <RadioGroupItem value={example} id={`tone-${index}`} />
                          <Label htmlFor={`tone-${index}`} className="cursor-pointer">
                            {example}
                          </Label>
                        </div>
                      ))}
                      <div className="flex items-center space-x-2">
                        <RadioGroupItem value="custom" id="tone-custom" />
                        <Label htmlFor="tone-custom" className="cursor-pointer">
                          직접 입력
                        </Label>
                      </div>
                    </RadioGroup>
                  </div>
                )}

                {(formData.tone === "custom" || toneExamples.length === 0) && (
                  <div>
                    <Label htmlFor="customTone">{toneExamples.length === 0 ? "말투" : "사용자 정의 말투"}</Label>
                    <Input
                      id="customTone"
                      placeholder="예: 캐주얼하고 친밀한, 정중하고 전문적인"
                      value={formData.customTone}
                      onChange={(e) => handleInputChange("customTone", e.target.value)}
                      required={formData.tone === "custom" || toneExamples.length === 0}
                    />
                  </div>
                )}

                {toneExamples.length === 0 && formData.personality && (
                  <div className="mt-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                    <div className="flex items-center space-x-2">
                      <Lightbulb className="h-4 w-4 text-yellow-600" />
                      <span className="text-sm text-yellow-800">
                        "{formData.personality}" 성격에 맞는 말투 예시를 생성하지 못했습니다. 직접 입력해주세요.
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* 학습 데이터 업로드 */}
          <Card>
            <CardHeader>
              <CardTitle>이미지 업로드</CardTitle>
              <CardDescription>AI 인플루언서가 사용할 이미지를 업로드하세요</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* 이미지 샘플 */}
              <div>
                <Label className="flex items-center space-x-2 mb-2"></Label>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors">
                  <Upload className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                  <p className="text-sm text-gray-600 mb-2">이미지 파일을 드래그하거나 클릭하여 업로드</p>
                  <input
                    type="file"
                    multiple
                    accept=".jpg,.jpeg,.png,.webp"
                    onChange={(e) => handleFileUpload("imageSamples", e.target.files)}
                    className="hidden"
                    id="image-upload"
                  />
                  <Label htmlFor="image-upload" className="cursor-pointer">
                    <Button type="button" variant="outline" size="sm">
                      파일 선택
                    </Button>
                  </Label>
                  {files.imageSamples && (
                    <p className="text-xs text-green-600 mt-2">{files.imageSamples.length}개 파일 선택됨</p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 제출 버튼 */}
          <div className="flex justify-end space-x-4">
            <Link href="/dashboard">
              <Button type="button" variant="outline">
                취소
              </Button>
            </Link>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? "생성 중..." : "AI 모델 생성"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
