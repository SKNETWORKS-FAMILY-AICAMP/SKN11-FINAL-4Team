import apiClient from '../api'

export interface MCPChatRequest {
    message: string
    selected_servers?: string[]
}

export interface MCPChatResponse {
    response: string
    tools_used: string[]
}

class MCPService {
    /**
     * MCP 챗봇 메시지 처리
     * @param request { message: string, selected_servers?: string[] }
     */
    static async processMessage(request: MCPChatRequest): Promise<MCPChatResponse> {
        return await apiClient.post<MCPChatResponse>('/api/v1/mcp/process', request, {
            requireAuth: false, // 인증 필요 없으면 false, 필요하면 true로 변경
            timeout: 120000 // 2분 타임아웃
        })
    }

    /**
     * MCP 서버 목록 조회
     */
    static async getServers(): Promise<{ servers: Record<string, { running: boolean, pid: number | null, config: any }>, total_count: number }> {
        return await apiClient.get<{ servers: Record<string, { running: boolean, pid: number | null, config: any }>, total_count: number }>('/api/v1/mcp/servers', {
            requireAuth: false,
            timeout: 30000
        })
    }

    /**
     * MCP 서버 추가 (HTTP/stdio)
     * @param payload 전체 서버 추가 JSON 객체
     */
    static async addServer(payload: any): Promise<any> {
        return await apiClient.post('/api/v1/mcp/servers/add', payload, {
            requireAuth: false,
            timeout: 30000
        })
    }
}

export default MCPService; 