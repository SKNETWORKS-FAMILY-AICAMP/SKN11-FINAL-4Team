"use client"

import { useState } from "react"
import { Navigation } from "@/components/navigation"
import { RequireAuth } from "@/components/auth/protected-route"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { AlertCircle, Send, Clock, CheckCircle, XCircle, Mail, Shield } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"

interface AccessRequest {
  id: string
  requestedGroup: string
  reason: string
  status: "pending" | "approved" | "rejected"
  requestDate: string
  reviewDate?: string
  reviewerNote?: string
}

const availableGroups = [
  { id: "editor", name: "Editor", description: "콘텐츠 편집 권한" },
  { id: "admin", name: "Admin", description: "관리자 권한" },
  { id: "developer", name: "Developer", description: "개발자 권한" },
]

export default function RequestAccessPage() {
  const [selectedGroup, setSelectedGroup] = useState("")
  const [reason, setReason] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitSuccess, setSubmitSuccess] = useState(false)
  
  // 임시 요청 내역 데이터
  const [requests, setRequests] = useState<AccessRequest[]>([
    {
      id: "1",
      requestedGroup: "Editor",
      reason: "콘텐츠 작성 및 편집 업무를 위해 필요합니다.",
      status: "pending",
      requestDate: "2024-06-25",
    },
    {
      id: "2", 
      requestedGroup: "Admin",
      reason: "시스템 관리 업무를 담당하게 되어 권한이 필요합니다.",
      status: "rejected",
      requestDate: "2024-06-20",
      reviewDate: "2024-06-22",
      reviewerNote: "추가 승인 절차가 필요합니다.",
    },
  ])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedGroup || !reason.trim()) return

    setIsSubmitting(true)
    
    // 실제 API 호출 대신 시뮬레이션
    setTimeout(() => {
      const newRequest: AccessRequest = {
        id: Date.now().toString(),
        requestedGroup: availableGroups.find(g => g.id === selectedGroup)?.name || selectedGroup,
        reason: reason.trim(),
        status: "pending",
        requestDate: new Date().toISOString().split('T')[0],
      }
      
      setRequests(prev => [newRequest, ...prev])
      setSelectedGroup("")
      setReason("")
      setIsSubmitting(false)
      setSubmitSuccess(true)
      
      // 성공 메시지 자동 숨김
      setTimeout(() => setSubmitSuccess(false), 3000)
    }, 1000)
  }

  const getStatusIcon = (status: AccessRequest["status"]) => {
    switch (status) {
      case "pending":
        return <Clock className="h-4 w-4 text-yellow-500" />
      case "approved":
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case "rejected":
        return <XCircle className="h-4 w-4 text-red-500" />
    }
  }

  const getStatusBadge = (status: AccessRequest["status"]) => {
    switch (status) {
      case "pending":
        return <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">대기중</Badge>
      case "approved":
        return <Badge variant="secondary" className="bg-green-100 text-green-800">승인됨</Badge>
      case "rejected":
        return <Badge variant="secondary" className="bg-red-100 text-red-800">거부됨</Badge>
    }
  }

  return (
    <RequireAuth>
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">권한 요청</h1>
            <p className="text-gray-600 mt-2">추가 권한이 필요한 경우 요청을 제출하세요</p>
          </div>

          {submitSuccess && (
            <Alert className="mb-6 border-green-200 bg-green-50">
              <CheckCircle className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800">
                권한 요청이 성공적으로 제출되었습니다. 관리자 검토 후 결과를 알려드리겠습니다.
              </AlertDescription>
            </Alert>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* 권한 요청 폼 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-5 w-5 text-blue-600" />
                  새 권한 요청
                </CardTitle>
                <CardDescription>
                  필요한 권한 그룹을 선택하고 요청 사유를 작성해주세요
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <Label htmlFor="group">요청할 권한 그룹</Label>
                    <Select value={selectedGroup} onValueChange={setSelectedGroup}>
                      <SelectTrigger>
                        <SelectValue placeholder="권한 그룹을 선택하세요" />
                      </SelectTrigger>
                      <SelectContent>
                        {availableGroups.map(group => (
                          <SelectItem key={group.id} value={group.id}>
                            <div className="flex flex-col">
                              <span className="font-medium">{group.name}</span>
                              <span className="text-sm text-gray-500">{group.description}</span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div>
                    <Label htmlFor="reason">요청 사유</Label>
                    <Textarea
                      id="reason"
                      placeholder="권한이 필요한 구체적인 사유를 작성해주세요..."
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      rows={4}
                      className="resize-none"
                    />
                  </div>

                  <Alert>
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      요청 제출 후 관리자의 검토를 거쳐 승인 여부가 결정됩니다. 
                      보통 1-2 영업일 내에 결과를 안내드립니다.
                    </AlertDescription>
                  </Alert>

                  <Button 
                    type="submit" 
                    className="w-full" 
                    disabled={!selectedGroup || !reason.trim() || isSubmitting}
                  >
                    {isSubmitting ? (
                      <>검토 중...</>
                    ) : (
                      <>
                        <Send className="h-4 w-4 mr-2" />
                        권한 요청 제출
                      </>
                    )}
                  </Button>
                </form>
              </CardContent>
            </Card>

            {/* 요청 내역 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Mail className="h-5 w-5 text-gray-600" />
                  요청 내역
                </CardTitle>
                <CardDescription>
                  제출한 권한 요청의 현재 상태를 확인할 수 있습니다
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {requests.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <Mail className="h-12 w-12 mx-auto mb-3 opacity-50" />
                    <p>아직 제출한 요청이 없습니다.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {requests.map(request => (
                      <div key={request.id} className="border rounded-lg p-4 bg-white">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            {getStatusIcon(request.status)}
                            <span className="font-medium">{request.requestedGroup}</span>
                          </div>
                          {getStatusBadge(request.status)}
                        </div>
                        
                        <p className="text-sm text-gray-600 mb-3">{request.reason}</p>
                        
                        <div className="text-xs text-gray-500 space-y-1">
                          <div>요청일: {request.requestDate}</div>
                          {request.reviewDate && (
                            <div>검토일: {request.reviewDate}</div>
                          )}
                          {request.reviewerNote && (
                            <div className="mt-2 p-2 bg-gray-50 rounded text-gray-700">
                              <strong>관리자 메모:</strong> {request.reviewerNote}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </RequireAuth>
  )
}