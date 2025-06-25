"use client"

import { useState } from "react"
import { Navigation } from "@/components/navigation"
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
        tokenAliases: groupTokenAliases,
      },
    ])
    setNewGroupName("")
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
      setGroups(prev => prev.map(g =>
        g.id === selectedGroupId && !g.users.includes(dragUserId)
          ? { ...g, users: [...g.users, dragUserId] }
          : g
      ))
    }
    setDragUserId(null)
  }
  const handleDropToAll = () => {
    if (dragUserId && selectedGroupId) {
      setGroups(prev => prev.map(g =>
        g.id === selectedGroupId
          ? { ...g, users: g.users.filter(uid => uid !== dragUserId) }
          : g
      ))
    }
    setDragUserId(null)
  }

  // 그룹/사용자 정보
  const selectedGroup = groups.find(g => g.id === selectedGroupId)
  const groupUserIds = selectedGroup?.users || []
  const groupUsers = allUsersMock.filter(u => groupUserIds.includes(u.id))
  const otherUsers = allUsersMock.filter(u => !groupUserIds.includes(u.id))

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">관리자 설정</h1>
          <p className="text-gray-600 mt-2">계정 정보를 관리하세요</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* 프로필 카드 */}
          <div className="lg:col-span-1">
            <Card>
              <CardHeader className="text-center">
                <div className="flex justify-center mb-4">
                  <Avatar className="h-24 w-24">
                    <AvatarFallback className="text-2xl">
                      <User className="h-8 w-8" />
                    </AvatarFallback>
                  </Avatar>
                </div>
                <CardTitle className="text-xl">{userInfo.name}</CardTitle>
                <CardDescription>{userInfo.position}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex items-center text-sm text-gray-600">
                    <Mail className="h-4 w-4 mr-2" />
                    {userInfo.email}
                  </div>
                  <div className="flex items-center text-sm text-gray-600">
                    <Phone className="h-4 w-4 mr-2" />
                    {userInfo.phone}
                  </div>
                  <div className="flex items-center text-sm text-gray-600">
                    <Calendar className="h-4 w-4 mr-2" />
                    가입일: {userInfo.joinDate}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 정보 편집 카드 */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle className="flex items-center">
                      <Settings className="h-5 w-5 mr-2" />
                      계정 정보
                    </CardTitle>
                    <CardDescription>개인 정보를 수정할 수 있습니다</CardDescription>
                  </div>
                  {!isEditing ? (
                    <Button onClick={() => setIsEditing(true)} variant="outline">
                      편집
                    </Button>
                  ) : (
                    <div className="flex space-x-2">
                      <Button onClick={() => setIsEditing(false)} variant="outline">
                        취소
                      </Button>
                      <Button onClick={handleSave}>
                        <Save className="h-4 w-4 mr-2" />
                        저장
                      </Button>
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="name">이름</Label>
                      <Input
                        id="name"
                        value={userInfo.name}
                        onChange={(e) => setUserInfo({ ...userInfo, name: e.target.value })}
                        disabled={!isEditing}
                      />
                    </div>
                    <div>
                      <Label htmlFor="email">이메일</Label>
                      <Input
                        id="email"
                        type="email"
                        value={userInfo.email}
                        onChange={(e) => setUserInfo({ ...userInfo, email: e.target.value })}
                        disabled={!isEditing}
                      />
                    </div>
                    <div>
                      <Label htmlFor="phone">전화번호</Label>
                      <Input
                        id="phone"
                        value={userInfo.phone}
                        onChange={(e) => setUserInfo({ ...userInfo, phone: e.target.value })}
                        disabled={!isEditing}
                      />
                    </div>
                    <div>
                      <Label htmlFor="company">회사</Label>
                      <Input
                        id="company"
                        value={userInfo.company}
                        onChange={(e) => setUserInfo({ ...userInfo, company: e.target.value })}
                        disabled={!isEditing}
                      />
                    </div>
                    <div>
                      <Label htmlFor="position">직책</Label>
                      <Input
                        id="position"
                        value={userInfo.position}
                        onChange={(e) => setUserInfo({ ...userInfo, position: e.target.value })}
                        disabled={!isEditing}
                      />
                    </div>
                    <div>
                      <Label htmlFor="joinDate">가입일</Label>
                      <Input
                        id="joinDate"
                        value={userInfo.joinDate}
                        disabled
                        className="bg-gray-50"
                      />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        <div className="mt-8">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5 text-blue-600" />
                권한 그룹
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="mb-4 divide-y">
                {groups.map(group => (
                  <li
                    key={group.id}
                    className={`flex items-center justify-between py-2 cursor-pointer rounded px-2 ${selectedGroupId === group.id ? "bg-blue-50" : "hover:bg-gray-50"}`}
                    onClick={() => openGroupModal(group.id)}
                  >
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between w-full">
                      <div>
                        <span className="font-semibold">{group.name}</span>
                        <span className="ml-2 text-xs text-gray-400">({group.users.length}명)</span>
                      </div>
                      <div className="flex flex-wrap gap-1 items-center mt-2 md:mt-0">
                        {editingTokenGroupId === group.id ? (
                          <>
                            <Command className="rounded-md border min-w-[180px]">
                              <CommandInput placeholder="토큰 검색..." />
                              <CommandList>
                                <CommandEmpty>토큰 없음</CommandEmpty>
                                {hfTokens.map(token => (
                                  <CommandItem
                                    key={token.alias}
                                    value={token.alias}
                                    onSelect={() => {
                                      if (editingTokenAliases.includes(token.alias)) {
                                        setEditingTokenAliases(prev => prev.filter(a => a !== token.alias));
                                      } else {
                                        setEditingTokenAliases(prev => [...prev, token.alias]);
                                      }
                                    }}
                                    className={editingTokenAliases.includes(token.alias) ? "bg-blue-50 text-blue-700" : ""}
                                  >
                                    <span>{token.alias}</span>
                                    {editingTokenAliases.includes(token.alias) && <Check className="ml-auto h-4 w-4" />}
                                  </CommandItem>
                                ))}
                              </CommandList>
                            </Command>
                            <Button size="sm" className="ml-2 bg-blue-600 text-white" onClick={e => { e.stopPropagation(); setGroups(groups => groups.map(g => g.id === group.id ? { ...g, tokenAliases: editingTokenAliases } : g)); setEditingTokenGroupId(null); }}>
                              저장
                            </Button>
                            <Button size="sm" variant="outline" className="ml-1" onClick={e => { e.stopPropagation(); setEditingTokenGroupId(null); }}>
                              취소
                            </Button>
                          </>
                        ) : (
                          <>
                            {group.tokenAliases && group.tokenAliases.length > 0 ? (
                              group.tokenAliases.map(alias => (
                                <Badge key={alias} className="bg-yellow-100 text-yellow-700">{alias}</Badge>
                              ))
                            ) : (
                              <Badge className="bg-gray-100 text-gray-400">미지정</Badge>
                            )}
                            <Button size="sm" variant="outline" className="ml-2" onClick={e => { e.stopPropagation(); setEditingTokenGroupId(group.id); setEditingTokenAliases(group.tokenAliases || []); }}>
                              토큰 편집
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                    <Button size="icon" variant="ghost" onClick={e => { e.stopPropagation(); handleDeleteGroup(group.id) }} title="그룹 삭제">
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </li>
                ))}
              </ul>
              <div className="flex gap-2 items-end">
                <div className="flex-1">
                  <Input
                    placeholder="새 그룹명"
                    value={newGroupName}
                    onChange={e => setNewGroupName(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleAddGroup()}
                  />
                </div>
                <div className="flex-1 min-w-[200px]">
                  <div className="mb-2 text-xs font-semibold text-gray-600">연결할 토큰</div>
                  <Command className="rounded-md border">
                    <CommandInput placeholder="토큰 검색..." />
                    <CommandList>
                      <CommandEmpty>토큰 없음</CommandEmpty>
                      {hfTokens.map(token => (
                        <CommandItem
                          key={token.alias}
                          value={token.alias}
                          onSelect={() => {
                            if (groupTokenAliases.includes(token.alias)) {
                              setGroupTokenAliases(prev => prev.filter(a => a !== token.alias));
                            } else {
                              setGroupTokenAliases(prev => [...prev, token.alias]);
                            }
                          }}
                          className={groupTokenAliases.includes(token.alias) ? "bg-blue-50 text-blue-700" : ""}
                        >
                          <span>{token.alias}</span>
                          {groupTokenAliases.includes(token.alias) && <Check className="ml-auto h-4 w-4" />}
                        </CommandItem>
                      ))}
                    </CommandList>
                  </Command>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {groupTokenAliases.map(alias => (
                      <Badge key={alias} className="bg-blue-100 text-blue-700">{alias}</Badge>
                    ))}
                  </div>
                </div>
                <Button variant="outline" className="h-10" onClick={handleAddGroup}>
                  <Plus className="h-4 w-4" />
                </Button>
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
  )
} 