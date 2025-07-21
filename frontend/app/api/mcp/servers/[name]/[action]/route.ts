import { NextRequest, NextResponse } from "next/server"

export async function POST(
    request: NextRequest,
    { params }: { params: { name: string; action: string } }
) {
    try {
        const { name, action } = params

        if (!["start", "stop"].includes(action)) {
            return NextResponse.json(
                { error: "잘못된 액션입니다. 'start' 또는 'stop'만 사용 가능합니다." },
                { status: 400 }
            )
        }

        const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

        const response = await fetch(`${apiBaseUrl}/api/v1/mcp/servers/${name}/${action}`, {
            method: "POST",
        })

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
        }

        const data = await response.json()
        return NextResponse.json(data)
    } catch (error) {
        console.error(`MCP 서버 ${params.action} 실패:`, error)
        return NextResponse.json(
            { error: `MCP 서버 ${params.action}에 실패했습니다.` },
            { status: 500 }
        )
    }
} 