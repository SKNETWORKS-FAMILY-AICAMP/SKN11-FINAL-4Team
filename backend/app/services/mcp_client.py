import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

logger = logging.getLogger(__name__)


class MCPClientService:
    """MCP 클라이언트 서비스"""

    def __init__(self):
        self.clients: Dict[str, MultiServerMCPClient] = {}
        self.sessions: Dict[str, ClientSession] = {}
        self.tools_cache: Dict[str, List] = {}

    async def get_client(self, server_name: str) -> MultiServerMCPClient:
        """MCP 클라이언트를 가져오거나 생성합니다."""
        if server_name not in self.clients:
            # MCP 서버 설정
            server_config = {
                "math": {
                    "command": "python",
                    "args": ["examples/mcp_math_server.py"],
                    "transport": "stdio",
                },
                "weather": {
                    "url": "http://localhost:8005/mcp/",
                    "transport": "streamable_http",
                },
            }

            self.clients[server_name] = MultiServerMCPClient(server_config)

        return self.clients[server_name]

    async def get_tools(self, server_name: str) -> List:
        """MCP 서버에서 도구들을 가져옵니다."""
        if server_name not in self.tools_cache:
            client = await self.get_client(server_name)
            tools = await client.get_tools()
            self.tools_cache[server_name] = tools

        return self.tools_cache[server_name]

    async def create_session(self, server_name: str) -> ClientSession:
        """MCP 세션을 생성합니다."""
        if server_name not in self.sessions:
            client = await self.get_client(server_name)
            session = await client.session(server_name).__aenter__()
            self.sessions[server_name] = session

        return self.sessions[server_name]

    async def close_session(self, server_name: str):
        """MCP 세션을 닫습니다."""
        if server_name in self.sessions:
            await self.sessions[server_name].__aexit__(None, None, None)
            del self.sessions[server_name]

    async def execute_tool(self, server_name: str, tool_name: str, **kwargs) -> Any:
        """MCP 도구를 실행합니다."""
        try:
            session = await self.create_session(server_name)
            tools = await self.get_tools(server_name)

            # 도구 찾기
            tool = None
            for t in tools:
                if t.name == tool_name:
                    tool = t
                    break

            if not tool:
                raise ValueError(f"Tool '{tool_name}' not found")

            # 도구 실행
            result = await tool.ainvoke(kwargs)
            return result

        except Exception as e:
            logger.error(f"Error executing MCP tool {tool_name}: {e}")
            raise

    async def list_available_tools(self, server_name: str) -> List[Dict]:
        """사용 가능한 도구 목록을 반환합니다."""
        try:
            tools = await self.get_tools(server_name)
            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "args_schema": tool.args_schema,
                }
                for tool in tools
            ]
        except Exception as e:
            logger.error(f"Error listing MCP tools: {e}")
            return []


# 전역 MCP 클라이언트 서비스 인스턴스
mcp_client_service = MCPClientService()
