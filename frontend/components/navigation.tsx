"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Bot, List, TestTube, PenTool, LogOut, User, Shield } from "lucide-react"
import { useAuth, usePermission } from "@/hooks/use-auth"

export function Navigation() {
  const pathname = usePathname()
  const { user, logout, isAuthenticated } = useAuth()
  const { hasPermission, isAdmin, hasGroup } = usePermission()

  if (pathname === "/login" || !isAuthenticated) {
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
            {hasPermission('model', 'read') && (
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
            )}
            {hasPermission('model', 'test') && (
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
            )}
            {hasPermission('post', 'read') && (
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
            )}
          </div>

          <div className="flex items-center">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="relative h-8 w-8 rounded-full">
                  <Avatar className="h-8 w-8">
                    {user?.profileImage && (
                      <AvatarImage src={user.profileImage} alt={user.name} />
                    )}
                    <AvatarFallback>
                      {user?.name?.charAt(0).toUpperCase() || <User className="h-4 w-4" />}
                    </AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-56" align="end" forceMount>
                <div className="px-2 py-1.5 text-sm">
                  <p className="font-medium">{user?.name}</p>
                  <p className="text-xs text-gray-500">{user?.email}</p>
                  <p className="text-xs text-gray-500">{user?.company}</p>
                </div>
                {isAdmin() && (
                  <Link href="/administrator">
                    <DropdownMenuItem>
                      <User className="mr-2 h-4 w-4" />
                      <span>관리자 설정</span>
                    </DropdownMenuItem>
                  </Link>
                )}
                {!isAdmin() && hasGroup('user') && (
                  <Link href="/request-access">
                    <DropdownMenuItem>
                      <Shield className="mr-2 h-4 w-4" />
                      <span>권한 요청</span>
                    </DropdownMenuItem>
                  </Link>
                )}
                <DropdownMenuItem onClick={logout}>
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
