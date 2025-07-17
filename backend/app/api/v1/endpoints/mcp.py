from fastapi import APIRouter, Depends, HTTPException
from fastapi import status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.database import get_db

from app.schemas.mcp import (
    MCPToolRequest,
    MCPToolResponse,
    MCPToolsListResponse,
    MCPToolInfo,
    MCPChatRequest,
    MCPChatResponse,
)
from app.services.mcp_client import mcp_client_service
from app.services.mcp_server_manager import mcp_server_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp", tags=["MCP"])


@router.get("/tools/{server_name}", response_model=MCPToolsListResponse)
async def list_mcp_tools(
    server_name: str,
    db: Session = Depends(get_db),
):
    """MCP 서버의 사용 가능한 도구 목록을 반환합니다."""
    try:
        tools_info = await mcp_client_service.list_available_tools(server_name)

        # Dict를 MCPToolInfo로 변환
        tools_list = []
        for tool_info in tools_info:
            tools_list.append(
                MCPToolInfo(
                    name=tool_info.get("name", ""),
                    description=tool_info.get("description", ""),
                    args_schema=tool_info.get("args_schema"),
                )
            )

        return MCPToolsListResponse(
            server_name=server_name, tools=tools_list, total_count=len(tools_list)
        )
    except Exception as e:
        logger.error(f"Error listing MCP tools for server {server_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list MCP tools: {str(e)}",
        )


@router.post("/tools/execute", response_model=MCPToolResponse)
async def execute_mcp_tool(
    request: MCPToolRequest,
    db: Session = Depends(get_db),
):
    """MCP 도구를 실행합니다."""
    try:
        result = await mcp_client_service.execute_tool(
            server_name=request.server_name,
            tool_name=request.tool_name,
            **request.parameters,
        )

        return MCPToolResponse(success=True, result=result)
    except Exception as e:
        logger.error(f"Error executing MCP tool {request.tool_name}: {e}")
        return MCPToolResponse(success=False, error=str(e))


@router.post("/chat", response_model=MCPChatResponse)
async def mcp_chat(
    request: MCPChatRequest,
    db: Session = Depends(get_db),
):
    """MCP를 사용한 챗봇 대화"""
    try:
        from langchain.agents import create_react_agent

        # MCP 도구들 가져오기
        tools = await mcp_client_service.get_tools(request.server_name)

        if not tools:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No tools available for server {request.server_name}",
            )

        # React 에이전트 생성
        from langchain_openai import ChatOpenAI
        from langchain.agents import AgentExecutor, create_react_agent
        from langchain.agents.react.base import DocstoreExplorer
        from langchain.prompts import PromptTemplate

        llm = ChatOpenAI(model="gpt-4", temperature=0)
        agent = create_react_agent(
            llm,
            tools,
            prompt=PromptTemplate.from_template("You are a helpful assistant."),
        )
        agent_executor = AgentExecutor.from_agent_and_tools(
            agent=agent, tools=tools, verbose=True
        )

        # 에이전트 실행
        response = await agent_executor.ainvoke({"input": request.message})

        # 사용된 도구들 추출
        tools_used = []
        if "intermediate_steps" in response:
            for step in response["intermediate_steps"]:
                if "tool" in step:
                    tools_used.append(step["tool"])

        return MCPChatResponse(
            response=response.get("output", str(response)),
            session_id=request.session_id or f"session_{hash(request.message)}",
            tools_used=tools_used,
        )

    except Exception as e:
        logger.error(f"Error in MCP chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat error: {str(e)}",
        )


@router.get("/servers")
async def list_mcp_servers(db: Session = Depends(get_db)):
    """사용 가능한 MCP 서버 목록을 반환합니다."""
    try:
        # MCP 서버 매니저에서 서버 상태 가져오기
        server_status = mcp_server_manager.get_server_status()

        servers = []
        for server_name, status in server_status.items():
            config = status.get("config", {})
            servers.append(
                {
                    "name": server_name,
                    "description": config.get("description", f"{server_name} 서버"),
                    "transport": config.get("transport", "unknown"),
                    "running": status.get("running", False),
                    "pid": status.get("pid"),
                }
            )

        return {
            "servers": servers,
            "total_count": len(servers),
            "running_count": len([s for s in servers if s["running"]]),
        }
    except Exception as e:
        logger.error(f"Error listing MCP servers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list MCP servers: {str(e)}",
        )


@router.post("/servers/{server_name}/restart")
async def restart_mcp_server(
    server_name: str,
    db: Session = Depends(get_db),
):
    """특정 MCP 서버를 재시작합니다."""
    try:
        await mcp_server_manager.restart_server(server_name)
        return {"message": f"{server_name} 서버가 재시작되었습니다."}
    except Exception as e:
        logger.error(f"Error restarting MCP server {server_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart MCP server: {str(e)}",
        )
