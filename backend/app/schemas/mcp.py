from pydantic import BaseModel
from typing import Dict, List, Optional, Any


class MCPToolRequest(BaseModel):
    """MCP 도구 실행 요청"""

    server_name: str
    tool_name: str
    parameters: Dict[str, Any] = {}


class MCPToolResponse(BaseModel):
    """MCP 도구 실행 응답"""

    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None


class MCPToolInfo(BaseModel):
    """MCP 도구 정보"""

    name: str
    description: str
    args_schema: Optional[Dict[str, Any]] = None


class MCPToolsListResponse(BaseModel):
    """MCP 도구 목록 응답"""

    server_name: str
    tools: List[MCPToolInfo]
    total_count: int


class MCPChatRequest(BaseModel):
    """MCP 챗봇 요청"""

    message: str
    server_name: str
    session_id: Optional[str] = None


class MCPChatResponse(BaseModel):
    """MCP 챗봇 응답"""

    response: str
    session_id: str
    tools_used: List[str] = []
