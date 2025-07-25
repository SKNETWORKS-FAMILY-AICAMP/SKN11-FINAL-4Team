import {
  BarChart3,
  FileText,
  Download,
  Link2,
  Info,
  Mic,
  Settings
} from "lucide-react";
import { TabsList, TabsTrigger } from "@/components/ui/tabs";

interface TabsListProps {
  className?: string;
}

export default function ModelTabsList({ className }: TabsListProps) {
  return (
    <TabsList className={`grid w-full grid-cols-7 ${className || ""}`}>
      <TabsTrigger
        value="analytics"
        className="flex items-center space-x-2"
      >
        <BarChart3 className="h-4 w-4" />
        <span>분석</span>
      </TabsTrigger>
      <TabsTrigger
        value="content"
        className="flex items-center space-x-2"
      >
        <FileText className="h-4 w-4" />
        <span>콘텐츠</span>
      </TabsTrigger>
      <TabsTrigger value="api" className="flex items-center space-x-2">
        <Download className="h-4 w-4" />
        <span>API</span>
      </TabsTrigger>
      <TabsTrigger
        value="integrations"
        className="flex items-center space-x-2"
      >
        <Link2 className="h-4 w-4" />
        <span>연동</span>
      </TabsTrigger>
      <TabsTrigger
        value="settings"
        className="flex items-center space-x-2"
      >
        <Info className="h-4 w-4" />
        <span>정보</span>
      </TabsTrigger>
      <TabsTrigger value="voice" className="flex items-center space-x-2">
        <Mic className="h-4 w-4" />
        <span>음성</span>
      </TabsTrigger>
      <TabsTrigger value="mcp" className="flex items-center space-x-2">
        <Settings className="h-4 w-4" />
        <span>MCP</span>
      </TabsTrigger>
    </TabsList>
  );
}