"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { signIn } from "next-auth/react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Bot } from "lucide-react"
import { socialLogin } from "@/lib/social-auth"
import { useAuth } from "@/hooks/use-auth"
import { useToast } from "@/hooks/use-toast"

export default function LoginPage() {
  const { toast } = useToast()
  const [isLoading, setIsLoading] = useState<string | null>(null)
  const router = useRouter()
  const { login, isAuthenticated, isLoading: authLoading } = useAuth()

  // 이미 로그인된 사용자는 대시보드로 리다이렉트
  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      router.push('/dashboard')
    }
  }, [isAuthenticated, authLoading, router])

  // 로그인 중복 방지를 위한 상태
  const [isRedirecting, setIsRedirecting] = useState(false)

  const handleOAuthLogin = async (provider: "google" | "naver") => {
    // 이미 로딩 중이거나 리다이렉트 중이면 중복 요청 방지
    if (isLoading !== null || isRedirecting) {
      return
    }

    setIsLoading(provider)
    setIsRedirecting(true)

    try {
      // 리다이렉트 방식 소셜 로그인 시작
      // socialLogin은 현재 페이지를 localStorage에 저장하고 리다이렉트함
      await socialLogin(provider)
      // 이 시점에서 페이지가 리다이렉트되므로 아래 코드는 실행되지 않음
    } catch (error) {
      console.error('로그인 시작 실패:', error)
      toast({
        title: "로그인 실패",
        description: '로그인을 시작할 수 없습니다. 다시 시도해주세요.',
        variant: "destructive",
        duration: 3000,
      })
      setIsLoading(null)
      setIsRedirecting(false)
    }
  }

  // 인증 로딩 중이거나 이미 로그인된 상태라면 로딩 표시
  if (authLoading || isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <img src="/favicon.ico" alt="AI Influencer Platform" className="h-12 w-12" />
          </div>
          <CardTitle className="text-2xl font-bold">AI Influencer Platform</CardTitle>
          <CardDescription>기업용 AI 인플루언서 생성 및 관리 플랫폼</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="text-center mb-6">
            <p className="text-sm text-gray-600 mb-2">소셜 계정으로 간편하게 시작하세요</p>
            <div className="space-y-2">
              <p className="text-xs text-blue-600 bg-blue-50 px-3 py-2 rounded-lg">
                💡 처음 로그인하면 자동으로 계정이 생성됩니다
              </p>
            </div>
          </div>

          {/* 구글 로그인 버튼 */}
          <Button
            onClick={() => handleOAuthLogin("google")}
            disabled={isLoading !== null || isRedirecting}
            className="w-full bg-white hover:bg-gray-50 text-gray-900 border border-gray-300 flex items-center justify-center space-x-3 py-3"
            variant="outline"
          >
            {isLoading === "google" ? (
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-gray-900"></div>
            ) : (
              <>
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  />
                </svg>
                <span className="font-medium">구글로 시작하기</span>
              </>
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
