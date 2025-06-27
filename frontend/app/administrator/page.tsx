"use client"

import { useState } from "react"
import { Navigation } from "@/components/navigation"
import { RequireAdmin } from "@/components/auth/protected-route"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { User, Mail, Phone, Calendar, Settings, Save, ShieldCheck, ShieldX, Search, Plus, Trash2, Users, X, Eye, EyeOff, Key, Check } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogCancel, AlertDialogAction } from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Command, CommandInput, CommandList, CommandItem, CommandEmpty } from "@/components/ui/command"

// 그룹 타입 정의
interface PostGroup {
  id: number;
  name: string;
  description: string;
  users: number[]; // user ids only
  tokenAliases?: string[]; // 여러 토큰 별칭
}

// 임시 권한 그룹/사용자 데이터
const initialGroups: PostGroup[] = [
  {
    id: 1,
    name: "Admin",
    description: "최고 관리자 그룹",
    users: [1, 2],
  },
  {
    id: 2,
    name: "Editor",
    description: "콘텐츠 편집자 그룹",
    users: [3],
  },
  {
    id: 3,
    name: "Viewer",
    description: "읽기 전용 그룹",
    users: [],
  },
]

// 임시 전체 사용자 데이터
const allUsersMock = [
  { id: 1, name: "홍길동", email: "admin1@email.com" },
  { id: 2, name: "김관리", email: "admin2@email.com" },
  { id: 3, name: "이에디터", email: "editor@email.com" },
  { id: 4, name: "이사용자", email: "user@email.com" },
  { id: 5, name: "박뷰어", email: "viewer@email.com" },
]

interface HfTokenItem {
  alias: string;
  token: string;
}

export default function AdministratorPage() {
  const [isEditing, setIsEditing] = useState(false)
  const [userInfo, setUserInfo] = useState({
    name: "홍길동",
    email: "hong@example.com",
    phone: "010-1234-5678",
    joinDate: "2024-01-15",
    company: "AIMEX Inc.",
    position: "AI 개발자"
  })

  const [groups, setGroups] = useState<PostGroup[]>(initialGroups)
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(groups[0]?.id || null)
  const [newGroupName, setNewGroupName] = useState("")
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [dragUserId, setDragUserId] = useState<number | null>(null)
  const [searchTerm, setSearchTerm] = useState("")
  const [dragOverBox, setDragOverBox] = useState<string | null>(null)
  const [hfTokens, setHfTokens] = useState<HfTokenItem[]>([])
  const [shownTokenIdxs, setShownTokenIdxs] = useState<number[]>([])
  const [editIdx, setEditIdx] = useState<number | null>(null)
  const [inputToken, setInputToken] = useState("")
  const [inputAlias, setInputAlias] = useState("")
  const [adding, setAdding] = useState(false)
  const [groupTokenAliases, setGroupTokenAliases] = useState<string[]>([])
  const [editingTokenGroupId, setEditingTokenGroupId] = useState<number | null>(null)
  const [editingTokenAliases, setEditingTokenAliases] = useState<string[]>([])

  const handleSave = () => {
    setIsEditing(false)
    // 여기에 실제 저장 로직 추가
  }

  // 그룹 추가
  const handleAddGroup = () => {
    if (!newGroupName.trim()) return
    setGroups(prev => [
      ...prev,
      {
        id: Date.now(),
        name: newGroupName,
        description: "",
        users: [],
        tokenAliases: [],
      },
    ])
    setNewGroupName("")
    setGroupTokenAliases([])
  }

  // 그룹 삭제
  const handleDeleteGroup = (groupId: number) => {
    setGroups(prev => prev.filter(g => g.id !== groupId))
    if (selectedGroupId === groupId) setSelectedGroupId(groups[0]?.id || null)
  }

  // 그룹 모달 열기
  const openGroupModal = (groupId: number) => {
    setSelectedGroupId(groupId)
    setIsModalOpen(true)
  }
  const closeGroupModal = () => {
    setIsModalOpen(false)
    setSelectedGroupId(null)
  }

  // 드래그앤드롭 로직
  const handleDragStart = (userId: number) => setDragUserId(userId)
  
  const handleDropToGroup = () => {
    if (dragUserId && selectedGroupId) {
      // 다른 그룹에서 해당 사용자 제거
      setGroups(prev => prev.map(g => ({
        ...g,
        users: g.id === selectedGroupId && !g.users.includes(dragUserId)
          ? [...g.users, dragUserId]
          : g.users.filter(uid => uid !== dragUserId)
      })))
    }
    setDragUserId(null)
    setSelectedGroupId(null)
  }
  
  const handleDropToAll = () => {
    if (dragUserId) {
      // 모든 그룹에서 해당 사용자 제거
      setGroups(prev => prev.map(g => ({
        ...g,
        users: g.users.filter(uid => uid !== dragUserId)
      })))
    }
    setDragUserId(null)
    setSelectedGroupId(null)
  }

  // 그룹/사용자 정보
  const selectedGroup = groups.find(g => g.id === selectedGroupId)
  const groupUserIds = selectedGroup?.users || []
  const groupUsers = allUsersMock.filter(u => groupUserIds.includes(u.id))
  const otherUsers = allUsersMock.filter(u => !groupUserIds.includes(u.id))

  return (
    <RequireAdmin>
      <div className="min-h-screen bg-gray-50">
        <Navigation />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">관리자 설정</h1>
          <p className="text-gray-600 mt-2">시스템 설정을 관리하세요</p>
        </div>

        <div className="mt-8">
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
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* 전체 사용자 목록 */}
                <Card className="shadow-sm">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base font-semibold flex items-center gap-2">
                      <Users className="h-4 w-4" />
                      전체 사용자
                    </CardTitle>
                  </CardHeader>
                  <CardContent 
                    className={`min-h-[300px] transition-colors ${
                      dragOverBox === 'all' ? 'bg-blue-50 border-blue-300' : ''
                    }`}
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
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {allUsersMock
                        .filter(user => !groups.some(g => g.users.includes(user.id)))
                        .filter(user => 
                          user.name.includes(searchTerm) || user.email.includes(searchTerm)
                        )
                        .map(user => (
                        <div
                          key={user.id}
                          className={`flex items-center gap-3 p-2 rounded-lg cursor-move transition-all ${
                            dragUserId === user.id 
                              ? 'opacity-50 transform scale-95' 
                              : 'hover:bg-gray-50 hover:shadow-sm'
                          }`}
                          draggable
                          onDragStart={() => handleDragStart(user.id)}
                          onDragEnd={() => setDragUserId(null)}
                        >
                          <Avatar className="h-8 w-8">
                            <AvatarFallback className="bg-gray-200 text-gray-600 text-xs">
                              {user.name.charAt(0)}
                            </AvatarFallback>
                          </Avatar>
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm truncate">{user.name}</p>
                            <p className="text-xs text-gray-500 truncate">{user.email}</p>
                          </div>
                          <div className="text-gray-400">
                            <User className="h-4 w-4" />
                          </div>
                        </div>
                      ))}
                      {allUsersMock
                        .filter(user => !groups.some(g => g.users.includes(user.id)))
                        .filter(user => 
                          user.name.includes(searchTerm) || user.email.includes(searchTerm)
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
                  {groups.map(group => (
                    <Card 
                      key={group.id} 
                      className={`shadow-sm transition-all ${
                        dragOverBox === `group-${group.id}` ? 'bg-green-50 border-green-300 shadow-md' : ''
                      }`}
                    >
                      <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className={`w-3 h-3 rounded-full ${
                              group.name === 'Admin' ? 'bg-red-500' :
                              group.name === 'Editor' ? 'bg-blue-500' : 'bg-green-500'
                            }`}></div>
                            <div>
                              <CardTitle className="text-base font-semibold">{group.name}</CardTitle>
                              <p className="text-sm text-gray-500">
                                {group.description || `${group.users.length}명의 사용자`}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant="secondary" className="text-xs">
                              {group.users.length}명
                            </Badge>
                            <Button 
                              size="icon" 
                              variant="ghost" 
                              onClick={() => handleDeleteGroup(group.id)}
                              className="h-8 w-8"
                            >
                              <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent
                        className={`min-h-[120px] transition-colors`}
                        onDragOver={e => { 
                          e.preventDefault(); 
                          setDragOverBox(`group-${group.id}`); 
                          setSelectedGroupId(group.id);
                        }}
                        onDragLeave={() => setDragOverBox(null)}
                        onDrop={() => {
                          handleDropToGroup();
                          setDragOverBox(null);
                        }}
                      >
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {allUsersMock
                            .filter(user => group.users.includes(user.id))
                            .map(user => (
                            <div
                              key={user.id}
                              className={`flex items-center gap-2 p-2 rounded-lg cursor-move transition-all ${
                                dragUserId === user.id 
                                  ? 'opacity-50 transform scale-95' 
                                  : 'hover:bg-white hover:shadow-sm border border-gray-100'
                              }`}
                              draggable
                              onDragStart={() => {
                                handleDragStart(user.id);
                                setSelectedGroupId(group.id);
                              }}
                              onDragEnd={() => setDragUserId(null)}
                            >
                              <Avatar className="h-6 w-6">
                                <AvatarFallback className="bg-blue-100 text-blue-600 text-xs">
                                  {user.name.charAt(0)}
                                </AvatarFallback>
                              </Avatar>
                              <div className="flex-1 min-w-0">
                                <p className="font-medium text-xs truncate">{user.name}</p>
                                <p className="text-xs text-gray-500 truncate">{user.email}</p>
                              </div>
                            </div>
                          ))}
                          {group.users.length === 0 && (
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
              
              {/* 새 그룹 추가 섹션 */}
              <div className="mt-6 pt-6 border-t">
                <h4 className="font-medium text-gray-900 mb-4">새 그룹 추가</h4>
                <div className="flex gap-3 items-end">
                  <div className="flex-1 max-w-xs">
                    <Label htmlFor="new-group-name" className="text-sm font-medium">그룹명</Label>
                    <Input
                      id="new-group-name"
                      placeholder="새 그룹명 입력"
                      value={newGroupName}
                      onChange={e => setNewGroupName(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleAddGroup()}
                      className="mt-1"
                    />
                  </div>
                  <Button 
                    onClick={handleAddGroup}
                    disabled={!newGroupName.trim()}
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    그룹 추가
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="h-8" />

        {/* 허깅페이스 토큰 관리 카드 */}
        <Card className="mb-0">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="h-5 w-5 text-yellow-600" />
              허깅페이스 토큰 관리
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* 토큰 리스트 */}
            {hfTokens.length === 0 && !adding && (
              <div className="text-gray-400 mb-4">등록된 토큰이 없습니다.</div>
            )}
            <ul className="space-y-3 mb-4">
              {hfTokens.map((item, idx) => (
                <li key={item.alias + '-' + idx} className="flex flex-col md:flex-row md:items-center gap-2 md:gap-4 border rounded px-4 py-2">
                  <div className="flex-1 flex items-center gap-2">
                    <span className="text-blue-700">{item.alias}</span>
                    <span className="text-gray-400">|</span>
                    {shownTokenIdxs.includes(idx) ? (
                      <span className="break-all">{item.token}</span>
                    ) : (
                      <span>{"*".repeat(Math.max(8, item.token.length))}</span>
                    )}
                    <Button size="icon" variant="ghost" onClick={() => setShownTokenIdxs(shownTokenIdxs.includes(idx) ? shownTokenIdxs.filter(i => i !== idx) : [...shownTokenIdxs, idx])}>
                      {shownTokenIdxs.includes(idx) ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </Button>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => { setEditIdx(idx); setInputAlias(item.alias); setInputToken(item.token); setAdding(false); }}>수정</Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="destructive" size="sm"><Trash2 className="h-4 w-4 mr-1" />삭제</Button>
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
                          <AlertDialogAction onClick={() => setHfTokens(hfTokens.filter((_, i) => i !== idx))} className="bg-red-600 hover:bg-red-700">삭제</AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </li>
              ))}
            </ul>
            {/* 토큰 추가/수정 폼 */}
            {(adding || editIdx !== null) && (
              <div className="flex flex-col md:flex-row gap-3 items-center mb-2">
                <Input
                  type="text"
                  placeholder="별칭 (예: 서비스용, 개발용)"
                  value={inputAlias}
                  onChange={e => setInputAlias(e.target.value)}
                  className="w-full md:w-48"
                />
                <Input
                  type="text"
                  placeholder="허깅페이스 토큰 입력"
                  value={inputToken}
                  onChange={e => setInputToken(e.target.value)}
                  className="w-full md:w-96"
                />
                <Button className="bg-blue-600 text-white" onClick={() => {
                  if (!inputAlias || !inputToken) return;
                  if (editIdx !== null) {
                    setHfTokens(hfTokens.map((item, i) => i === editIdx ? { alias: inputAlias, token: inputToken } : item));
                    setEditIdx(null);
                  } else {
                    setHfTokens([...hfTokens, { alias: inputAlias, token: inputToken }]);
                    setAdding(false);
                  }
                  setInputAlias("");
                  setInputToken("");
                }}>
                  <Save className="h-4 w-4 mr-1" /> 저장
                </Button>
                <Button variant="outline" onClick={() => { setEditIdx(null); setAdding(false); setInputAlias(""); setInputToken(""); }}>취소</Button>
              </div>
            )}
            {/* 추가 버튼 */}
            {!adding && editIdx === null && (
              <Button variant="outline" onClick={() => { setAdding(true); setInputAlias(""); setInputToken(""); }}>+ 새 토큰 추가</Button>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 그룹 상세/사용자 관리 (모달로 이동) */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-blue-600" />
              {selectedGroup?.name} 그룹 사용자 관리
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
                <ul className="divide-y max-h-60 overflow-y-auto rounded"
                >
                  {otherUsers.filter(user =>
                    user.name.includes(searchTerm) || user.email.includes(searchTerm)
                  ).map(user => (
                    <li
                      key={user.id}
                      className="flex items-center gap-3 py-2 px-2 rounded transition-shadow bg-white"
                      draggable
                      onDragStart={() => handleDragStart(user.id)}
                      onDragEnd={() => setDragUserId(null)}
                    >
                      <User className="h-4 w-4 text-gray-500" />
                      <span className="font-medium">{user.name}</span>
                      <span className="text-xs text-gray-500">{user.email}</span>
                    </li>
                  ))}
                  {otherUsers.filter(user =>
                    user.name.includes(searchTerm) || user.email.includes(searchTerm)
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
                <ul className="divide-y max-h-60 overflow-y-auto rounded"
                >
                  {groupUsers.map(user => (
                    <li
                      key={user.id}
                      className="flex items-center gap-3 py-2 px-2 rounded transition-shadow bg-white"
                      draggable
                      onDragStart={() => handleDragStart(user.id)}
                      onDragEnd={() => setDragUserId(null)}
                    >
                      <User className="h-4 w-4 text-gray-500" />
                      <span className="font-medium">{user.name}</span>
                      <span className="text-xs text-gray-500">{user.email}</span>
                    </li>
                  ))}
                  {groupUsers.length === 0 && (
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
      </div>
    </RequireAdmin>
  )
} 