import type React from "react"
import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { AuthProvider } from "@/contexts/auth-context"

import { Toaster } from "@/components/ui/toaster"
import { AuthGuard } from "@/components/auth/auth-guard"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "AI Influencer Platform",
  description: "기업용 AI 인플루언서 생성 및 관리 플랫폼",
  generator: 'v0.dev',
  icons: {
    icon: "/favicon.ico",
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko">
      <body className={inter.className} suppressHydrationWarning={true}>
        <AuthProvider>
          <AuthGuard>
            {children}
          </AuthGuard>
        </AuthProvider>
        <Toaster />
      </body>
    </html>
  )
}
