import { NextAuthOptions } from "next-auth"
import GoogleProvider from "next-auth/providers/google"

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"

export const authOptions: NextAuthOptions = {
  providers: [
    // NextAuth는 사용하지 않고 authorization code 방식 사용
    // 필요시 다른 provider 추가 가능
  ],
  pages: {
    signIn: '/login',
  },
  session: {
    strategy: 'jwt',
  },
}