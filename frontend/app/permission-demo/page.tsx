"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Shield, User, Users, Zap } from "lucide-react"
import { useAuth, useTeamPermission } from "@/hooks/use-auth"
import PermissionGuard, { ModelCreationGuard, PostCreationGuard } from "@/components/auth/permission-guard"

export default function PermissionDemoPage() {
  const { user, isDefaultTeam, requiresPermissionRequest } = useAuth()
  const teamPermission = useTeamPermission()

  return (
    <PermissionGuard>
      <div className="container mx-auto p-6 space-y-6">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">팀 권한 시스템 데모</h1>
          <p className="text-gray-600">현재 사용자의 팀과 권한을 확인해보세요</p>
        </div>

        {/* 사용자 정보 카드 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="w-5 h-5" />
              사용자 정보
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-600">이름</p>
                <p className="font-medium">{user?.name || user?.user_name}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">이메일</p>
                <p className="font-medium">{user?.email}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">팀</p>
                <div className="flex items-center gap-2">
                  <Badge variant={user?.teams?.length === 0 ? "destructive" : "default"}>
                    {user?.teams && user.teams.length > 0 ? user.teams[0].group_name : 'Default'}
                  </Badge>
                  {user?.teams?.length === 0 && (
                    <span className="text-sm text-red-600">(권한 제한)</span>
                  )}
                </div>
              </div>
              <div>
                <p className="text-sm text-gray-600">팀 목록</p>
                <div className="flex gap-1">
                  {user?.teams?.map(team => (
                    <Badge key={team.group_id} variant="outline">
                      {team.group_name}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 권한 상태 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="w-5 h-5" />
              권한 상태
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {requiresPermissionRequest() && (
              <Alert>
                <Shield className="h-4 w-4" />
                <AlertDescription>
                  현재 기본 팀에 속해있어 추가 권한이 필요합니다.
                </AlertDescription>
              </Alert>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 border rounded-lg">
                <h4 className="font-medium mb-2">모델 생성</h4>
                <Badge variant={teamPermission.canCreateModel() ? "default" : "destructive"}>
                  {teamPermission.canCreateModel() ? "허용됨" : "제한됨"}
                </Badge>
              </div>
              <div className="p-4 border rounded-lg">
                <h4 className="font-medium mb-2">게시글 작성</h4>
                <Badge variant={teamPermission.canCreatePost() ? "default" : "destructive"}>
                  {teamPermission.canCreatePost() ? "허용됨" : "제한됨"}
                </Badge>
              </div>
              <div className="p-4 border rounded-lg">
                <h4 className="font-medium mb-2">콘텐츠 관리</h4>
                <Badge variant={teamPermission.canManageContent() ? "default" : "destructive"}>
                  {teamPermission.canManageContent() ? "허용됨" : "제한됨"}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 기능 테스트 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>모델 생성 기능</CardTitle>
              <CardDescription>
                권한이 있는 사용자만 접근 가능
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ModelCreationGuard
                fallback={
                  <div className="text-center p-4 text-gray-500">
                    <Shield className="w-12 h-12 mx-auto mb-2 text-gray-400" />
                    <p>모델 생성 권한이 없습니다</p>
                  </div>
                }
              >
                <div className="text-center p-4">
                  <Zap className="w-12 h-12 mx-auto mb-2 text-green-600" />
                  <p className="text-green-600 font-medium">모델 생성 가능!</p>
                  <Button className="mt-2">새 모델 만들기</Button>
                </div>
              </ModelCreationGuard>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>게시글 작성 기능</CardTitle>
              <CardDescription>
                권한이 있는 사용자만 접근 가능
              </CardDescription>
            </CardHeader>
            <CardContent>
              <PostCreationGuard
                fallback={
                  <div className="text-center p-4 text-gray-500">
                    <Shield className="w-12 h-12 mx-auto mb-2 text-gray-400" />
                    <p>게시글 작성 권한이 없습니다</p>
                  </div>
                }
              >
                <div className="text-center p-4">
                  <Zap className="w-12 h-12 mx-auto mb-2 text-blue-600" />
                  <p className="text-blue-600 font-medium">게시글 작성 가능!</p>
                  <Button className="mt-2">새 게시글 작성</Button>
                </div>
              </PostCreationGuard>
            </CardContent>
          </Card>
        </div>
      </div>
    </PermissionGuard>
  )
}