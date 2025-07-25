import { Settings } from "lucide-react";

interface Model {
  id: string;
  [key: string]: any;
}

interface McpTabProps {
  model: Model;
  MCPServerSelector: React.ComponentType<{
    influencerId: string;
    model: Model;
  }>;
}

export default function McpTab({
  model,
  MCPServerSelector
}: McpTabProps) {
  return (
    <div className="p-8 text-center text-gray-700">
      <Settings className="h-8 w-8 mx-auto mb-2 text-blue-500" />
      <h2 className="text-xl font-bold mb-2">MCP 도구 관리</h2>
      <p className="text-gray-600 mb-6">
        MCP 서버 및 도구 상태를 확인하고, 챗봇 페이지에서 사용할 MCP
        서버를 선택할 수 있습니다.
      </p>
      <MCPServerSelector influencerId={model.id} model={model} />
    </div>
  );
}