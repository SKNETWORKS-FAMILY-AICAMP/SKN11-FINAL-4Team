import apiClient from '../api'

export interface MCPChatRequest {
    message: string;
    influencer_id: string;
}

export interface MCPChatResponse {
    response: string
    tools_used: string[]
}

class MCPService {
    /**
     * MCP 챗봇 메시지 처리
     * @param request { message: string, influencer_id: string }
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
    static async addServer(payload: any): Promise<{ success: boolean, message?: string }> {
        try {
            const res = await apiClient.post('/api/v1/mcp/servers/add', payload, {
                requireAuth: false,
                timeout: 30000
            });
            // 백엔드가 항상 { success, message } 반환하도록 기대
            if (res && typeof res === 'object' && 'success' in res) {
                return {
                    success: Boolean((res as any).success),
                    message: (res as any).message
                };
            }
            // 혹시라도 백엔드가 다르게 응답하면 성공으로 간주
            return { success: true, message: '서버가 추가되었습니다.' };
        } catch (error: any) {
            // 에러 객체에서 메시지 추출 (콘솔 출력 없이)
            let msg = '서버 추가에 실패했습니다.';

            // 에러는 catch 블록에서만 남김
            if (error?.data?.detail) {
                msg = error.data.detail;
            } else if (error?.data?.message) {
                msg = error.data.message;
            } else if (error?.message) {
                msg = error.message;
            } else if (error?.response?.data?.detail) {
                msg = error.response.data.detail;
            } else if (error?.response?.data?.message) {
                msg = error.response.data.message;
            }

            return { success: false, message: msg };
        }
    }

    /**
     * MCP 서버 제거
     * @param serverName 제거할 서버 이름
     */
    static async removeServer(serverName: string): Promise<{ success: boolean, message?: string }> {
        try {
            const res = await apiClient.delete(`/api/v1/mcp/servers/${serverName}`, {
                requireAuth: false,
                timeout: 30000
            });
            return {
                success: true,
                message: '서버가 제거되었습니다.'
            };
        } catch (error: any) {
            let msg = '서버 제거에 실패했습니다.';

            if (error?.data?.detail) {
                msg = error.data.detail;
            } else if (error?.data?.message) {
                msg = error.data.message;
            } else if (error?.message) {
                msg = error.message;
            } else if (error?.response?.data?.detail) {
                msg = error.response.data.detail;
            } else if (error?.response?.data?.message) {
                msg = error.response.data.message;
            }

            return { success: false, message: msg };
        }
    }
}

export default MCPService; 