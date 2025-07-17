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
                "transport": "stdio",
                "port": None,
                "description": "수학 계산 서버",
            },
            "weather": {
                "script": "examples/mcp_weather_server.py",
                "transport": "streamable-http",
                "port": 8002,
                "description": "날씨 정보 서버",
            },
            # 추가 MCP 서버들을 위한 포트 예약
            # "calculator": {
            #     "script": "examples/mcp_calculator_server.py",
            #     "transport": "streamable-http",
            #     "port": 8003,
            #     "description": "고급 계산기 서버",
            # },
            # "translator": {
            #     "script": "examples/mcp_translator_server.py",
            #     "transport": "streamable-http",
            #     "port": 8004,
            #     "description": "번역 서버",
            # },
            # "file_manager": {
            #     "script": "examples/mcp_file_manager_server.py",
            #     "transport": "streamable-http",
            #     "port": 8005,
            #     "description": "파일 관리 서버",
            # },
        }

    async def start_all_servers(self):
        """모든 MCP 서버를 시작합니다."""
        logger.info("MCP 서버들을 시작합니다...")

        # 백엔드 서버가 완전히 시작되었는지 확인
        await self._wait_for_backend_server()

        for server_name, config in self.server_configs.items():
            try:
                await self.start_server(server_name, config)
            except Exception as e:
                logger.error(f"{server_name} 서버 시작 실패: {e}")

        logger.info(f"{len(self.processes)}개의 MCP 서버가 시작되었습니다.")

    async def _wait_for_backend_server(self):
        """백엔드 서버가 완전히 시작될 때까지 대기합니다."""
        import httpx
        import asyncio

        max_retries = 15
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get("http://localhost:8000/", timeout=10.0)
                    if response.status_code == 200:
                        logger.info("백엔드 서버가 준비되었습니다.")
                        return
            except Exception as e:
                logger.info(
                    f"백엔드 서버 대기 중... (시도 {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(retry_delay)

        logger.warning("백엔드 서버 연결을 확인할 수 없지만 MCP 서버를 시작합니다.")

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
            elif config["transport"] == "streamable-http":
                # HTTP 서버는 포트를 지정하여 실행
                # .env 파일의 MCP_PORT를 우선 사용, 없으면 config의 포트 사용
                env = os.environ.copy()
                env_port = os.getenv("MCP_PORT")
                if env_port:
                    port = int(env_port)
                    logger.info(
                        f"{server_name} 서버를 .env의 포트 {port}에서 시작합니다..."
                    )
                else:
                    port = config.get("port", 8002)
                    logger.info(f"{server_name} 서버를 포트 {port}에서 시작합니다...")

                env["MCP_PORT"] = str(port)
                env["MCP_HOST"] = "0.0.0.0"
                process = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=Path(__file__).parent.parent.parent,
                    env=env,
                    encoding="utf-8",
                    errors="replace",
                )
            else:
                logger.error(f"지원하지 않는 transport: {config['transport']}")
                return

            # 프로세스가 정상적으로 시작되었는지 확인
            await asyncio.sleep(2)

            if process.poll() is None:  # 프로세스가 살아있음
                self.processes[server_name] = process
                logger.info(f"{server_name} 서버 시작됨 (PID: {process.pid})")
            else:
                # 프로세스가 종료된 경우 에러 로그 확인
                stdout, stderr = process.communicate()
                logger.error(f"{server_name} 서버 시작 실패:")
                if stdout:
                    logger.error(f"stdout: {stdout}")
                if stderr:
                    logger.error(f"stderr: {stderr}")

        except Exception as e:
            logger.error(f"{server_name} 서버 시작 중 오류: {e}")

    async def stop_all_servers(self):
        """모든 MCP 서버를 중지합니다."""
        logger.info("MCP 서버들을 중지합니다...")

        for server_name, process in self.processes.items():
            try:
                await self.stop_server(server_name, process)
            except Exception as e:
                logger.error(f"{server_name} 서버 중지 실패: {e}")

        self.processes.clear()
        logger.info("모든 MCP 서버가 중지되었습니다.")

    async def stop_server(self, server_name: str, process: subprocess.Popen):
        """특정 MCP 서버를 중지합니다."""
        try:
            # 프로세스가 살아있는 경우에만 종료 시도
            if process.poll() is None:
                # SIGTERM으로 정상 종료 시도
                process.terminate()

                # 5초 대기 후 강제 종료
                try:
                    process.wait(timeout=5)
                    logger.info(f"{server_name} 서버 정상 종료됨")
                except subprocess.TimeoutExpired:
                    process.kill()
                    logger.warning(f"{server_name} 서버 강제 종료됨")
            else:
                logger.info(f"{server_name} 서버는 이미 종료됨")

        except Exception as e:
            logger.error(f"{server_name} 서버 중지 중 오류: {e}")

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

    async def restart_server(self, server_name: str):
        """특정 서버를 재시작합니다."""
        if server_name in self.processes:
            await self.stop_server(server_name, self.processes[server_name])
            del self.processes[server_name]

        if server_name in self.server_configs:
            await self.start_server(server_name, self.server_configs[server_name])


# 전역 MCP 서버 매니저 인스턴스
mcp_server_manager = MCPServerManager()
