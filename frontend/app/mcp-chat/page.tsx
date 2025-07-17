"use client"

import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Loader2, Send, Bot, User, MessageSquare, Settings, Wrench, RefreshCw } from "lucide-react"
import { MCPService, type MCPServerInfo, type MCPToolInfo } from "@/lib/services/mcp.service"

interface Message {
    id: string
    content: string
    sender: "user" | "bot"
    timestamp: Date
    tools_used?: string[]
}

export default function MCPChatPage() {
    const [messages, setMessages] = useState<Message[]>([])
    const [inputMessage, setInputMessage] = useState("")
    const [isLoading, setIsLoading] = useState(false)
    const [selectedServer, setSelectedServer] = useState<string>("")
    const [servers, setServers] = useState<MCPServerInfo[]>([])
    const [tools, setTools] = useState<MCPToolInfo[]>([])
    const [sessionId, setSessionId] = useState<string>("")
    const [isRestarting, setIsRestarting] = useState<string | null>(null)

    const messagesEndRef = useRef<HTMLDivElement>(null)

    // MCP 서버 목록 로드
    const loadServers = async () => {
        try {
            const response = await MCPService.getServers()
            setServers(response.servers)
            if (response.servers.length > 0) {
                setSelectedServer(response.servers[0].name)
            }
        } catch (error) {
            console.error("Error loading MCP servers:", error)
        }
    }

    // 선택된 서버의 도구 목록 로드
    const loadTools = async (serverName: string) => {
        try {
            const response = await MCPService.getTools(serverName)
            setTools(response.tools)
        } catch (error) {
            console.error("Error loading MCP tools:", error)
            setTools([])
        }
    }

    // 서버 변경 시 도구 목록 업데이트
    useEffect(() => {
        if (selectedServer) {
            loadTools(selectedServer)
        }
    }, [selectedServer])

    // 서버 재시작 함수
    const restartServer = async (serverName: string) => {
        try {
            setIsRestarting(serverName)
            await MCPService.restartServer(serverName)
            // 서버 목록 새로고침
            await loadServers()
            // 현재 선택된 서버가 재시작된 서버라면 도구 목록도 새로고침
            if (selectedServer === serverName) {
                await loadTools(serverName)
            }
        } catch (error) {
            console.error("Error restarting server:", error)
        } finally {
            setIsRestarting(null)
        }
    }

    // 초기 로드
    useEffect(() => {
        loadServers()
    }, [])

    // 메시지 전송
    const sendMessage = async () => {
        if (!inputMessage.trim() || !selectedServer || isLoading) return

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
            const response = await MCPService.chat({
                message: currentMessage,
                server_name: selectedServer,
                session_id: sessionId,
            })

            const botMessage: Message = {
                id: (Date.now() + 1).toString(),
                content: response.response,
                sender: "bot",
                timestamp: new Date(),
                tools_used: response.tools_used,
            }
            setMessages(prev => [...prev, botMessage])
            setSessionId(response.session_id)
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
                                    <AvatarFallback className="bg-blue-500 text-white">
                                        <Wrench className="h-5 w-5" />
                                    </AvatarFallback>
                                </Avatar>
                                <div>
                                    <CardTitle className="text-lg">MCP 챗봇</CardTitle>
                                    <p className="text-sm text-gray-500">Model Context Protocol을 사용한 AI 대화</p>
                                </div>
                            </div>
                            <div className="flex items-center space-x-2">
                                <Settings className="h-4 w-4 text-gray-400" />
                                <Select value={selectedServer} onValueChange={setSelectedServer}>
                                    <SelectTrigger className="w-48">
                                        <SelectValue placeholder="서버 선택" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {servers.map((server) => (
                                            <SelectItem key={server.name} value={server.name}>
                                                <div className="flex items-center justify-between">
                                                    <span>{server.description}</span>
                                                    <div className="flex items-center space-x-2">
                                                        <Badge
                                                            variant={server.running ? "default" : "secondary"}
                                                            className="text-xs"
                                                        >
                                                            {server.running ? "실행중" : "중지됨"}
                                                        </Badge>
                                                        {isRestarting === server.name && (
                                                            <RefreshCw className="h-3 w-3 animate-spin" />
                                                        )}
                                                    </div>
                                                </div>
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                {selectedServer && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => restartServer(selectedServer)}
                                        disabled={isRestarting === selectedServer}
                                    >
                                        <RefreshCw className={`h-4 w-4 ${isRestarting === selectedServer ? 'animate-spin' : ''}`} />
                                    </Button>
                                )}
                            </div>
                        </div>
                    </CardHeader>
                </Card>

                <div className="flex-1 flex gap-4 min-h-0">
                    {/* 도구 목록 사이드바 */}
                    <Card className="w-80 flex-shrink-0">
                        <CardHeader>
                            <CardTitle className="text-sm">사용 가능한 도구</CardTitle>
                        </CardHeader>
                        <CardContent className="overflow-y-auto max-h-96">
                            {tools.length === 0 ? (
                                <p className="text-sm text-gray-500">도구를 불러오는 중...</p>
                            ) : (
                                <div className="space-y-2">
                                    {tools.map((tool) => (
                                        <div key={tool.name} className="p-3 border rounded-lg">
                                            <div className="font-medium text-sm">{tool.name}</div>
                                            <div className="text-xs text-gray-500 mt-1">{tool.description}</div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* 채팅 영역 */}
                    <Card className="flex-1 flex flex-col min-h-0">
                        <CardContent className="flex-1 flex flex-col p-0 h-full">
                            {/* 메시지 영역 */}
                            <div className="flex-1 overflow-y-auto p-6 space-y-4 min-h-0">
                                {messages.length === 0 ? (
                                    <div className="text-center py-12">
                                        <MessageSquare className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                                        <p className="text-gray-500 text-lg">대화를 시작해보세요!</p>
                                        <p className="text-gray-400 mt-2">MCP 도구들을 활용한 AI와 대화할 수 있습니다.</p>
                                    </div>
                                ) : (
                                    messages.map((message) => (
                                        <div
                                            key={message.id}
                                            className={`flex ${message.sender === "user" ? "justify-end" : "justify-start"}`}
                                        >
                                            <div className={`flex items-start space-x-3 max-w-[70%] ${message.sender === "user" ? "flex-row-reverse space-x-reverse" : ""}`}>
                                                <Avatar className="h-8 w-8">
                                                    <AvatarFallback className={message.sender === "user" ? "bg-blue-500 text-white" : "bg-green-500 text-white"}>
                                                        {message.sender === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                                                    </AvatarFallback>
                                                </Avatar>

                                                <div className={`rounded-lg px-4 py-2 ${message.sender === "user"
                                                    ? "bg-blue-500 text-white"
                                                    : "bg-gray-100 text-gray-900"
                                                    }`}>
                                                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                                                    {message.tools_used && message.tools_used.length > 0 && (
                                                        <div className="mt-2 flex flex-wrap gap-1">
                                                            {message.tools_used.map((tool) => (
                                                                <Badge key={tool} variant="secondary" className="text-xs">
                                                                    {tool}
                                                                </Badge>
                                                            ))}
                                                        </div>
                                                    )}
                                                    <p className={`text-xs mt-1 ${message.sender === "user" ? "text-blue-100" : "text-gray-500"}`}>
                                                        {message.timestamp.toLocaleTimeString('ko-KR', {
                                                            hour: '2-digit',
                                                            minute: '2-digit'
                                                        })}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    ))
                                )}

                                {isLoading && (
                                    <div className="flex justify-start">
                                        <div className="flex items-start space-x-3 max-w-[70%]">
                                            <Avatar className="h-8 w-8">
                                                <AvatarFallback className="bg-green-500 text-white">
                                                    <Bot className="h-4 w-4" />
                                                </AvatarFallback>
                                            </Avatar>
                                            <div className="bg-gray-100 rounded-lg px-4 py-2">
                                                <div className="flex items-center space-x-2">
                                                    <Loader2 className="h-4 w-4 animate-spin text-gray-500" />
                                                    <span className="text-sm text-gray-500">답변을 생성하고 있습니다...</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                <div ref={messagesEndRef} />
                            </div>

                            {/* 입력 영역 */}
                            <div className="border-t p-4">
                                <div className="flex space-x-2">
                                    <Textarea
                                        value={inputMessage}
                                        onChange={(e) => setInputMessage(e.target.value)}
                                        onKeyPress={handleKeyPress}
                                        placeholder="메시지를 입력하세요..."
                                        className="flex-1 resize-none"
                                        rows={1}
                                        disabled={isLoading || !selectedServer}
                                    />
                                    <Button
                                        onClick={sendMessage}
                                        disabled={!inputMessage.trim() || isLoading || !selectedServer}
                                        size="sm"
                                        className="self-end"
                                    >
                                        <Send className="h-4 w-4" />
                                    </Button>
                                </div>
                                <p className="text-xs text-gray-500 mt-2">
                                    Enter로 전송, Shift+Enter로 줄바꿈
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    )
} 