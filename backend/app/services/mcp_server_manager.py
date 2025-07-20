import asyncio
import subprocess
import logging
import signal
import sys
import os
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class MCPServerManager:
    """MCP 서버들을 관리하는 매니저"""

    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.server_configs = {
            "math": {
                "script": "examples/mcp_math_server.py",
                "transport": "streamable-http",  # stdio → streamable-http로 변경
                "port": 8003,  # 포트 추가
                "description": "수학 계산 서버",
            },
            "weather": {
                "script": "examples/mcp_weather_server.py",
                "transport": "streamable-http",
                "port": 8005,  # 포트 변경 (8002 → 8005)
                "description": "날씨 정보 서버",
            },
            # 실제 구현된 서버만 활성화 (나머지는 주석 처리)
        }

    async def start_all_servers(self):
        """모든 MCP 서버를 시작합니다."""
        logger.info("MCP 서버들을 시작합니다...")

        # MCP 모듈 사용 가능 여부 확인
        try:
            import mcp
            from langchain_mcp_adapters.client import MultiServerMCPClient
            logger.info("✅ MCP 모듈 사용 가능")
        except ImportError as e:
            logger.warning(f"⚠️ MCP 모듈이 설치되지 않았습니다: {e}")
            logger.warning("⚠️ MCP 서버 시작을 건너뜁니다.")
            return

        # MCP 서버들을 바로 시작
        logger.info("🚀 MCP 서버들을 바로 시작합니다...")

        for server_name, config in self.server_configs.items():
            try:
                await self.start_server(server_name, config)
            except Exception as e:
                logger.error(f"{server_name} 서버 시작 실패: {e}")

        logger.info(f"{len(self.processes)}개의 MCP 서버가 시작되었습니다.")

    async def _is_port_in_use(self, port: int) -> bool:
        """포트가 사용 중인지 확인합니다."""
        import socket
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                return result == 0
        except Exception:
            return False

    async def start_server(self, server_name: str, config: dict):
        """특정 MCP 서버를 시작합니다."""
        script_path = Path(__file__).parent.parent.parent / config["script"]

        if not script_path.exists():
            logger.error(f"스크립트 파일을 찾을 수 없습니다: {script_path}")
            return

        try:
            if config["transport"] == "stdio":
                # stdio 서버는 백그라운드에서 실행
                process = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    cwd=Path(__file__).parent.parent.parent,
                    encoding="utf-8",
                    errors="replace",
                )
                
                # 프로세스가 정상적으로 시작되었는지 확인
                await asyncio.sleep(2)
                if process.poll() is None:
                    self.processes[server_name] = process
                    logger.info(f"{server_name} 서버 시작됨 (PID: {process.pid})")
                else:
                    stdout, stderr = process.communicate()
                    logger.error(f"{server_name} 서버 시작 실패:\nstdout: {stdout}\nstderr: {stderr}")
                    
            elif config["transport"] == "streamable-http":
                port = config.get("port")
                if port is None:
                    logger.error(f"{server_name} 서버에 포트가 설정되지 않았습니다.")
                    return
                
                # 포트가 사용 중인지 확인
                if await self._is_port_in_use(port):
                    logger.warning(f"포트 {port}가 이미 사용 중입니다. {server_name} 서버를 건너뜁니다.")
                    return
                
                logger.info(f"{server_name} 서버를 포트 {port}에서 시작합니다...")
                
                # 환경변수 설정
                env = os.environ.copy()
                env["MCP_PORT"] = str(port)
                env["MCP_HOST"] = "0.0.0.0"
                
                # 디버그 출력
                logger.info(f"환경변수 설정: MCP_PORT={env['MCP_PORT']}, MCP_HOST={env['MCP_HOST']}")
                
                process = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=Path(__file__).parent.parent.parent,
                    env=env,
                    encoding="utf-8",
                    errors="replace",
                )
                
                # 서버가 시작될 때까지 대기
                await asyncio.sleep(3)
                if process.poll() is None:
                    self.processes[server_name] = process
                    logger.info(f"{server_name} 서버 시작됨 (PID: {process.pid})")
                else:
                    stdout, stderr = process.communicate()
                    logger.error(f"{server_name} 서버 시작 실패:\nstdout: {stdout}\nstderr: {stderr}")
                    
        except Exception as e:
            logger.error(f"{server_name} 서버 시작 실패: {e}")

    async def stop_all_servers(self):
        """모든 MCP 서버를 중지합니다."""
        logger.info("MCP 서버들을 중지합니다...")
        
        for server_name, process in self.processes.items():
            try:
                if process.poll() is None:  # 프로세스가 살아있음
                    process.terminate()
                    await asyncio.sleep(2)
                    
                    if process.poll() is None:  # 여전히 살아있으면 강제 종료
                        process.kill()
                        
                    logger.info(f"{server_name} 서버 정상 종료됨")
                else:
                    logger.info(f"{server_name} 서버는 이미 종료됨")
            except Exception as e:
                logger.error(f"{server_name} 서버 종료 실패: {e}")
                
        self.processes.clear()
        logger.info("모든 MCP 서버가 중지되었습니다.")
        
    async def restart_server(self, server_name: str):
        """특정 MCP 서버를 재시작합니다."""
        try:
            # 서버 중지
            if server_name in self.processes:
                process = self.processes[server_name]
                if process.poll() is None:
                    process.terminate()
                    await asyncio.sleep(2)
                    if process.poll() is None:
                        process.kill()
                del self.processes[server_name]
                
            # 서버 재시작
            if server_name in self.server_configs:
                config = self.server_configs[server_name]
                await self.start_server(server_name, config)
                logger.info(f"{server_name} 서버 재시작 완료")
            else:
                raise ValueError(f"알 수 없는 서버: {server_name}")
                
        except Exception as e:
            logger.error(f"{server_name} 서버 재시작 실패: {e}")
            raise

    def get_server_status(self) -> Dict[str, dict]:
        """모든 서버의 상태를 반환합니다."""
        status = {}

        for server_name, process in self.processes.items():
            is_running = process.poll() is None
            status[server_name] = {
                "running": is_running,
                "pid": process.pid if is_running else None,
                "config": self.server_configs.get(server_name, {}),
            }

        return status


# 전역 MCP 서버 매니저 인스턴스
mcp_server_manager = MCPServerManager()
