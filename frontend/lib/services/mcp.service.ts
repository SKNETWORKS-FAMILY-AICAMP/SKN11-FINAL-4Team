import apiClient from '../api'

export interface MCPChatRequest {
    message: string
}

export interface MCPChatResponse {
    response: string
    tools_used: string[]
}

class MCPService {
    /**
     * MCP 챗봇 메시지 처리
     */
    static async processMessage(request: MCPChatRequest): Promise<MCPChatResponse> {
        return await apiClient.post<MCPChatResponse>('/api/v1/mcp/process', request, {
            requireAuth: false, // 인증 필요 없으면 false, 필요하면 true로 변경
            timeout: 120000 // 2분 타임아웃
        })
    }
}

export default MCPService; 