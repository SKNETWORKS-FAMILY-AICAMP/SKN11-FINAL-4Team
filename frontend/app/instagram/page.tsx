'use client'

import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@/hooks/use-auth'
import { useRouter, useSearchParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Instagram, AlertCircle, CheckCircle, Settings } from 'lucide-react'
import { InstagramService, InstagramStatus } from '@/lib/services/instagram.service'
import { InstagramDebugHelper } from '@/components/instagram-debug-helper'
import { useToast } from '@/hooks/use-toast'
import { Suspense } from 'react'

// 임시 인플루언서 ID (실제 앱에서는 동적으로 받아와야 함)
const TEMP_INFLUENCER_ID = 'c85a6638-2289-4202-81a2-6e5a4e5b636a';

function InstagramPageContent() {
  const [status, setStatus] = useState<InstagramStatus | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showDebugHelper, setShowDebugHelper] = useState(false)
  const { isAuthenticated, user } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const { toast } = useToast()

  const fetchStatus = useCallback(async () => {
    if (!isAuthenticated || !user) return

    setIsLoading(true)
    try {
      const instagramStatus = await InstagramService.getStatus(TEMP_INFLUENCER_ID)
      setStatus(instagramStatus)
    } catch (err: any) {
      setError(err.message || '상태 정보를 가져오는 데 실패했습니다.')
      setStatus({ is_connected: false, is_active: false })
    } finally {
      setIsLoading(false)
    }
  }, [isAuthenticated, user])

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login')
    } else {
      fetchStatus()
    }
  }, [isAuthenticated, router, fetchStatus])

  useEffect(() => {
    const code = searchParams.get('code')
    if (code && isAuthenticated) {
      handleInstagramConnect(code)
      // URL에서 code 제거
      router.replace('/instagram')
    }
  }, [searchParams, isAuthenticated, router])

  const handleInstagramLogin = () => {
    const clientId = process.env.NEXT_PUBLIC_INSTAGRAM_APP_ID;
    if (!clientId) {
      setError('Instagram App ID가 설정되지 않았습니다. 환경 변수를 확인해주세요.');
      return;
    }
    const redirectUri = `${window.location.origin}/instagram`;
    const scopes = ['user_profile', 'user_media'].join(',');
    const authUrl = `https://api.instagram.com/oauth/authorize?client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&scope=${scopes}&response_type=code`;
    window.location.href = authUrl;
  }

  const handleInstagramConnect = async (code: string) => {
    setIsLoading(true)
    setError(null)

    try {
      const redirectUri = `${window.location.origin}/instagram`;
      const response = await InstagramService.connectAccount({
        influencer_id: TEMP_INFLUENCER_ID,
        code,
        redirect_uri: redirectUri,
      })

      if (response.success) {
        toast({ title: "성공", description: response.message })
        await fetchStatus() // 상태 새로고침
      } else {
        throw new Error(response.message || 'Instagram 연결에 실패했습니다.')
      }
    } catch (err: any) {
      console.error('Instagram connection error:', err)
      setError(err.message || 'Instagram 연결 중 오류가 발생했습니다.')
      toast({ variant: 'destructive', title: "오류", description: err.message })
    } finally {
      setIsLoading(false)
    }
  }

  const handleDisconnect = async () => {
    setIsLoading(true)
    try {
      await InstagramService.disconnectAccount(TEMP_INFLUENCER_ID)
      toast({ title: "성공", description: "인스타그램 연동이 해제되었습니다." })
      await fetchStatus()
    } catch (err: any) {
      setError(err.message || '연동 해제에 실패했습니다.')
      toast({ variant: 'destructive', title: "오류", description: err.message })
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return <div className="container mx-auto py-8 px-4">로딩 중...</div>
  }

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-8">
        <div className="flex items-center space-x-3 mb-2">
          <Instagram className="w-8 h-8 text-pink-600" />
          <h1 className="text-3xl font-bold">Instagram 관리</h1>
        </div>
        <p className="text-gray-600">Instagram Business 계정을 연결하여 콘텐츠를 관리하세요</p>
      </div>

      {!status?.is_connected ? (
        <div className="max-w-2xl mx-auto">
          <Card>
            <CardHeader className="text-center">
              <div className="w-16 h-16 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full flex items-center justify-center mx-auto mb-4">
                <Instagram className="w-8 h-8 text-white" />
              </div>
              <CardTitle>Instagram 계정 연결</CardTitle>
              <CardDescription>
                Instagram 계정을 연결하여 다양한 기능을 이용하세요.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start space-x-3">
                  <AlertCircle className="w-5 h-5 text-red-500 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-red-800">연결 실패</h4>
                    <p className="text-red-600 text-sm mt-1">{error}</p>
                  </div>
                </div>
              )}
              <Button 
                onClick={handleInstagramLogin}
                disabled={isLoading}
                className="w-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white py-3"
                size="lg"
              >
                <div className="flex items-center space-x-2">
                  <Instagram className="w-5 h-5" />
                  <span>Instagram 계정으로 로그인</span>
                </div>
              </Button>
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>연결된 계정 정보</CardTitle>
            </CardHeader>
            <CardContent>
              <p><strong>사용자 이름:</strong> @{status.instagram_username}</p>
              <p><strong>계정 종류:</strong> {status.account_type}</p>
              <p><strong>연결 상태:</strong> {status.is_active ? <Badge>활성</Badge> : <Badge variant="destructive">비활성</Badge>}</p>
              <p><strong>연결 일시:</strong> {status.connected_at ? new Date(status.connected_at).toLocaleString() : '-'}</p>
              <Button onClick={handleDisconnect} variant="destructive" className="mt-4">연결 해제</Button>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="mt-4">
        <Button 
          variant="outline" 
          size="sm"
          onClick={() => setShowDebugHelper(!showDebugHelper)}
          className="text-xs"
        >
          <Settings className="w-3 h-3 mr-1" />
          {showDebugHelper ? '디버그 도구 숨기기' : '연결 문제 해결'}
        </Button>
      </div>

      {showDebugHelper && (
        <div className="mt-6">
          <InstagramDebugHelper />
        </div>
      )}
    </div>
  )
}

export default function InstagramPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <InstagramPageContent />
    </Suspense>
  )
}
