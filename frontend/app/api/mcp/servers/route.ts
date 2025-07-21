import { NextRequest, NextResponse } from "next/server"

export async function GET() {
    try {
        const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
        const response = await fetch(`${apiBaseUrl}/api/v1/mcp/servers`)

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
        }

        const data = await response.json()
        return NextResponse.json(data)
    } catch (error) {
        console.error("MCP 서버 목록 조회 실패:", error)
        return NextResponse.json(
            { error: "MCP 서버 목록을 불러오는데 실패했습니다." },
            { status: 500 }
        )
    }
} 