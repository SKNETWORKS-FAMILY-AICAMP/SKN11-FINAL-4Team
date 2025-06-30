import "next-auth"
import { DefaultSession } from "next-auth"

declare module "next-auth" {
  interface Session extends DefaultSession {
    backendJWT?: string
    backendUser?: any
    provider?: string
  }

  interface Account {
    backend_jwt?: string
    backend_user?: any
  }
}