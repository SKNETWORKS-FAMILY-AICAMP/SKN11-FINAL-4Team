import { apiClient } from '@/lib/api'

export interface MCPToolInfo {
    name: string
    description: string
    args_schema?: any
}

export interface MCPToolsListResponse {
    server_name: string
    tools: MCPToolInfo[]
    total_count: number
}

export interface MCPToolRequest {
    server_name: string
    tool_name: string
    parameters: Record<string, any>
}

export interface MCPToolResponse {
    success: boolean
    result?: any
    error?: string
}

export interface MCPChatRequest {
    message: string
    server_name: string
    session_id?: string
}

export interface MCPChatResponse {
    response: string
    session_id: string
    tools_used: string[]
}

export interface MCPServerInfo {
    name: string
    description: string
    transport: string
    running?: boolean
    pid?: number
}

export interface MCPServersResponse {
    servers: MCPServerInfo[]
    total_count: number
    running_count?: number
}

export class MCPService {
    /**
 * MCP 서버 목록을 가져옵니다.
 */
    static async getServers(): Promise<MCPServersResponse> {
        return await apiClient.get<MCPServersResponse>('/api/v1/mcp/servers', { requireAuth: false })
    }

    /**
     * 특정 MCP 서버를 재시작합니다.
     */
    static async restartServer(serverName: string): Promise<{ message: string }> {
        return await apiClient.post<{ message: string }>(`/api/v1/mcp/servers/${serverName}/restart`, undefined, { requireAuth: false })
    }

    /**
     * 특정 MCP 서버의 도구 목록을 가져옵니다.
     */
    static async getTools(serverName: string): Promise<MCPToolsListResponse> {
        return await apiClient.get<MCPToolsListResponse>(`/api/v1/mcp/tools/${serverName}`, { requireAuth: false })
    }

    /**
     * MCP 도구를 실행합니다.
     */
    static async executeTool(request: MCPToolRequest): Promise<MCPToolResponse> {
        return await apiClient.post<MCPToolResponse>('/api/v1/mcp/tools/execute', request, { requireAuth: false })
    }

    /**
     * MCP를 사용한 챗봇 대화를 수행합니다.
     */
    static async chat(request: MCPChatRequest): Promise<MCPChatResponse> {
        return await apiClient.post<MCPChatResponse>('/api/v1/mcp/chat', request, { requireAuth: false })
    }
} 