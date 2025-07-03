"use client"

import { useState, useEffect } from "react"
import { Navigation } from "@/components/navigation"
import { RequireAdmin } from "@/components/auth/protected-route"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { User, Save, ShieldCheck, ShieldX, Plus, Trash2, Users, Eye, EyeOff, Key, Loader2 } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogCancel, AlertDialogAction } from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { AdminService, type AdminTeam, type AdminUser, type AdminHFToken, type AdminCreateHFTokenRequest } from "@/lib/services/admin.service"

export default function AdministratorPage() {
  const [teams, setTeams] = useState<AdminTeam[]>([])
  const [allUsers, setAllUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null)
  const [newGroupName, setNewGroupName] = useState("")
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [dragUserId, setDragUserId] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState("")
  const [dragOverBox, setDragOverBox] = useState<string | null>(null)
  
  // HF Token 관련 상태들
  const [hfTokens, setHfTokens] = useState<AdminHFToken[]>([])
  const [loadingTokens, setLoadingTokens] = useState(false)
  const [inputToken, setInputToken] = useState("")
  const [inputAlias, setInputAlias] = useState("")
  const [inputUsername, setInputUsername] = useState("")
  const [selectedTeamForToken, setSelectedTeamForToken] = useState<number | null>(null)
  const [creatingToken, setCreatingToken] = useState(false)
  const [dragTokenId, setDragTokenId] = useState<string | null>(null)
  const [dragOverTokenBox, setDragOverTokenBox] = useState<string | null>(null)
  const [selectedTokenDetail, setSelectedTokenDetail] = useState<AdminHFToken | null>(null)
  const [isTokenDetailOpen, setIsTokenDetailOpen] = useState(false)

  // API에서 데이터 로드
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const [teamsData, usersData] = await Promise.all([
          AdminService.getTeams(),
          AdminService.getUsers()
        ])
        
        console.log('Teams data:', teamsData)
        console.log('Users data:', usersData)
        
        setTeams(teamsData)
        setAllUsers(usersData)
        setSelectedGroupId(teamsData[0]?.group_id || null)
      } catch (err: any) {
        console.error('Error loading data:', err)
        setError(err.message || '데이터를 불러오는데 실패했습니다.')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  // HF 토큰 탭이 선택될 때 토큰 데이터 로드
  useEffect(() => {
    fetchHFTokens()
  }, [])

  // HF 토큰 데이터 로드
  const fetchHFTokens = async () => {
    try {
      setLoadingTokens(true)
      const tokensData = await AdminService.getHFTokens({ include_assigned: true })
      console.log('HF Tokens data:', tokensData)
      setHfTokens(tokensData)
    } catch (err: any) {
      console.error('Error loading HF tokens:', err)
      setError(err.message || 'HF 토큰을 불러오는데 실패했습니다.')
    } finally {
      setLoadingTokens(false)
    }
  }

  // HF 토큰 생성
  const handleCreateHFToken = async () => {
    if (!inputAlias.trim() || !inputToken.trim() || !inputUsername.trim()) return

    try {
      setCreatingToken(true)
      
      const tokenData: AdminCreateHFTokenRequest = {
        hf_token_value: inputToken.trim(),
        hf_token_nickname: inputAlias.trim(),
        hf_user_name: inputUsername.trim(),
        assign_to_team_id: selectedTeamForToken || null
      }

      const newToken = await AdminService.createHFToken(tokenData)
      console.log('Token created:', newToken)
      
      // 토큰 목록 새로고침
      await fetchHFTokens()
      
      // 입력 필드 초기화
      setInputAlias("")
      setInputToken("")
      setInputUsername("")
      setSelectedTeamForToken(null)
      
      // 성공 메시지 (선택사항)
      console.log('HF 토큰이 성공적으로 생성되었습니다.')
      
    } catch (err: any) {
      console.error('Error creating HF token:', err)
      setError(err.message || 'HF 토큰 생성에 실패했습니다.')
    } finally {
      setCreatingToken(false)
    }
  }

  // 그룹 추가
  const groupNameExists = teams.some(t => t.group_name === newGroupName.trim());
  const handleAddGroup = async () => {
    if (!newGroupName.trim() || groupNameExists) return;
    
    try {
      const newTeam = await AdminService.createTeam({
        group_name: newGroupName.trim(),
        group_description: ""
      })
      setTeams(prev => [...prev, newTeam])
      setNewGroupName("")
    } catch (err: any) {
      console.error('Failed to create team:', err)
      setError('팀 생성에 실패했습니다.')
    }
  }

  // 그룹 삭제
  const handleDeleteGroup = async (groupId: number) => {
    try {
      await AdminService.deleteTeam(groupId)
      setTeams(prev => prev.filter(t => t.group_id !== groupId))
      if (selectedGroupId === groupId) {
        setSelectedGroupId(teams.find(t => t.group_id !== groupId)?.group_id || null)
      }
    } catch (err: any) {
      console.error('Failed to delete team:', err)
      setError('팀 삭제에 실패했습니다.')
    }
  }

  // 그룹 모달 열기/닫기
  const openGroupModal = (groupId: number) => {
    setSelectedGroupId(groupId)
    setIsModalOpen(true)
  }
  const closeGroupModal = () => {
    setIsModalOpen(false)
    setSelectedGroupId(null)
  }

  // 드래그앤드롭 로직
  const handleDragStart = (userId: string) => {
    setDragUserId(userId)
    // 드래그 중에도 스크롤 가능하도록 설정
    document.body.style.overflow = 'auto'
    document.body.style.userSelect = 'none'
    
    // 드래그 중 스크롤을 방해하지 않도록 설정
    const handleDrag = (e: DragEvent) => {
      e.preventDefault()
      // 드래그 중에도 스크롤 허용
      document.body.style.overflow = 'auto'
    }
    
    document.addEventListener('drag', handleDrag)
    
    // 드래그 종료 시 이벤트 리스너 제거
    const cleanup = () => {
      document.removeEventListener('drag', handleDrag)
      document.body.style.overflow = ''
      document.body.style.userSelect = ''
    }
    
    // 드래그 종료 시 정리
    document.addEventListener('dragend', cleanup, { once: true })
  }
  
  const handleDropToGroup = async () => {
    if (dragUserId && selectedGroupId) {
      try {
        // 현재 사용자가 속한 팀들 찾기
        const currentTeams = teams.filter(t => 
          t.users.some(u => u.user_id === dragUserId)
        )
        
        // 이미 해당 팀에 속해있는지 확인
        const alreadyInTargetTeam = currentTeams.some(t => t.group_id === selectedGroupId)
        
        if (!alreadyInTargetTeam) {
          // 다른 팀들에서 제거
          for (const team of currentTeams) {
            await AdminService.removeUserFromTeam(team.group_id, dragUserId)
          }
          
          // 새 팀에 추가
          await AdminService.addUserToTeam(selectedGroupId, dragUserId)
          
          // 상태 업데이트
          const [updatedTeams, updatedUsers] = await Promise.all([
            AdminService.getTeams(),
            AdminService.getUsers()
          ])
          setTeams(updatedTeams)
          setAllUsers(updatedUsers)
        }
      } catch (err: any) {
        console.error('Failed to move user:', err)
        setError('사용자 이동에 실패했습니다.')
      }
    }
    setDragUserId(null);
    setSelectedGroupId(null);
  }
  
  const handleDropToAll = async () => {
    if (dragUserId) {
      try {
        // 사용자가 속한 모든 팀에서 제거
        const userTeams = teams.filter(t => 
          t.users?.some(u => u.user_id === dragUserId)
        )
        
        for (const team of userTeams) {
          await AdminService.removeUserFromTeam(team.group_id, dragUserId)
        }
        
        // 상태 업데이트
        const [updatedTeams] = await Promise.all([AdminService.getTeams()])
        setTeams(updatedTeams)
      } catch (err: any) {
        console.error('Failed to remove user from teams:', err)
        setError('사용자 제거에 실패했습니다.')
      }
    }
    setDragUserId(null)
    setSelectedGroupId(null)
  }

  const handleDragEnd = () => {
    setDragUserId(null)
    document.body.style.overflow = ''
    document.body.style.userSelect = ''
  }

  // 그룹/사용자 정보
  const selectedTeam = teams.find(t => t.group_id === selectedGroupId)
  const teamUsers = selectedTeam?.users || []
  
  // 어떤 팀에도 속하지 않은 사용자들 필터링
  const assignedUserIds = new Set<string>()
  teams.forEach(team => {
    team.users.forEach(user => {
      assignedUserIds.add(user.user_id)
    })
  })
  const otherUsers = allUsers.filter(u => !assignedUserIds.has(u.user_id))

  const aliasExists = hfTokens.some(t => t.hf_token_nickname === inputAlias.trim());
  const usernameExists = hfTokens.some(t => t.hf_user_name === inputUsername.trim());

  return (
    <RequireAdmin>
      <div className="min-h-screen bg-gray-50" style={{ 
        overflow: 'auto', 
        overscrollBehavior: 'contain',
        scrollBehavior: 'smooth'
      }}>
        <Navigation />

        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">관리자 설정</h1>
            <p className="text-gray-600 mt-2">시스템 설정을 관리하세요</p>
          </div>

          {/* 로딩 상태 */}
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <p className="text-gray-600">데이터를 불러오는 중...</p>
              </div>
            </div>
          )}

          {/* 에러 상태 */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-center space-x-2">
                <ShieldX className="h-5 w-5 text-red-600" />
                <span className="text-red-800 font-medium">오류 발생</span>
              </div>
              <p className="text-red-700 mt-1">{error}</p>
              <Button 
                variant="outline" 
                size="sm" 
                className="mt-2"
                onClick={() => window.location.reload()}
              >
                다시 시도
              </Button>
            </div>
          )}

          {/* 메인 콘텐츠 */}
          {!loading && !error && (
            <>
              <Tabs defaultValue="group" className="w-full">
                <TabsList className="mb-6">
                  <TabsTrigger value="group">권한 그룹 관리</TabsTrigger>
                  <TabsTrigger value="hf">허깅페이스 토큰 관리</TabsTrigger>
                </TabsList>
                <TabsContent value="group">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Users className="h-5 w-5 text-blue-600" />
                        권한 그룹 관리
                      </CardTitle>
                      <CardDescription>
                        사용자를 드래그하여 그룹에 추가하거나 제거할 수 있습니다.
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      {/* 새 그룹 추가 섹션 */}
                      <div className="mb-6 pb-6 border-b">
                        <h4 className="font-medium text-gray-900 mb-4">새 그룹 추가</h4>
                        <div className="flex gap-3 items-end">
                          <div className="flex-1 max-w-xs">
                            <Label htmlFor="new-group-name">그룹 이름</Label>
                            <Input
                              id="new-group-name"
                              placeholder="예: 마케터, 개발자"
                              value={newGroupName}
                              onChange={e => setNewGroupName(e.target.value)}
                            />
                          </div>
                          <Button onClick={handleAddGroup} disabled={!newGroupName.trim() || groupNameExists} className="bg-blue-600 hover:bg-blue-700 text-white">
                            <Plus className="h-4 w-4 mr-1" />
                            그룹 추가
                          </Button>
                        </div>
                        {groupNameExists && (
                          <div className="text-xs text-red-600 mt-1">이미 사용 중인 그룹 이름입니다.</div>
                        )}
                      </div>
                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* 전체 사용자 목록 */}
                        <Card 
                          className={`shadow-sm transition-all ${
                            dragOverBox === 'all' ? 'bg-green-50 border-green-300 shadow-md' : ''
                          }`}
                          onDragOver={e => { 
                            e.preventDefault(); 
                            e.stopPropagation();
                            setDragOverBox('all'); 
                          }}
                          onDragLeave={(e) => {
                            if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                              setDragOverBox(null);
                            }
                          }}
                          onDrop={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            handleDropToAll();
                            setDragOverBox(null);
                          }}
                        >
                          <CardHeader className="pb-3">
                            <CardTitle className="text-base font-semibold flex items-center gap-2">
                              <Users className="h-4 w-4" />
                              전체 사용자
                            </CardTitle>
                          </CardHeader>
                          <CardContent 
                            className={`transition-colors`}
                            style={{ 
                              minHeight: '300px',
                              position: 'relative'
                            }}
                          >
                            <Input
                              placeholder="이름 또는 이메일로 검색"
                              className="mb-3"
                              value={searchTerm}
                              onChange={e => setSearchTerm(e.target.value)}
                            />
                            <div className="space-y-2 overflow-y-auto" style={{ scrollBehavior: 'smooth', overscrollBehavior: 'contain' }}>
                              {otherUsers
                                .filter(user => 
                                  user.user_name.includes(searchTerm) || user.email.includes(searchTerm)
                                )
                                .map(user => (
                                <div
                                  key={user.user_id}
                                  className={`flex items-center gap-3 p-4 rounded-lg transition-all w-full min-h-[70px] ${
                                    dragUserId === user.user_id 
                                      ? 'opacity-50 transform scale-95 bg-blue-100' 
                                      : 'hover:bg-gray-50 hover:shadow-sm'
                                  }`}
                                  draggable
                                  onDragStart={() => handleDragStart(user.user_id)}
                                  onDragEnd={handleDragEnd}
                                  onDrag={(e) => {
                                    // 드래그 중에도 스크롤 허용
                                    e.preventDefault()
                                    document.body.style.overflow = 'auto'
                                  }}
                                  style={{ 
                                    cursor: dragUserId === user.user_id ? 'grabbing' : 'grab',
                                    touchAction: 'pan-y',
                                    userSelect: 'none',
                                    WebkitUserSelect: 'none',
                                    MozUserSelect: 'none',
                                    msUserSelect: 'none',
                                    pointerEvents: 'auto'
                                  }}
                                >
                                  <Avatar className="h-8 w-8 flex-shrink-0">
                                    <AvatarFallback className="bg-gray-200 text-gray-600 text-xs">
                                      {user.user_name.charAt(0)}
                                    </AvatarFallback>
                                  </Avatar>
                                  <div className="flex-1 min-w-0 flex flex-col justify-center">
                                    <p className="font-medium text-sm truncate">{user.user_name}</p>
                                    <p className="text-xs text-gray-500 truncate">{user.email}</p>
                                  </div>
                                  <div className="text-gray-400 flex-shrink-0">
                                    <User className="h-4 w-4" />
                                  </div>
                                </div>
                              ))}
                              {otherUsers
                                .filter(user => 
                                  user.user_name.includes(searchTerm) || user.email.includes(searchTerm)
                                ).length === 0 && (
                                  <div className="text-center py-8 text-gray-500">
                                    <Users className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                    <p className="text-sm">할당되지 않은 사용자가 없습니다.</p>
                                  </div>
                                )}
                            </div>
                          </CardContent>
                        </Card>

                        {/* 권한 그룹들 */}
                        <div className="lg:col-span-2 space-y-4">
                          {teams.map(team => (
                            <Card 
                              key={team.group_id} 
                              className={`shadow-sm transition-all ${
                                dragOverBox === `group-${team.group_id}` ? 'bg-green-50 border-green-300 shadow-md' : ''
                              }`}
                              onDragOver={e => { 
                                e.preventDefault(); 
                                setDragOverBox(`group-${team.group_id}`); 
                                setSelectedGroupId(team.group_id);
                              }}
                              onDragLeave={() => setDragOverBox(null)}
                              onDrop={() => {
                                handleDropToGroup();
                                setDragOverBox(null);
                              }}
                            >
                              <CardHeader className="pb-3">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-3">
                                    <div className={`w-3 h-3 rounded-full ${
                                      team.group_id === 0 ? 'bg-red-500' :
                                      team.group_name === 'Editor' ? 'bg-blue-500' : 'bg-green-500'
                                    }`}></div>
                                      <div>
                                        <CardTitle className="text-base font-semibold">{team.group_name}</CardTitle>
                                        <p className="text-sm text-gray-500">
                                          {team.group_description || `${team.users?.length || 0}명의 사용자`}
                                        </p>
                                      </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                      <Badge variant="secondary" className="text-xs">
                                        {team.users?.length || 0}명
                                      </Badge>
                                      {team.group_id !== 0 && (
                                        <Button 
                                          size="icon" 
                                          variant="ghost" 
                                          onClick={() => handleDeleteGroup(team.group_id)}
                                          className="h-8 w-8"
                                        >
                                          <Trash2 className="h-4 w-4 text-red-500" />
                                        </Button>
                                      )}
                                    </div>
                                  </div>
                                </CardHeader>
                                <CardContent
                                  className={`min-h-[120px] transition-colors`}
                                >
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                    {(team.users || []).map(user => (
                                      <div
                                        key={user.user_id}
                                        className={`flex items-center gap-2 p-3 rounded-lg transition-all w-full h-full min-h-[50px] ${
                                          dragUserId === user.user_id 
                                            ? 'opacity-50 transform scale-95 bg-blue-100' 
                                            : 'hover:bg-white hover:shadow-sm border border-gray-100'
                                        }`}
                                        draggable
                                        onDragStart={() => {
                                          handleDragStart(user.user_id);
                                          setSelectedGroupId(team.group_id);
                                        }}
                                        onDragEnd={handleDragEnd}
                                        onDrag={(e) => {
                                          // 드래그 중에도 스크롤 허용
                                          e.preventDefault()
                                          document.body.style.overflow = 'auto'
                                        }}
                                        style={{ 
                                          cursor: dragUserId === user.user_id ? 'grabbing' : 'grab',
                                          touchAction: 'pan-y',
                                          userSelect: 'none',
                                          WebkitUserSelect: 'none',
                                          MozUserSelect: 'none',
                                          msUserSelect: 'none',
                                          pointerEvents: 'auto'
                                        }}
                                      >
                                        <Avatar className="h-6 w-6 flex-shrink-0">
                                          <AvatarFallback className="bg-blue-100 text-blue-600 text-xs">
                                            {user.user_name.charAt(0)}
                                          </AvatarFallback>
                                        </Avatar>
                                        <div className="flex-1 min-w-0 flex flex-col justify-center">
                                          <p className="font-medium text-xs truncate">{user.user_name}</p>
                                          <p className="text-xs text-gray-500 truncate">{user.email}</p>
                                        </div>
                                      </div>
                                    ))}
                                    {(!team.users || team.users.length === 0) && (
                                      <div className="col-span-2 text-center py-4 text-gray-400 border-2 border-dashed border-gray-200 rounded-lg">
                                        <p className="text-sm">사용자를 여기에 드래그하세요</p>
                                      </div>
                                    )}
                                  </div>
                                </CardContent>
                              </Card>
                            ))}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>
                <TabsContent value="hf">
                  <Card className="mb-0">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Key className="h-5 w-5 text-yellow-600" />
                        허깅페이스 토큰 관리
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      {/* 새 토큰 추가 섹션 */}
                      <div className="mb-6 pb-6 border-b">
                        <h4 className="font-medium text-gray-900 mb-4">새 토큰 추가</h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 items-end">
                          <div>
                            <Label htmlFor="new-token-alias">별칭</Label>
                            <Input
                              id="new-token-alias"
                              placeholder="예: 서비스용, 개발용"
                              value={inputAlias}
                              onChange={e => setInputAlias(e.target.value)}
                              disabled={creatingToken}
                            />
                          </div>
                          <div>
                            <Label htmlFor="new-token-username">허깅페이스 사용자명</Label>
                            <Input
                              id="new-token-username"
                              placeholder="허깅페이스 계정명"
                              value={inputUsername}
                              onChange={e => setInputUsername(e.target.value)}
                              disabled={creatingToken}
                            />
                          </div>
                          <div>
                            <Label htmlFor="new-token-value">토큰</Label>
                            <Input
                              id="new-token-value"
                              type="password"
                              placeholder="hf_..."
                              value={inputToken}
                              onChange={e => setInputToken(e.target.value)}
                              disabled={creatingToken}
                            />
                          </div>
                          <div>
                            <Label htmlFor="team-select">팀 할당 (선택사항)</Label>
                            <select
                              id="team-select"
                              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                              value={selectedTeamForToken || ""}
                              onChange={e => setSelectedTeamForToken(e.target.value ? Number(e.target.value) : null)}
                              disabled={creatingToken}
                            >
                              <option value="">할당하지 않음</option>
                              {teams.map(team => (
                                <option key={team.group_id} value={team.group_id}>
                                  {team.group_name}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>
                        <div className="flex justify-end mt-4">
                          <Button
                            onClick={handleCreateHFToken}
                            disabled={!inputAlias.trim() || !inputToken.trim() || !inputUsername.trim() || aliasExists || creatingToken}
                            className="bg-blue-600 hover:bg-blue-700 text-white"
                          >
                            {creatingToken ? (
                              <>
                                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                                생성 중...
                              </>
                            ) : (
                              <>
                                <Plus className="h-4 w-4 mr-1" />
                                토큰 생성
                              </>
                            )}
                          </Button>
                        </div>
                        {aliasExists && (
                          <div className="text-xs text-red-600 mt-1">이미 사용 중인 별칭입니다.</div>
                        )}
                        {usernameExists && (
                          <div className="text-xs text-red-600 mt-1">이미 등록된 사용자명입니다.</div>
                        )}
                      </div>
                      {/* 토큰 리스트 */}
                      {loadingTokens ? (
                        <div className="flex items-center justify-center py-12">
                          <div className="text-center">
                            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-blue-600" />
                            <p className="text-gray-600">토큰을 불러오는 중...</p>
                          </div>
                        </div>
                      ) : hfTokens.length === 0 ? (
                        <div className="text-center py-8 text-gray-400">
                          <Key className="h-8 w-8 mx-auto mb-2 opacity-50" />
                          <p className="text-sm">등록된 토큰이 없습니다. 새 토큰을 추가해보세요.</p>
                        </div>
                      ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                          {/* 할당되지 않은 토큰들 */}
                          <Card className={`shadow-sm transition-all ${dragOverTokenBox === 'unassigned-tokens' ? 'bg-green-50 border-green-300 shadow-md' : ''}`}>
                            <CardHeader className="pb-3">
                              <CardTitle className="text-base font-semibold flex items-center gap-2">
                                <Key className="h-4 w-4 text-yellow-600" />
                                할당되지 않은 토큰 ({hfTokens.filter(t => !t.group_id).length})
                              </CardTitle>
                            </CardHeader>
                            <CardContent className="transition-colors" style={{ minHeight: '200px' }}>
                              <div className="text-xs text-gray-500 mb-2">
                                토큰을 <span className="font-semibold text-blue-600">클릭</span>하여 상세 정보를 확인하세요.
                              </div>
                              <div className="space-y-2 overflow-y-auto mt-4">
                                {hfTokens
                                  .filter(token => !token.group_id)
                                  .map((token) => (
                                    <div
                                      key={token.hf_manage_id}
                                      className="flex items-center gap-3 p-4 rounded-lg transition-all w-full min-h-[50px] bg-yellow-50 border border-yellow-200 hover:bg-yellow-100 cursor-pointer"
                                      onClick={() => {
                                        setSelectedTokenDetail(token);
                                        setIsTokenDetailOpen(true);
                                      }}
                                    >
                                      <div className="flex-1">
                                        <div className="font-medium text-yellow-800">{token.hf_token_nickname}</div>
                                        <div className="text-xs text-gray-500">사용자: {token.hf_user_name}</div>
                                        {token.hf_token_masked && (
                                          <div className="text-xs text-gray-400">{token.hf_token_masked}</div>
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                {hfTokens.filter(t => !t.group_id).length === 0 && (
                                  <div className="text-center py-4 text-gray-400">
                                    <p className="text-sm">할당되지 않은 토큰이 없습니다.</p>
                                  </div>
                                )}
                              </div>
                            </CardContent>
                          </Card>

                          {/* 팀별 할당된 토큰들 */}
                          <div className="lg:col-span-2 space-y-4">
                            {teams.map(team => {
                              const teamTokens = hfTokens.filter(t => t.group_id === team.group_id)
                              if (teamTokens.length === 0) return null
                              
                              return (
                                <Card key={team.group_id} className="shadow-sm">
                                  <CardHeader className="pb-3">
                                    <CardTitle className="text-base font-semibold flex items-center gap-2">
                                      <div className={`w-3 h-3 rounded-full ${
                                        team.group_id === 1 ? 'bg-red-500' : 'bg-green-500'
                                      }`}></div>
                                      {team.group_name} ({teamTokens.length}개 토큰)
                                    </CardTitle>
                                  </CardHeader>
                                  <CardContent>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                      {teamTokens.map((token) => (
                                        <div
                                          key={token.hf_manage_id}
                                          className="flex items-center gap-2 p-3 rounded-lg bg-blue-50 border border-blue-200 hover:bg-blue-100 cursor-pointer"
                                          onClick={() => {
                                            setSelectedTokenDetail(token);
                                            setIsTokenDetailOpen(true);
                                          }}
                                        >
                                          <div className="flex-1">
                                            <div className="font-medium text-blue-800 text-sm">{token.hf_token_nickname}</div>
                                            <div className="text-xs text-gray-500">{token.hf_user_name}</div>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </CardContent>
                                </Card>
                              )
                            })}
                            
                            {hfTokens.filter(t => t.group_id).length === 0 && (
                              <div className="text-center py-8 text-gray-400">
                                <Key className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                <p className="text-sm">팀에 할당된 토큰이 없습니다.</p>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>
              </Tabs>
              <div className="h-8" />
              {/* 그룹 상세/사용자 관리 (모달로 이동) */}
              <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
                <DialogContent className="max-w-3xl">
                  <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                      <ShieldCheck className="h-5 w-5 text-blue-600" />
                      {selectedTeam?.group_name} 그룹 사용자 관리
                    </DialogTitle>
                  </DialogHeader>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8 py-4">
                    {/* 전체 사용자 목록 */}
                    <Card className="shadow-none border bg-white">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base font-semibold">전체 사용자</CardTitle>
                      </CardHeader>
                      <CardContent
                        className="pt-0"
                        style={{ minHeight: 280 }}
                        onDragOver={e => { e.preventDefault(); setDragOverBox('all'); }}
                        onDragLeave={() => setDragOverBox(null)}
                        onDrop={handleDropToAll}
                      >
                        <Input
                          placeholder="이름 또는 이메일로 검색"
                          className="mb-3"
                          value={searchTerm}
                          onChange={e => setSearchTerm(e.target.value)}
                        />
                        <ul className="divide-y max-h-60 overflow-y-auto rounded">
                          {otherUsers.filter(user =>
                            user.user_name.includes(searchTerm) || user.email.includes(searchTerm)
                          ).map(user => (
                            <li
                              key={user.user_id}
                              className={`flex items-center gap-3 py-3 px-3 rounded transition-shadow bg-white w-full h-full min-h-[50px] hover:bg-gray-50`}
                              draggable
                              onDragStart={() => handleDragStart(user.user_id)}
                              onDragEnd={handleDragEnd}
                              onDrag={(e) => {
                                        // 드래그 중에도 스크롤 허용
                                        e.preventDefault()
                                        document.body.style.overflow = 'auto'
                                      }}
                                      style={{ 
                                        cursor: dragUserId === user.user_id ? 'grabbing' : 'grab',
                                        touchAction: 'pan-y',
                                        userSelect: 'none',
                                        WebkitUserSelect: 'none',
                                        MozUserSelect: 'none',
                                        msUserSelect: 'none',
                                        pointerEvents: 'auto'
                                      }}
                            >
                              <User className="h-4 w-4 text-gray-500 flex-shrink-0" />
                              <div className="flex-1 min-w-0 flex flex-col justify-center">
                                <span className="font-medium">{user.user_name}</span>
                                <span className="text-xs text-gray-500">{user.email}</span>
                              </div>
                            </li>
                          ))}
                          {otherUsers.filter(user =>
                            user.user_name.includes(searchTerm) || user.email.includes(searchTerm)
                          ).length === 0 && (
                            <li className="text-sm text-gray-400 py-4 text-center">추가 가능한 사용자가 없습니다.</li>
                          )}
                        </ul>
                      </CardContent>
                    </Card>
                    {/* 그룹 사용자 목록 */}
                    <Card className="shadow-none border bg-white">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base font-semibold">그룹 내 사용자</CardTitle>
                      </CardHeader>
                      <CardContent
                        className="pt-0"
                        style={{ minHeight: 280 }}
                        onDragOver={e => { e.preventDefault(); setDragOverBox('group'); }}
                        onDragLeave={() => setDragOverBox(null)}
                        onDrop={handleDropToGroup}
                      >
                        <ul className="divide-y max-h-60 overflow-y-auto rounded">
                          {teamUsers.map(user => (
                            <li
                              key={user.user_id}
                              className={`flex items-center gap-3 py-3 px-3 rounded transition-shadow bg-white w-full h-full min-h-[50px] hover:bg-gray-50`}
                              draggable
                              onDragStart={() => handleDragStart(user.user_id)}
                              onDragEnd={handleDragEnd}
                              onDrag={(e) => {
                                        // 드래그 중에도 스크롤 허용
                                        e.preventDefault()
                                        document.body.style.overflow = 'auto'
                                      }}
                                      style={{ 
                                        cursor: dragUserId === user.user_id ? 'grabbing' : 'grab',
                                        touchAction: 'pan-y',
                                        userSelect: 'none',
                                        WebkitUserSelect: 'none',
                                        MozUserSelect: 'none',
                                        msUserSelect: 'none',
                                        pointerEvents: 'auto'
                                      }}
                            >
                              <User className="h-4 w-4 text-gray-500 flex-shrink-0" />
                              <div className="flex-1 min-w-0 flex flex-col justify-center">
                                <span className="font-medium">{user.user_name}</span>
                                <span className="text-xs text-gray-500">{user.email}</span>
                              </div>
                            </li>
                          ))}
                          {teamUsers.length === 0 && (
                            <li className="text-sm text-gray-400 py-4 text-center">아직 사용자가 없습니다.</li>
                          )}
                        </ul>
                      </CardContent>
                    </Card>
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={closeGroupModal}>닫기</Button>
                    <Button className="bg-blue-600 text-white" onClick={closeGroupModal}>저장</Button>
                  </div>
                </DialogContent>
              </Dialog>
              {/* 토큰 상세 정보 모달 */}
              <Dialog open={isTokenDetailOpen} onOpenChange={setIsTokenDetailOpen}>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>토큰 상세 정보</DialogTitle>
                  </DialogHeader>
                  {selectedTokenDetail && (
                    <div className="space-y-4">
                      <div>
                        <span className="font-semibold">토큰 ID:</span> <span className="text-sm text-gray-600">{selectedTokenDetail.hf_manage_id}</span>
                      </div>
                      <div>
                        <span className="font-semibold">별칭:</span> {selectedTokenDetail.hf_token_nickname}
                      </div>
                      <div>
                        <span className="font-semibold">허깅페이스 사용자명:</span> {selectedTokenDetail.hf_user_name}
                      </div>
                      <div>
                        <span className="font-semibold">토큰 (마스킹됨):</span> <span className="break-all font-mono text-sm">{selectedTokenDetail.hf_token_masked || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="font-semibold">할당된 팀:</span>
                        {selectedTokenDetail.group_id ? (
                          <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm">
                            {teams.find(t => t.group_id === selectedTokenDetail.group_id)?.group_name || `팀 ${selectedTokenDetail.group_id}`}
                          </span>
                        ) : (
                          <span className="ml-2 text-gray-500">할당되지 않음</span>
                        )}
                      </div>
                      {selectedTokenDetail.created_at && (
                        <div>
                          <span className="font-semibold">생성일:</span> <span className="text-sm text-gray-600">
                            {new Date(selectedTokenDetail.created_at).toLocaleString('ko-KR')}
                          </span>
                        </div>
                      )}
                      <div className="flex justify-end gap-2 mt-6">
                        {!selectedTokenDetail.group_id && (
                          <select
                            className="mr-2 flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                            onChange={async (e) => {
                              if (e.target.value) {
                                try {
                                  await AdminService.assignTokenToTeam(selectedTokenDetail.hf_manage_id, Number(e.target.value))
                                  await fetchHFTokens()
                                  setIsTokenDetailOpen(false)
                                } catch (err: any) {
                                  setError(err.message || '토큰 할당에 실패했습니다.')
                                }
                              }
                            }}
                          >
                            <option value="">팀에 할당...</option>
                            {teams.map(team => (
                              <option key={team.group_id} value={team.group_id}>
                                {team.group_name}
                              </option>
                            ))}
                          </select>
                        )}
                        {selectedTokenDetail.group_id && (
                          <Button 
                            variant="outline" 
                            onClick={async () => {
                              try {
                                await AdminService.unassignToken(selectedTokenDetail.hf_manage_id)
                                await fetchHFTokens()
                                setIsTokenDetailOpen(false)
                              } catch (err: any) {
                                setError(err.message || '토큰 할당 해제에 실패했습니다.')
                              }
                            }}
                          >
                            할당 해제
                          </Button>
                        )}
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="destructive">삭제</Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>토큰 삭제</AlertDialogTitle>
                              <AlertDialogDescription>
                                정말 이 토큰을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>취소</AlertDialogCancel>
                              <AlertDialogAction 
                                onClick={async () => {
                                  try {
                                    await AdminService.deleteHFToken(selectedTokenDetail.hf_manage_id)
                                    await fetchHFTokens()
                                    setIsTokenDetailOpen(false)
                                  } catch (err: any) {
                                    setError(err.message || '토큰 삭제에 실패했습니다.')
                                  }
                                }} 
                                className="bg-red-600 hover:bg-red-700"
                              >
                                삭제
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                        <Button variant="outline" onClick={() => setIsTokenDetailOpen(false)}>닫기</Button>
                      </div>
                    </div>
                  )}
                </DialogContent>
              </Dialog>
            </>
          )}
        </div>
      </div>
    </RequireAdmin>
  )
}
