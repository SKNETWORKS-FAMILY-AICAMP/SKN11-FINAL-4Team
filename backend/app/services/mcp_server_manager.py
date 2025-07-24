import asyncio
import subprocess
import logging
import signal
import sys
import os
import json
from typing import Dict, List, Optional
from pathlib import Path
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class MCPServerManager:
    """MCP 서버들을 관리하는 매니저"""

    def __init__(self, db: Session = None):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.server_configs: Dict[str, dict] = {}
        self.db = db
        self._load_servers_from_database()

    def _load_servers_from_database(self):
        """데이터베이스에서 MCP 서버 설정을 로드합니다."""
        if not self.db:
            logger.error("데이터베이스 세션이 없습니다. MCP 서버를 로드할 수 없습니다.")
            self.server_configs = {}
            return

        try:
            from app.models.mcp_server import MCPServer

            # 데이터베이스에서 모든 MCP 서버 조회
            servers = self.db.query(MCPServer).all()

            for server in servers:
                try:
                    # JSON 설정을 파싱
                    config = json.loads(server.mcp_config)
                    config["description"] = (
                        server.description or f"{server.mcp_name} 서버"
                    )

                    # mcp_status에 따라 transport 설정
                    if server.mcp_status == 0:  # stdio
                        config["transport"] = "stdio"
                        logger.info(f"✅ MCP 서버 '{server.mcp_name}' 로드됨 (stdio)")
                    elif server.mcp_status == 1:  # SSE/외부 URL
                        config["transport"] = "sse"
                        logger.info(
                            f"✅ MCP 서버 '{server.mcp_name}' 로드됨 (SSE/외부 URL)"
                        )
                    elif server.mcp_status == 2:  # streamable-http (로컬 스크립트)
                        config["transport"] = "streamable-http"
                        logger.info(
                            f"✅ MCP 서버 '{server.mcp_name}' 로드됨 (streamable-http)"
                        )
                    else:
                        logger.warning(
                            f"⚠️ MCP 서버 '{server.mcp_name}'의 알 수 없는 상태: {server.mcp_status}"
                        )
                        continue

                    self.server_configs[server.mcp_name] = config

                except json.JSONDecodeError as e:
                    logger.error(f"❌ MCP 서버 '{server.mcp_name}' 설정 파싱 실패: {e}")
                except Exception as e:
                    logger.error(f"❌ MCP 서버 '{server.mcp_name}' 로드 실패: {e}")

            logger.info(
                f"📊 총 {len(self.server_configs)}개의 MCP 서버가 로드되었습니다."
            )

        except Exception as e:
            logger.error(f"❌ 데이터베이스에서 MCP 서버 로드 실패: {e}")
            self.server_configs = {}

    def refresh_servers(self, db: Session):
        """데이터베이스에서 서버 설정을 새로고침합니다."""
        self.db = db
        self.server_configs.clear()
        self._load_servers_from_database()
        logger.info("🔄 MCP 서버 설정이 새로고침되었습니다.")

    async def start_all_servers(self):
        """데이터베이스의 모든 MCP 서버를 시작합니다."""
        logger.info("데이터베이스의 MCP 서버들을 시작합니다...")

        # langchain-mcp-adapters 사용 가능 여부 확인
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            from langchain_mcp_adapters.tools import load_mcp_tools

            logger.info("✅ langchain-mcp-adapters 사용 가능")
        except ImportError as e:
            logger.warning(f"⚠️ langchain-mcp-adapters가 설치되지 않았습니다: {e}")
            logger.warning("⚠️ MCP 서버 시작을 건너뜁니다.")
            return

        # 데이터베이스에서 서버 설정이 로드되었는지 확인
        if not self.server_configs:
            logger.warning("⚠️ 데이터베이스에 MCP 서버가 없습니다.")
            return

        # MCP 서버들을 바로 시작
        logger.info(f"🚀 {len(self.server_configs)}개의 MCP 서버를 시작합니다...")

        started_count = 0
        for server_name, config in self.server_configs.items():
            try:
                await self._start_server_with_config(server_name, config)
                started_count += 1
                logger.info(f"✅ {server_name} 서버 시작 완료")
            except Exception as e:
                logger.error(f"❌ {server_name} 서버 시작 실패: {e}")

        logger.info(f"📊 총 {started_count}개의 MCP 서버가 성공적으로 시작되었습니다.")

    async def _is_port_in_use(self, port: int) -> bool:
        """포트가 사용 중인지 확인합니다."""
        import socket

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex(("localhost", port))
                return result == 0
        except Exception:
            return False

    async def start_server(self, server_name: str):
        """특정 MCP 서버를 시작합니다."""
        try:
            if server_name not in self.server_configs:
                raise ValueError(f"알 수 없는 서버: {server_name}")

            config = self.server_configs[server_name]
            await self._start_server_with_config(server_name, config)

        except Exception as e:
            logger.error(f"MCP 서버 '{server_name}' 시작 실패: {e}")
            raise

    async def _start_server_with_config(self, server_name: str, config: dict):
        """설정을 사용하여 특정 MCP 서버를 시작합니다.

        실행 방법:
        - mcp_status = 0 (stdio): 명령어 실행 방식 (npx, cmd 등)
        - mcp_status = 1 (SSE로 받아오면): streamable-http 방식 (포트 기반)
        """

        # 명령어 실행 방식의 MCP 서버인 경우 (stdio - mcp_status = 0)
        if "command" in config and "args" in config:
            logger.info(f"🚀 {server_name} 서버는 명령어 실행 방식입니다 (stdio)")
            await self._start_command_mcp_server(server_name, config)
            return

        # 외부 URL 기반 서버인 경우 (streamable-http - mcp_status = 1)
        if "url" in config and "script" not in config:
            logger.info(
                f"🌐 {server_name} 서버는 외부 HTTP 기반 서버입니다 (streamable-http): {config['url']}"
            )
            # 외부 HTTP 서버는 프로세스를 시작하지 않고 상태만 등록
            self.processes[server_name] = None  # 외부 서버는 프로세스 없음
            logger.info(f"✅ {server_name} 외부 HTTP 서버 등록됨")
            return

        # 로컬 스크립트 기반 서버인 경우 (streamable-http - mcp_status = 1)
        if "script" not in config:
            logger.error(
                f"❌ {server_name} 서버에 script, url 또는 command가 설정되지 않았습니다."
            )
            return

        # 스크립트 기반 서버 실행 (streamable-http)
        script_path = Path(__file__).parent.parent.parent / config["script"]

        if not script_path.exists():
            logger.error(f"스크립트 파일을 찾을 수 없습니다: {script_path}")
            raise FileNotFoundError(f"스크립트 파일을 찾을 수 없습니다: {script_path}")

        try:
            if config["transport"] == "streamable-http":
                # 포트 자동 할당 또는 환경변수에서 가져오기
                port = config.get("port")
                if port is None:
                    # 환경변수에서 포트 가져오기
                    port = os.environ.get("MCP_PORT", 8000)
                    # 사용 가능한 포트 찾기
                    base_port = int(port)
                    for i in range(100):  # 8000-8099 범위에서 사용 가능한 포트 찾기
                        test_port = base_port + i
                        if not await self._is_port_in_use(test_port):
                            port = test_port
                            break
                    else:
                        logger.error(
                            f"사용 가능한 포트를 찾을 수 없습니다. {server_name} 서버를 건너뜁니다."
                        )
                        return

                # 포트가 사용 중인지 확인
                if await self._is_port_in_use(port):
                    logger.warning(
                        f"포트 {port}가 이미 사용 중입니다. {server_name} 서버를 건너뜁니다."
                    )
                    return

                logger.info(f"{server_name} 서버를 포트 {port}에서 시작합니다...")

                # 환경변수 설정
                env = os.environ.copy()
                env["MCP_PORT"] = str(port)
                env["MCP_HOST"] = "0.0.0.0"

                # 디버그 출력
                logger.info(
                    f"환경변수 설정: MCP_PORT={env['MCP_PORT']}, MCP_HOST={env['MCP_HOST']}"
                )

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
                    logger.error(
                        f"{server_name} 서버 시작 실패:\nstdout: {stdout}\nstderr: {stderr}"
                    )
                    raise RuntimeError(f"{server_name} 서버 시작 실패: {stderr}")

        except Exception as e:
            logger.error(f"{server_name} 서버 시작 중 예외 발생: {e}")
            raise

    async def _start_command_mcp_server(self, server_name: str, config: dict):
        """명령어 실행 방식의 MCP 서버를 시작합니다."""
        try:
            import asyncio
            import subprocess

            command = config["command"]
            args = config["args"]

            logger.info(
                f"🚀 명령어 실행 방식 MCP 서버 시작: {command} {' '.join(args)}"
            )

            # 서브프로세스로 MCP 서버 실행
            process = subprocess.Popen(
                [command] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # 프로세스가 정상적으로 시작되었는지 확인
            await asyncio.sleep(3)
            if process.poll() is None:
                self.processes[server_name] = process
                logger.info(
                    f"{server_name} 명령어 실행 MCP 서버 시작됨 (PID: {process.pid})"
                )
            else:
                stdout, stderr = process.communicate()
                logger.error(
                    f"{server_name} 명령어 실행 MCP 서버 시작 실패:\nstdout: {stdout}\nstderr: {stderr}"
                )
                raise RuntimeError(
                    f"{server_name} 명령어 실행 MCP 서버 시작 실패: {stderr}"
                )

        except Exception as e:
            error_msg = f"{server_name} 명령어 실행 MCP 서버 시작 실패: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    async def _start_external_mcp_server(self, server_name: str, config: dict):
        """외부 MCP 서버를 표준 MCP 프로토콜로 연결합니다."""
        try:
            import asyncio
            import subprocess
            from mcp.client import ClientSession, StdioServerParameters

            # 외부 MCP 서버 설정
            if server_name == "websearch":
                # Exa Search MCP 서버
                cmd = [
                    "npx",
                    "-y",
                    "@smithery/cli@latest",
                    "run",
                    "exa",
                    "--key",
                    "424b5510-2224-480b-a976-93ed248876ca",
                    "--profile",
                    "controversial-swallow-jyXJrS",
                ]
            else:
                logger.error(f"알 수 없는 외부 MCP 서버: {server_name}")
                return

            # 서브프로세스로 외부 MCP 서버 실행
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # 프로세스가 정상적으로 시작되었는지 확인
            await asyncio.sleep(2)
            if process.poll() is None:
                self.processes[server_name] = process
                logger.info(f"{server_name} 외부 MCP 서버 시작됨 (PID: {process.pid})")
            else:
                stdout, stderr = process.communicate()
                logger.error(
                    f"{server_name} 외부 MCP 서버 시작 실패:\nstdout: {stdout}\nstderr: {stderr}"
                )

        except Exception as e:
            error_msg = f"{server_name} 외부 MCP 서버 시작 실패: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    async def stop_all_servers(self):
        """모든 MCP 서버를 중지합니다."""
        logger.info("MCP 서버들을 중지합니다...")

        for server_name, process in self.processes.items():
            try:
                if process is None:  # 외부 서버는 프로세스가 없으므로 건너뛰기
                    continue

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
                if process is not None:  # 외부 서버가 아닌 경우에만 처리
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

        # 모든 서버 설정을 포함
        for server_name, config in self.server_configs.items():
            is_running = False
            pid = None

            # 실행 중인 프로세스 확인
            if server_name in self.processes:
                process = self.processes[server_name]
                if process is None:  # 외부 서버
                    is_running = True  # 외부 서버는 항상 사용 가능하다고 가정
                    pid = None
                else:  # 로컬 서버
                    is_running = process.poll() is None
                    pid = process.pid if is_running else None

            status[server_name] = {
                "running": is_running,
                "pid": pid,
                "config": config,
            }

        return status

    async def add_server(self, server_name: str, server_url: str):
        """새로운 MCP 서버를 추가합니다."""
        try:
            # URL에서 포트 추출
            if ":" in server_url:
                host, port_str = server_url.split(":", 1)
                port = int(port_str)
            else:
                port = 8000  # 기본 포트

            # 서버 설정 추가
            self.server_configs[server_name] = {
                "url": server_url,
                "port": port,
                "description": f"동적으로 추가된 서버: {server_name}",
            }

            logger.info(f"MCP 서버 '{server_name}' 추가됨: {server_url}")

        except Exception as e:
            logger.error(f"MCP 서버 '{server_name}' 추가 실패: {e}")
            raise

    async def remove_server(self, server_name: str):
        """MCP 서버를 제거합니다."""
        try:
            # 서버 중지
            if server_name in self.processes:
                process = self.processes[server_name]
                if process is not None:  # 외부 서버가 아닌 경우에만 처리
                    if process.poll() is None:
                        process.terminate()
                        await asyncio.sleep(2)
                        if process.poll() is None:
                            process.kill()
                del self.processes[server_name]

            # 설정 제거
            if server_name in self.server_configs:
                del self.server_configs[server_name]

            logger.info(f"MCP 서버 '{server_name}' 제거됨")

        except Exception as e:
            logger.error(f"MCP 서버 '{server_name}' 제거 실패: {e}")
            raise

    async def stop_server(self, server_name: str):
        """특정 MCP 서버를 중지합니다."""
        try:
            if server_name in self.processes:
                process = self.processes[server_name]
                if process is not None:  # 외부 서버가 아닌 경우에만 처리
                    if process.poll() is None:
                        process.terminate()
                        await asyncio.sleep(2)
                        if process.poll() is None:
                            process.kill()
                del self.processes[server_name]
                logger.info(f"MCP 서버 '{server_name}' 중지됨")
            else:
                logger.warning(f"MCP 서버 '{server_name}'는 실행 중이 아닙니다.")

        except Exception as e:
            logger.error(f"MCP 서버 '{server_name}' 중지 실패: {e}")
            raise


# 전역 MCP 서버 매니저 인스턴스 (기본 설정으로 초기화)
mcp_server_manager = MCPServerManager()


def get_mcp_server_manager(db: Session = None) -> MCPServerManager:
    """데이터베이스 세션과 함께 MCP 서버 매니저를 반환합니다."""
    if db:
        # 새로운 데이터베이스 세션으로 매니저 새로고침
        mcp_server_manager.refresh_servers(db)
    return mcp_server_manager
