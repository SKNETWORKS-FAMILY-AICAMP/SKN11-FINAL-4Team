import { NextRequest, NextResponse } from "next/server"

export async function DELETE(
    request: NextRequest,
    { params }: { params: { name: string } }
) {
    try {
        const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

        const response = await fetch(`${apiBaseUrl}/api/v1/mcp/servers/${params.name}`, {
            method: "DELETE",
        })

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
        }

        const data = await response.json()
        return NextResponse.json(data)
    } catch (error) {
        console.error("MCP 서버 제거 실패:", error)
        return NextResponse.json(
            { error: "MCP 서버 제거에 실패했습니다." },
            { status: 500 }
        )
    }
} 