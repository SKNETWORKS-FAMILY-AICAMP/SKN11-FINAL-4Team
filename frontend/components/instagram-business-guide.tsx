"use client"

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { CheckCircle, AlertCircle, ExternalLink, Lightbulb, Users, BarChart3, MessageSquare } from "lucide-react"

interface InstagramBusinessGuideProps {
  userAccountType?: string
  isBusinessVerified?: boolean
  recommendations?: string[]
  onClose?: () => void
}

export function InstagramBusinessGuide({ 
  userAccountType = 'PERSONAL', 
  isBusinessVerified = false,
  recommendations = [],
  onClose 
}: InstagramBusinessGuideProps) {
  const [currentStep, setCurrentStep] = useState(0)

  const businessFeatures = [
    {
      icon: BarChart3,
      title: "인사이트 분석",
      description: "게시물 성과, 도달률, 참여율 등 상세한 분석 데이터",
      available: isBusinessVerified
    },
    {
      icon: MessageSquare,
      title: "메시지 관리",
      description: "고객과의 소통을 위한 메시지 관리 도구",
      available: isBusinessVerified
    },
    {
      icon: Users,
      title: "오디언스 인사이트",
      description: "팔로워 분석 및 타겟 오디언스 파악",
      available: isBusinessVerified
    }
  ]

  const conversionSteps = [
    {
      title: "Instagram 앱 열기",
      description: "모바일에서 Instagram 앱을 실행합니다"
    },
    {
      title: "프로필 설정 이동",
      description: "프로필 → 설정 → 계정 → 전문 계정으로 전환"
    },
    {
      title: "계정 유형 선택",
      description: "비즈니스 또는 크리에이터 중 선택"
    },
    {
      title: "정보 입력",
      description: "연락처 정보 및 카테고리 설정"
    },
    {
      title: "완료",
      description: "다시 로그인하여 새로운 권한 적용"
    }
  ]

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                {isBusinessVerified ? (
                  <>
                    <CheckCircle className="w-5 h-5 text-green-500" />
                    비즈니스 계정 활성화됨
                  </>
                ) : (
                  <>
                    <AlertCircle className="w-5 h-5 text-orange-500" />
                    비즈니스 계정으로 업그레이드
                  </>
                )}
              </CardTitle>
              <CardDescription>
                현재 계정 타입: <Badge variant={isBusinessVerified ? "default" : "secondary"}>
                  {userAccountType === 'BUSINESS' ? '비즈니스' : 
                   userAccountType === 'CREATOR' ? '크리에이터' : '개인'}
                </Badge>
              </CardDescription>
            </div>
            {onClose && (
              <Button variant="ghost" size="sm" onClick={onClose}>
                ✕
              </Button>
            )}
          </div>
        </CardHeader>

        <CardContent className="space-y-6">
          {!isBusinessVerified && recommendations.length > 0 && (
            <Alert>
              <Lightbulb className="h-4 w-4" />
              <AlertDescription>
                <ul className="list-disc list-inside space-y-1">
                  {recommendations.map((rec, index) => (
                    <li key={index}>{rec}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          {/* 비즈니스 기능 소개 */}
          <div>
            <h3 className="text-lg font-semibold mb-3">비즈니스 계정 전용 기능</h3>
            <div className="grid gap-4">
              {businessFeatures.map((feature, index) => (
                <div key={index} className={`flex items-start gap-3 p-3 rounded-lg border ${
                  feature.available ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'
                }`}>
                  <feature.icon className={`w-5 h-5 mt-0.5 ${
                    feature.available ? 'text-green-600' : 'text-gray-400'
                  }`} />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="font-medium">{feature.title}</h4>
                      {feature.available && <CheckCircle className="w-4 h-4 text-green-500" />}
                    </div>
                    <p className="text-sm text-gray-600">{feature.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 계정 전환 가이드 */}
          {!isBusinessVerified && (
            <div>
              <h3 className="text-lg font-semibold mb-3">비즈니스 계정 전환 방법</h3>
              <div className="space-y-3">
                {conversionSteps.map((step, index) => (
                  <div key={index} className={`flex items-start gap-3 p-3 rounded-lg ${
                    index <= currentStep ? 'bg-blue-50 border border-blue-200' : 'bg-gray-50'
                  }`}>
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-sm font-medium ${
                      index <= currentStep ? 'bg-blue-500 text-white' : 'bg-gray-300 text-gray-600'
                    }`}>
                      {index + 1}
                    </div>
                    <div>
                      <h4 className="font-medium">{step.title}</h4>
                      <p className="text-sm text-gray-600">{step.description}</p>
                    </div>
                  </div>
                ))}
              </div>

              {currentStep < conversionSteps.length - 1 && (
                <Button 
                  onClick={() => setCurrentStep(currentStep + 1)}
                  className="w-full mt-4"
                >
                  다음 단계
                </Button>
              )}
            </div>
          )}

          {/* 도움말 링크 */}
          <div className="border-t pt-4">
            <h4 className="font-medium mb-2">추가 도움이 필요하신가요?</h4>
            <div className="space-y-2">
              <a 
                href="https://help.instagram.com/502981923235522" 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-blue-600 hover:text-blue-800 text-sm"
              >
                <ExternalLink className="w-4 h-4" />
                Instagram 비즈니스 계정 공식 가이드
              </a>
              <a 
                href="https://business.instagram.com/" 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-blue-600 hover:text-blue-800 text-sm"
              >
                <ExternalLink className="w-4 h-4" />
                Instagram for Business
              </a>
            </div>
          </div>

          {/* 액션 버튼 */}
          <div className="flex gap-3 pt-4">
            {isBusinessVerified ? (
              <Button onClick={onClose} className="flex-1">
                시작하기
              </Button>
            ) : (
              <>
                <Button variant="outline" onClick={onClose} className="flex-1">
                  나중에 하기
                </Button>
                <Button 
                  onClick={() => window.open('https://help.instagram.com/502981923235522', '_blank')}
                  className="flex-1"
                >
                  전환 가이드 보기
                </Button>
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}