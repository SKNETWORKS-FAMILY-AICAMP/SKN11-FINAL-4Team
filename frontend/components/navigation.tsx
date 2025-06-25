"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Bot, List, TestTube, PenTool, LogOut, User } from "lucide-react"

export function Navigation() {
  const pathname = usePathname()
  const router = useRouter()

  const handleLogout = () => {
    // 여기에 실제 로그아웃 로직 추가 (토큰 삭제, 세션 정리 등)
    // localStorage.removeItem('token')
    // sessionStorage.clear()
    
    // 로그인 페이지로 리다이렉트
    router.push('/login')
  }

  const isAdmin = true; // TODO: Replace with actual admin check

  if (pathname === "/login") {
    return null
  }

  return (
    <nav className="border-b bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link href="/dashboard" className="flex items-center space-x-2">
              <Bot className="h-8 w-8 text-blue-600" />
              <span className="text-xl font-bold text-gray-900">AIMEX</span>
            </Link>
          </div>

          <div className="hidden md:flex md:space-x-8 -ml-5">
            <Link
              href="/dashboard"
              className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${
                pathname === "/dashboard"
                  ? "text-blue-600 border-b-2 border-blue-600"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <List className="h-4 w-4 mr-2" />
              모델 목록
            </Link>
            <Link
              href="/test-model"
              className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${
                pathname === "/test-model"
                  ? "text-blue-600 border-b-2 border-blue-600"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <TestTube className="h-4 w-4 mr-2" />
              모델 테스트
            </Link>
            <Link
              href="/post_list"
              className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${
                pathname === "/post_list"
                  ? "text-blue-600 border-b-2 border-blue-600"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <PenTool className="h-4 w-4 mr-2" />
              게시글 목록
            </Link>
          </div>

          <div className="flex items-center">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="relative h-8 w-8 rounded-full">
                  <Avatar className="h-8 w-8">
                    <AvatarFallback>
                      <User className="h-4 w-4" />
                    </AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-56" align="end" forceMount>
                {isAdmin && (
                  <Link href="/administrator">
                    <DropdownMenuItem>
                      <User className="mr-2 h-4 w-4" />
                      <span>관리자 설정</span>
                    </DropdownMenuItem>
                  </Link>
                )}
                <DropdownMenuItem onClick={handleLogout}>
                  <LogOut className="mr-2 h-4 w-4" />
                  <span>로그아웃</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>
    </nav>
  )
}
