"use client"

import { useState } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Navigation } from "@/components/navigation"
import { useAuth } from "@/hooks/use-auth"

export default function ProfilePage() {
  const { user } = useAuth()
  const [editMode, setEditMode] = useState(false)
  const [name, setName] = useState(user?.name || user?.user_name || "")
  const [email, setEmail] = useState(user?.email || "")
  const [company, setCompany] = useState(user?.company || "")
  const [saved, setSaved] = useState(false)

  // 원본 정보 저장 (취소 시 복원용)
  const [original, setOriginal] = useState({
    name: user?.name || user?.user_name || "",
    email: user?.email || "",
    company: user?.company || ""
  })

  const handleEdit = () => {
    setEditMode(true)
    setSaved(false)
  }

  const handleCancel = () => {
    setName(original.name)
    setEmail(original.email)
    setCompany(original.company)
    setEditMode(false)
    setSaved(false)
  }

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault()
    setOriginal({ name, email, company })
    setEditMode(false)
    setSaved(true)
    // TODO: API 연동 (PATCH /api/profile 등)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      <div className="flex items-center justify-center pt-12">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>프로필 관리</CardTitle>
          </CardHeader>
          <CardContent>
            {!editMode ? (
              <div className="space-y-6">
                <div>
                  <Label>이름</Label>
                  <div className="mt-1 p-2 border rounded bg-gray-100">{name}</div>
                </div>
                <div>
                  <Label>이메일</Label>
                  <div className="mt-1 p-2 border rounded bg-gray-100">{email}</div>
                </div>
                <div>
                  <Label>회사</Label>
                  <div className="mt-1 p-2 border rounded bg-gray-100">{company}</div>
                </div>
                <Button className="w-full" onClick={handleEdit}>수정</Button>
                {saved && <div className="text-green-600 text-sm mt-2">저장되었습니다.</div>}
              </div>
            ) : (
              <form onSubmit={handleSave} className="space-y-6">
                <div>
                  <Label htmlFor="name">이름</Label>
                  <Input
                    id="name"
                    type="text"
                    placeholder="이름"
                    value={name}
                    onChange={e => setName(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="email">이메일</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <Label>회사</Label>
                  <div className="mt-1 p-2 border rounded bg-gray-100">{company}</div>
                </div>
                <div className="flex gap-2">
                  <Button type="submit" className="flex-1">저장</Button>
                  <Button type="button" variant="outline" className="flex-1" onClick={handleCancel}>취소</Button>
                </div>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
} 