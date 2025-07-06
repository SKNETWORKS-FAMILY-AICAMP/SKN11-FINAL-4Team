"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Shield, Clock, Mail, MessageSquare } from "lucide-react"
import { useAuth } from "@/hooks/use-auth"
import PermissionService from "@/lib/services/permission.service"

export default function PermissionRequestPage() {
  const { user } = useAuth()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSubmitted, setIsSubmitted] = useState(false)
  const [requestReason, setRequestReason] = useState("")
  const [contactEmail, setContactEmail] = useState(user?.email || "")

  const handleSubmitRequest = async () => {
    if (!requestReason.trim()) {
      alert("권한 요청 사유를 입력해주세요.")
      return
    }

    if (!contactEmail.trim()) {
      alert("연락처 이메일을 입력해주세요.")
      return
    }

    setIsSubmitting(true)
    
    try {
      await PermissionService.createPermissionRequest({
        reason: requestReason.trim(),
        contactEmail: contactEmail.trim()
      })
      
      setIsSubmitted(true)
    } catch (error) {
      console.error("권한 요청 실패:", error)
      const errorMessage = error instanceof Error ? error.message : "권한 요청 중 오류가 발생했습니다."
      alert(errorMessage + " 다시 시도해주세요.")
    } finally {
      setIsSubmitting(false)
    }
  }

  if (isSubmitted) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
              <Mail className="w-8 h-8 text-green-600" />
            </div>
            <CardTitle className="text-2xl font-bold text-gray-900">
              요청이 제출되었습니다
            </CardTitle>
            <CardDescription>
              권한 요청이 성공적으로 제출되었습니다
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center space-y-4">
            <Alert>
              <Clock className="h-4 w-4" />
              <AlertDescription>
                관리자가 검토한 후 연락드리겠습니다. 일반적으로 1-2 영업일이 소요됩니다.
              </AlertDescription>
            </Alert>
            <div className="text-sm text-gray-600">
              <p>문의사항이 있으시면</p>
              <p className="font-medium">{contactEmail}</p>
              <p>으로 연락 주시기 바랍니다.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <Card className="w-full max-w-2xl">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center">
            <Shield className="w-8 h-8 text-amber-600" />
          </div>
          <CardTitle className="text-2xl font-bold text-gray-900">
            권한 요청이 필요합니다
          </CardTitle>
          <CardDescription>
            현재 기본 팀에 속해 있어 추가 권한이 필요합니다
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <Alert>
            <Shield className="h-4 w-4" />
            <AlertDescription>
              <strong>{user?.teams && user.teams.length > 0 ? user.teams[0].group_name : 'Default'} 팀</strong>은 기본 권한만 가지고 있습니다. 
              AI 모델 생성 및 게시글 작성을 위해서는 추가 권한이 필요합니다.
            </AlertDescription>
          </Alert>

          <div className="space-y-4">
            <div>
              <Label htmlFor="contact-email">연락처 이메일</Label>
              <Input
                id="contact-email"
                type="email"
                value={contactEmail}
                onChange={(e) => setContactEmail(e.target.value)}
                placeholder="연락받을 이메일 주소"
                className="mt-1"
              />
            </div>

            <div>
              <Label htmlFor="request-reason">권한 요청 사유</Label>
              <Textarea
                id="request-reason"
                value={requestReason}
                onChange={(e) => setRequestReason(e.target.value)}
                placeholder="권한이 필요한 이유를 자세히 설명해주세요..."
                className="mt-1 min-h-32"
                maxLength={500}
              />
              <div className="text-sm text-gray-500 mt-1">
                {requestReason.length}/500자
              </div>
            </div>
          </div>

          <div className="bg-gray-50 p-4 rounded-lg">
            <h4 className="font-medium text-gray-900 mb-2">요청할 권한:</h4>
            <ul className="space-y-1 text-sm text-gray-600">
              <li>• AI 모델 생성 및 관리</li>
              <li>• 게시글 작성 및 편집</li>
              <li>• 고급 기능 접근</li>
            </ul>
          </div>

          <div className="flex gap-3">
            <Button
              onClick={handleSubmitRequest}
              disabled={isSubmitting || !requestReason.trim()}
              className="flex-1"
            >
              {isSubmitting ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  권한 요청 중...
                </>
              ) : (
                <>
                  <MessageSquare className="w-4 h-4 mr-2" />
                  권한 요청하기
                </>
              )}
            </Button>
          </div>

          <div className="text-center text-sm text-gray-500">
            <p>관리자가 요청을 검토한 후 연락드리겠습니다.</p>
            <p>긴급한 경우 관리자에게 직접 연락해주세요.</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}