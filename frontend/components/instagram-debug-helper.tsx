"use client"

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { CheckCircle, AlertCircle, Info, ExternalLink } from "lucide-react"

interface DebugInfo {
  hasAppId: boolean
  hasAppSecret: boolean
  redirectUri: string
  currentOrigin: string
  userAgent: string
  popupSupported: boolean
}

export function InstagramDebugHelper() {
  const [debugInfo, setDebugInfo] = useState<DebugInfo | null>(null)
  const [isChecking, setIsChecking] = useState(false)

  const runDebugCheck = () => {
    setIsChecking(true)
    
    setTimeout(() => {
      const clientId = process.env.NEXT_PUBLIC_INSTAGRAM_APP_ID || '';
      const info: DebugInfo = {
        hasAppId: !!clientId,
        hasAppSecret: !!(process.env.INSTAGRAM_APP_SECRET), // 서버에서만 확인 가능
        redirectUri: `${window.location.origin}/api/auth/callback/instagram`,
        currentOrigin: window.location.origin,
        userAgent: navigator.userAgent,
        popupSupported: !!(window.open)
      }
      
      // 실제 client_id 값 콘솔에 출력 (디버깅용)
      console.log('Environment Debug:', {
        'NEXT_PUBLIC_INSTAGRAM_APP_ID': clientId,
        'CLIENT_ID_LENGTH': clientId.length,
        'ALL_ENV_VARS': Object.keys(process.env).filter(key => key.includes('INSTAGRAM'))
      })
      
      setDebugInfo(info)
      setIsChecking(false)
    }, 1000)
  }

  const testPopup = () => {
    const testPopup = window.open('about:blank', 'test-popup', 'width=400,height=300')
    if (testPopup) {
      setTimeout(() => testPopup.close(), 2000)
      alert('팝업 테스트 성공! 팝업이 정상적으로 열렸습니다.')
    } else {
      alert('팝업 테스트 실패! 브라우저가 팝업을 차단했습니다.')
    }
  }

  return (
    <Card className="w-full max-w-2xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Info className="w-5 h-5" />
          Instagram 연결 디버그 도구
        </CardTitle>
        <CardDescription>
          Instagram 인증 문제를 진단하고 해결하세요
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Button onClick={runDebugCheck} disabled={isChecking} size="sm">
            {isChecking ? '확인 중...' : '환경 확인'}
          </Button>
          <Button onClick={testPopup} variant="outline" size="sm">
            팝업 테스트
          </Button>
        </div>

        {debugInfo && (
          <div className="space-y-3">
            <h4 className="font-semibold">진단 결과</h4>
            
            <div className="grid gap-2">
              <div className="flex items-center justify-between p-2 rounded border">
                <span className="text-sm">Instagram App ID</span>
                <Badge variant={debugInfo.hasAppId ? "default" : "destructive"}>
                  {debugInfo.hasAppId ? (
                    <><CheckCircle className="w-3 h-3 mr-1" />설정됨</>
                  ) : (
                    <><AlertCircle className="w-3 h-3 mr-1" />미설정</>
                  )}
                </Badge>
              </div>

              <div className="flex items-center justify-between p-2 rounded border">
                <span className="text-sm">팝업 지원</span>
                <Badge variant={debugInfo.popupSupported ? "default" : "destructive"}>
                  {debugInfo.popupSupported ? (
                    <><CheckCircle className="w-3 h-3 mr-1" />지원</>
                  ) : (
                    <><AlertCircle className="w-3 h-3 mr-1" />차단됨</>
                  )}
                </Badge>
              </div>

              <div className="p-2 rounded border bg-gray-50">
                <div className="text-xs text-gray-600 space-y-1">
                  <div><strong>Instagram App ID:</strong> {process.env.NEXT_PUBLIC_INSTAGRAM_APP_ID ? 
                    `${(process.env.NEXT_PUBLIC_INSTAGRAM_APP_ID).substring(0, 4)}...` : '❌ 설정 안됨'}</div>
                  <div><strong>리다이렉트 URI:</strong> {debugInfo.redirectUri}</div>
                  <div><strong>현재 도메인:</strong> {debugInfo.currentOrigin}</div>
                  <div><strong>브라우저:</strong> {debugInfo.userAgent.includes('Chrome') ? 'Chrome' : 
                                                debugInfo.userAgent.includes('Firefox') ? 'Firefox' :
                                                debugInfo.userAgent.includes('Safari') ? 'Safari' : 'Other'}</div>
                </div>
              </div>
            </div>

            {!debugInfo.hasAppId && (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  <strong>Instagram App ID가 설정되지 않았습니다.</strong>
                  <br />
                  환경 변수 <code>NEXT_PUBLIC_INSTAGRAM_APP_ID</code>를 설정해주세요.
                </AlertDescription>
              </Alert>
            )}

            {!debugInfo.popupSupported && (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  <strong>팝업이 차단되었습니다.</strong>
                  <br />
                  브라우저 설정에서 이 사이트의 팝업을 허용해주세요.
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}

        <div className="border-t pt-4">
          <h4 className="font-semibold mb-2">일반적인 해결 방법</h4>
          <div className="space-y-2 text-sm text-gray-600">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 mt-0.5 text-orange-500" />
              <div>
                <strong>팝업 차단 해제:</strong>
                <ul className="list-disc list-inside ml-2 mt-1">
                  <li>Chrome: 주소창 오른쪽 팝업 차단 아이콘 클릭</li>
                  <li>Firefox: 주소창 왼쪽 방패 아이콘 클릭</li>
                  <li>Safari: 환경설정 → 웹사이트 → 팝업 창</li>
                </ul>
              </div>
            </div>
            
            <div className="flex items-start gap-2">
              <Info className="w-4 h-4 mt-0.5 text-blue-500" />
              <div>
                <strong>브라우저 캐시 정리:</strong> Ctrl+F5 (Windows) 또는 Cmd+Shift+R (Mac)
              </div>
            </div>
            
            <div className="flex items-start gap-2">
              <ExternalLink className="w-4 h-4 mt-0.5 text-green-500" />
              <div>
                <strong>시크릿/프라이빗 모드:</strong> 확장 프로그램 없이 테스트
              </div>
            </div>
          </div>
        </div>

        <div className="border-t pt-4">
          <h4 className="font-semibold mb-2">Instagram 앱 설정 확인</h4>
          <div className="text-sm text-gray-600 space-y-1">
            <p>Instagram 개발자 계정에서 다음을 확인하세요:</p>
            <ul className="list-disc list-inside ml-4">
              <li>앱 ID와 시크릿이 올바른지 확인</li>
              <li>리다이렉트 URI가 정확히 설정되었는지 확인</li>
              <li>앱이 "Live" 모드인지 확인</li>
              <li>필요한 권한이 승인되었는지 확인</li>
            </ul>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}