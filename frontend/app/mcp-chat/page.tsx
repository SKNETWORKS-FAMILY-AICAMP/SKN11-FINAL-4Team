"use client"

import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Loader2, Send, Bot, User, MessageSquare, Settings, Wrench, RefreshCw, Zap, Plus, Server } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { apiClient } from "@/lib/api"

interface Message {
    id: string
    content: string
    sender: "user" | "bot"
    timestamp: Date
    tools_used?: string[]
}

interface ToolInfo {
    name: string
    description: string
    type: "basic" | "mcp"
}

export default function MCPChatPage() {
    const [messages, setMessages] = useState<Message[]>([])
    const [inputMessage, setInputMessage] = useState("")
    const [isLoading, setIsLoading] = useState(false)
    const [sessionId, setSessionId] = useState<string>("")
    const [isInitialized, setIsInitialized] = useState(false)
    const [isInitializing, setIsInitializing] = useState(false)
    const [tools, setTools] = useState<ToolInfo[]>([])
    const [showToolsDialog, setShowToolsDialog] = useState(false)
    const [newServerName, setNewServerName] = useState("")
    const [newServerUrl, setNewServerUrl] = useState("")

    const messagesEndRef = useRef<HTMLDivElement>(null)

    // MCP 챗봇 초기화
    const initializeChatbot = async () => {
        try {
            setIsInitializing(true)
            await apiClient.post("/api/v1/mcp/init", undefined, { requireAuth: false })
            setIsInitialized(true)
            await loadTools()
            console.log("MCP 챗봇 초기화 완료")
        } catch (error) {
            console.error("초기화 중 오류:", error)
        } finally {
            setIsInitializing(false)
        }
    }

    // 도구 목록 로드
    const loadTools = async () => {
        try {
            const data = await apiClient.get("/api/v1/mcp/tools", { requireAuth: false })
            const toolList = Object.values(data.tools) as ToolInfo[]
            setTools(toolList)
        } catch (error) {
            console.error("도구 목록 로드 중 오류:", error)
        }
    }

    // 챗봇 상태 확인
    const checkStatus = async () => {
        try {
            const status = await apiClient.get("/api/v1/mcp/status", { requireAuth: false })
            setIsInitialized(status.initialized)
            if (status.initialized) {
                await loadTools()
            }
        } catch (error) {
            console.error("상태 확인 중 오류:", error)
        }
    }

    // 도구 다시 로드
    const reloadTools = async () => {
        try {
            await apiClient.post("/api/v1/mcp/tools/reload", undefined, { requireAuth: false })
            await loadTools()
            console.log("도구 다시 로드 완료")
        } catch (error) {
            console.error("도구 다시 로드 중 오류:", error)
        }
    }

    // 새 MCP 서버 추가
    const addMCPServer = async () => {
        if (!newServerName || !newServerUrl) return
        
        try {
            await apiClient.post(`/api/v1/mcp/servers/${newServerName}/add?server_url=${encodeURIComponent(newServerUrl)}`, undefined, { requireAuth: false })
            await reloadTools()
            setNewServerName("")
            setNewServerUrl("")
            setShowToolsDialog(false)
            console.log("MCP 서버 추가 완료")
        } catch (error) {
            console.error("MCP 서버 추가 중 오류:", error)
        }
    }

    // 초기 로드
    useEffect(() => {
        checkStatus()
    }, [])

    // 메시지 전송
    const sendMessage = async () => {
        if (!inputMessage.trim() || isLoading) return

        const userMessage: Message = {
            id: Date.now().toString(),
            content: inputMessage,
            sender: "user",
            timestamp: new Date(),
        }
        setMessages(prev => [...prev, userMessage])
        const currentMessage = inputMessage
        setInputMessage("")
        setIsLoading(true)

        try {
            const result = await apiClient.post("/api/v1/mcp/chat", {
                message: currentMessage,
                session_id: sessionId,
            }, { requireAuth: false })

            const botMessage: Message = {
                id: (Date.now() + 1).toString(),
                content: result.response,
                sender: "bot",
                timestamp: new Date(),
                tools_used: result.tools_used,
            }
            setMessages(prev => [...prev, botMessage])
            setSessionId(result.session_id)
        } catch (error) {
            console.error("Error sending message:", error)
            const errorMessage: Message = {
                id: (Date.now() + 1).toString(),
                content: "메시지 전송 중 오류가 발생했습니다. 다시 시도해주세요.",
                sender: "bot",
                timestamp: new Date(),
            }
            setMessages(prev => [...prev, errorMessage])
        } finally {
            setIsLoading(false)
        }
    }

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            sendMessage()
        }
    }

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }

    useEffect(() => {
        scrollToBottom()
    }, [messages])

    return (
        <div className="h-screen bg-gray-50">
            <div className="h-full flex flex-col p-4 max-w-4xl mx-auto">
                {/* 헤더 */}
                <Card className="mb-4">
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-3">
                                <Avatar className="h-10 w-10">
                                    <AvatarFallback className="bg-purple-500 text-white">
                                        <Zap className="h-5 w-5" />
                                    </AvatarFallback>
                                </Avatar>
                                <div>
                                    <CardTitle className="text-lg">확장 가능한 MCP 챗봇</CardTitle>
                                    <p className="text-sm text-gray-500">LangChain + 로컬 EXAONE 모델 + 동적 MCP 도구</p>
                                </div>
                            </div>
                            <div className="flex items-center space-x-2">
                                <Badge
                                    variant={isInitialized ? "default" : "secondary"}
                                    className="text-xs"
                                >
                                    {isInitialized ? "초기화됨" : "초기화 필요"}
                                </Badge>
                                <Dialog open={showToolsDialog} onOpenChange={setShowToolsDialog}>
                                    <DialogTrigger asChild>
                                        <Button variant="outline" size="sm">
                                            <Wrench className="h-4 w-4 mr-1" />
                                            도구 관리
                                        </Button>
                                    </DialogTrigger>
                                    <DialogContent>
                                        <DialogHeader>
                                            <DialogTitle>MCP 도구 관리</DialogTitle>
                                        </DialogHeader>
                                        <div className="space-y-4">
                                            <div>
                                                <Label>사용 가능한 도구 ({tools.length}개)</Label>
                                                <div className="mt-2 max-h-40 overflow-y-auto space-y-2">
                                                    {tools.map((tool, index) => (
                                                        <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                                                            <div>
                                                                <div className="font-medium">{tool.name}</div>
                                                                <div className="text-sm text-gray-600">{tool.description}</div>
                                                            </div>
                                                            <Badge variant={tool.type === "mcp" ? "default" : "secondary"} className="text-xs">
                                                                {tool.type}
                                                            </Badge>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                            <div className="space-y-2">
                                                <Label>새 MCP 서버 추가</Label>
                                                <Input
                                                    placeholder="서버 이름 (예: weather)"
                                                    value={newServerName}
                                                    onChange={(e) => setNewServerName(e.target.value)}
                                                />
                                                <Input
                                                    placeholder="서버 URL (예: http://localhost:8002)"
                                                    value={newServerUrl}
                                                    onChange={(e) => setNewServerUrl(e.target.value)}
                                                />
                                                <Button onClick={addMCPServer} disabled={!newServerName || !newServerUrl}>
                                                    <Plus className="h-4 w-4 mr-1" />
                                                    서버 추가
                                                </Button>
                                            </div>
                                            <Button onClick={reloadTools} variant="outline" className="w-full">
                                                <RefreshCw className="h-4 w-4 mr-1" />
                                                도구 다시 로드
                                            </Button>
                                        </div>
                                    </DialogContent>
                                </Dialog>
                                {!isInitialized && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={initializeChatbot}
                                        disabled={isInitializing}
                                    >
                                        {isInitializing ? (
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                        ) : (
                                            <RefreshCw className="h-4 w-4" />
                                        )}
                                        초기화
                                    </Button>
                                )}
                            </div>
                        </div>
                    </CardHeader>
                </Card>

                {/* 채팅 영역 */}
                <Card className="flex-1 mb-4">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center space-x-2">
                            <MessageSquare className="h-4 w-4" />
                            <span>대화</span>
                            {tools.length > 0 && (
                                <Badge variant="outline" className="text-xs">
                                    {tools.length}개 도구
                                </Badge>
                            )}
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="h-full flex flex-col">
                        <div className="flex-1 overflow-y-auto space-y-4 mb-4">
                            {messages.length === 0 ? (
                                <div className="text-center text-gray-500 py-8">
                                    <Bot className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                                    <p>안녕하세요! 확장 가능한 MCP 챗봇입니다.</p>
                                    <p className="text-sm mt-2">자연어로 질문해보세요. 예: "5와 3을 더해줘", "10의 제곱근은?"</p>
                                    {!isInitialized && (
                                        <div className="mt-4">
                                            <Button onClick={initializeChatbot} disabled={isInitializing}>
                                                {isInitializing ? (
                                                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                                ) : (
                                                    <Zap className="h-4 w-4 mr-2" />
                                                )}
                                                챗봇 초기화
                                            </Button>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                messages.map((message) => (
                                    <div
                                        key={message.id}
                                        className={`flex ${message.sender === "user" ? "justify-end" : "justify-start"}`}
                                    >
                                        <div className={`flex items-start space-x-2 max-w-[80%] ${message.sender === "user" ? "flex-row-reverse space-x-reverse" : ""}`}>
                                            <Avatar className="h-8 w-8">
                                                <AvatarFallback className={message.sender === "user" ? "bg-blue-500 text-white" : "bg-purple-500 text-white"}>
                                                    {message.sender === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                                                </AvatarFallback>
                                            </Avatar>
                                            <div className={`rounded-lg px-3 py-2 ${message.sender === "user" ? "bg-blue-500 text-white" : "bg-gray-100"}`}>
                                                <p className="text-sm">{message.content}</p>
                                                {message.tools_used && message.tools_used.length > 0 && (
                                                    <div className="mt-2 flex flex-wrap gap-1">
                                                        {message.tools_used.map((tool, index) => (
                                                            <Badge key={index} variant="outline" className="text-xs">
                                                                <Wrench className="h-3 w-3 mr-1" />
                                                                {tool}
                                                            </Badge>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* 입력 영역 */}
                        <div className="flex items-end space-x-2">
                            <Textarea
                                value={inputMessage}
                                onChange={(e) => setInputMessage(e.target.value)}
                                onKeyPress={handleKeyPress}
                                placeholder="메시지를 입력하세요... (예: 5와 3을 더해줘, 10의 제곱근은?)"
                                className="flex-1 resize-none"
                                rows={2}
                            />
                            <Button onClick={sendMessage} disabled={isLoading || !inputMessage.trim()}>
                                {isLoading ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <Send className="h-4 w-4" />
                                )}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
} 