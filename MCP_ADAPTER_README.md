# MCP (Model Context Protocol) 어댑터

이 프로젝트는 [LangChain MCP Adapters](https://github.com/langchain-ai/langchain-mcp-adapters)를 참고하여 구현된 MCP 어댑터입니다. MCP를 통해 다양한 도구들을 챗봇과 연동하여 사용할 수 있습니다.

## 🚀 주요 기능

- **MCP 서버 연결**: 다양한 MCP 서버와 연결하여 도구들을 사용
- **챗봇 통합**: MCP 도구들을 활용한 AI 챗봇 대화
- **도구 실행**: 개별 MCP 도구를 직접 실행
- **서버 관리**: MCP 서버 목록 조회 및 도구 목록 확인

## 📁 프로젝트 구조

```
backend/
├── app/
│   ├── services/
│   │   └── mcp_client.py          # MCP 클라이언트 서비스
│   ├── schemas/
│   │   └── mcp.py                 # MCP 관련 Pydantic 스키마
│   └── api/v1/endpoints/
│       └── mcp.py                 # MCP API 엔드포인트
├── examples/
│   ├── mcp_math_server.py         # 수학 계산 MCP 서버
│   └── mcp_weather_server.py      # 날씨 정보 MCP 서버
└── requirements.txt                # MCP 의존성 포함

frontend/
├── app/
│   └── mcp-chat/
│       └── page.tsx               # MCP 챗봇 페이지
├── lib/services/
│   └── mcp.service.ts             # MCP 프론트엔드 서비스
└── components/
    └── navigation.tsx             # 네비게이션에 MCP 링크 추가
```

## 🛠️ 설치 및 설정

### 1. 백엔드 의존성 설치

```bash
cd backend
pip install -r requirements.txt
```

### 2. 백엔드 서버 실행 (MCP 서버 자동 시작)

```bash
cd backend
python run.py
```

**🎉 자동 시작 기능**: 백엔드 서버가 시작되면 MCP 서버들(수학 서버, 날씨 서버)이 자동으로 함께 시작됩니다!

### 3. 수동으로 MCP 서버 실행 (선택사항)

개발 중에 MCP 서버를 별도로 실행하고 싶다면:

#### 수학 서버 (stdio)
```bash
cd backend
python examples/mcp_math_server.py
```

#### 날씨 서버 (streamable HTTP)
```bash
cd backend
python examples/mcp_weather_server.py
```

### 4. 프론트엔드 실행

```bash
cd frontend
npm run dev
```

## 📖 사용법

### 1. MCP 챗봇 접속

브라우저에서 `http://localhost:3000/mcp-chat`에 접속하여 MCP 챗봇을 사용할 수 있습니다.

### 2. 서버 선택

챗봇 페이지에서 사용할 MCP 서버를 선택합니다:
- **Math Server**: 수학 계산 도구들 (덧셈, 뺄셈, 곱셈, 나눗셈, 거듭제곱, 제곱근, 팩토리얼, 최대공약수, 최소공배수, 이차방정식 해)
- **Weather Server**: 날씨 정보 도구들 (현재 날씨, 날씨 예보, 대기질, 자외선 지수, 바람 정보, 일출/일몰)

### 3. 대화 시작

선택한 서버의 도구들을 활용하여 AI와 대화할 수 있습니다:

```
사용자: "15와 25를 더해줘"
AI: "15 + 25 = 40입니다."

사용자: "서울의 현재 날씨는 어때?"
AI: "서울의 현재 날씨는 온도 22°C, 맑음, 습도 45%입니다."

사용자: "x² + 5x + 6 = 0의 해를 구해줘"
AI: "이차방정식 x² + 5x + 6 = 0의 해는 x = -2, x = -3입니다."
```

## 🔧 API 엔드포인트

### MCP 서버 목록 조회
```
GET /api/v1/mcp/servers
```

### MCP 서버 재시작
```
POST /api/v1/mcp/servers/{server_name}/restart
```

### MCP 도구 목록 조회
```
GET /api/v1/mcp/tools/{server_name}
```

### MCP 도구 실행
```
POST /api/v1/mcp/tools/execute
{
  "server_name": "math",
  "tool_name": "add",
  "parameters": {
    "a": 10,
    "b": 20
  }
}
```

### MCP 챗봇 대화
```
POST /api/v1/mcp/chat
{
  "message": "15와 25를 더해줘",
  "server_name": "math",
  "session_id": "optional_session_id"
}
```

### 서버 상태 확인
```
GET /health
GET /mcp/status
```

## 🛠️ 커스텀 MCP 서버 개발

### 1. FastMCP 서버 생성

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("My Custom Server")

@mcp.tool()
async def my_custom_tool(param1: str, param2: int) -> dict:
    """커스텀 도구 설명"""
    # 도구 로직 구현
    result = {"result": "success", "data": param1}
    return result

if __name__ == "__main__":
    mcp.run(transport="stdio")  # 또는 "streamable-http"
```

### 2. 서버 설정 추가

`backend/app/services/mcp_client.py`에서 새로운 서버 설정을 추가:

```python
server_config = {
    "math": {...},
    "weather": {...},
    "my_custom": {
        "command": "python",
        "args": ["path/to/my_custom_server.py"],
        "transport": "stdio",
    }
}
```

## 🔍 디버깅

### 로그 확인

백엔드 로그에서 MCP 관련 메시지를 확인할 수 있습니다:

```bash
# 백엔드 로그 확인
tail -f backend/logs/app.log
```

### 서버 상태 확인

```bash
# 전체 서버 상태 확인
curl http://localhost:8000/health

# MCP 서버 상태 확인
curl http://localhost:8000/mcp/status

# 수학 서버 테스트
curl -X POST http://localhost:8000/api/v1/mcp/tools/execute \
  -H "Content-Type: application/json" \
  -d '{"server_name": "math", "tool_name": "add", "parameters": {"a": 5, "b": 3}}'
```

### MCP 서버 관리

```bash
# 특정 서버 재시작
curl -X POST http://localhost:8000/api/v1/mcp/servers/math/restart
```

## 📚 참고 자료

- [LangChain MCP Adapters](https://github.com/langchain-ai/langchain-mcp-adapters)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://mcpjs.dev/)

## 🤝 기여하기

1. 이슈를 생성하여 버그나 기능 요청을 알려주세요
2. Pull Request를 통해 개선사항을 제안해주세요
3. 새로운 MCP 서버나 도구를 개발하여 기여해주세요

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 