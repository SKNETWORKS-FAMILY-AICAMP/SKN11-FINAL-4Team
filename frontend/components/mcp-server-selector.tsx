"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
    Server,
    Plus,
    Settings,
    CheckCircle,
    XCircle,
    Loader2,
    Trash2,
    Play,
    Square
} from "lucide-react"
import { toast } from "@/hooks/use-toast"

interface MCPServer {
    name: string
    url?: string
    port?: number
    description: string
    running: boolean
    config?: {
        script?: string
        transport?: string
        port?: number
        url?: string
    }
}

interface MCPServerSelectorProps {
    onServerChange?: (selectedServers: string[]) => void
    selectedServers?: string[]
}

export function MCPServerSelector({ onServerChange, selectedServers = [] }: MCPServerSelectorProps) {
    const [servers, setServers] = useState<MCPServer[]>([])
    const [loading, setLoading] = useState(true)
    const [selected, setSelected] = useState<string[]>(selectedServers)
    const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
    const [newServer, setNewServer] = useState({ name: "", url: "", description: "" })

    // 서버 목록 로드
    const loadServers = async () => {
        setLoading(true)
        try {
            const response = await fetch("/api/mcp/servers")
            const data = await response.json()

            if (data.servers) {
                const serverList = Object.entries(data.servers).map(([name, status]: [string, any]) => ({
                    name,
                    url: status.config?.url,
                    port: status.config?.port,
                    description: status.config?.description || `MCP 서버: ${name}`,
                    running: status.running || false,
                    config: status.config
                }))
                setServers(serverList)
            }
        } catch (error) {
            console.error("서버 목록 로드 실패:", error)
            toast({
                title: "오류",
                description: "MCP 서버 목록을 불러오는데 실패했습니다.",
                variant: "destructive"
            })
        } finally {
            setLoading(false)
        }
    }

    // 서버 추가
    const addServer = async () => {
        if (!newServer.name || !newServer.url) {
            toast({
                title: "입력 오류",
                description: "서버 이름과 URL을 입력해주세요.",
                variant: "destructive"
            })
            return
        }

        try {
            const response = await fetch(`/api/mcp/servers/${newServer.name}/add`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ server_url: newServer.url })
            })

            if (response.ok) {
                toast({
                    title: "성공",
                    description: `MCP 서버 '${newServer.name}'이 추가되었습니다.`
                })
                setNewServer({ name: "", url: "", description: "" })
                setIsAddDialogOpen(false)
                loadServers()
            } else {
                throw new Error("서버 추가 실패")
            }
        } catch (error) {
            console.error("서버 추가 실패:", error)
            toast({
                title: "오류",
                description: "MCP 서버 추가에 실패했습니다.",
                variant: "destructive"
            })
        }
    }

    // 서버 시작/중지
    const toggleServer = async (serverName: string, action: "start" | "stop") => {
        try {
            const response = await fetch(`/api/mcp/servers/${serverName}/${action}`, {
                method: "POST"
            })

            if (response.ok) {
                toast({
                    title: "성공",
                    description: `MCP 서버 '${serverName}'이 ${action === "start" ? "시작" : "중지"}되었습니다.`
                })
                loadServers()
            } else {
                throw new Error(`서버 ${action} 실패`)
            }
        } catch (error) {
            console.error(`서버 ${action} 실패:`, error)
            toast({
                title: "오류",
                description: `MCP 서버 ${action === "start" ? "시작" : "중지"}에 실패했습니다.`,
                variant: "destructive"
            })
        }
    }

    // 서버 제거
    const removeServer = async (serverName: string) => {
        if (!confirm(`정말로 MCP 서버 '${serverName}'을 제거하시겠습니까?`)) {
            return
        }

        try {
            const response = await fetch(`/api/mcp/servers/${serverName}`, {
                method: "DELETE"
            })

            if (response.ok) {
                toast({
                    title: "성공",
                    description: `MCP 서버 '${serverName}'이 제거되었습니다.`
                })
                setSelected(selected.filter(s => s !== serverName))
                loadServers()
            } else {
                throw new Error("서버 제거 실패")
            }
        } catch (error) {
            console.error("서버 제거 실패:", error)
            toast({
                title: "오류",
                description: "MCP 서버 제거에 실패했습니다.",
                variant: "destructive"
            })
        }
    }

    // 선택된 서버 변경
    const handleServerToggle = (serverName: string) => {
        const newSelected = selected.includes(serverName)
            ? selected.filter(s => s !== serverName)
            : [...selected, serverName]

        setSelected(newSelected)
        onServerChange?.(newSelected)
    }

    useEffect(() => {
        loadServers()
    }, [])

    useEffect(() => {
        setSelected(selectedServers)
    }, [selectedServers])

    if (loading) {
        return (
            <Card>
                <CardContent className="p-6">
                    <div className="flex items-center justify-center">
                        <Loader2 className="h-6 w-6 animate-spin" />
                        <span className="ml-2">MCP 서버 목록을 불러오는 중...</span>
                    </div>
                </CardContent>
            </Card>
        )
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                    <Server className="h-5 w-5" />
                    <h3 className="text-lg font-semibold">MCP 서버 관리</h3>
                </div>
                <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
                    <DialogTrigger asChild>
                        <Button size="sm" className="flex items-center space-x-2">
                            <Plus className="h-4 w-4" />
                            <span>서버 추가</span>
                        </Button>
                    </DialogTrigger>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>새 MCP 서버 추가</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4">
                            <div>
                                <Label htmlFor="server-name">서버 이름</Label>
                                <Input
                                    id="server-name"
                                    value={newServer.name}
                                    onChange={(e) => setNewServer({ ...newServer, name: e.target.value })}
                                    placeholder="예: websearch"
                                />
                            </div>
                            <div>
                                <Label htmlFor="server-url">서버 URL</Label>
                                <Input
                                    id="server-url"
                                    value={newServer.url}
                                    onChange={(e) => setNewServer({ ...newServer, url: e.target.value })}
                                    placeholder="예: https://websearch.mcpjs.dev"
                                />
                            </div>
                            <div>
                                <Label htmlFor="server-description">설명 (선택사항)</Label>
                                <Input
                                    id="server-description"
                                    value={newServer.description}
                                    onChange={(e) => setNewServer({ ...newServer, description: e.target.value })}
                                    placeholder="서버 설명"
                                />
                            </div>
                            <div className="flex justify-end space-x-2">
                                <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                                    취소
                                </Button>
                                <Button onClick={addServer}>추가</Button>
                            </div>
                        </div>
                    </DialogContent>
                </Dialog>
            </div>

            <div className="grid gap-4">
                {servers.map((server) => (
                    <Card key={server.name} className="relative">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center space-x-3">
                                    <div className="flex items-center space-x-2">
                                        <Switch
                                            checked={selected.includes(server.name)}
                                            onCheckedChange={() => handleServerToggle(server.name)}
                                        />
                                        <span className="font-medium">{server.name}</span>
                                    </div>
                                    <Badge variant={server.running ? "default" : "secondary"}>
                                        {server.running ? (
                                            <CheckCircle className="h-3 w-3 mr-1" />
                                        ) : (
                                            <XCircle className="h-3 w-3 mr-1" />
                                        )}
                                        {server.running ? "실행 중" : "중지됨"}
                                    </Badge>
                                </div>

                                <div className="flex items-center space-x-2">
                                    {server.running ? (
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => toggleServer(server.name, "stop")}
                                        >
                                            <Square className="h-4 w-4" />
                                        </Button>
                                    ) : (
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => toggleServer(server.name, "start")}
                                        >
                                            <Play className="h-4 w-4" />
                                        </Button>
                                    )}
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => removeServer(server.name)}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>

                            <div className="mt-2 text-sm text-muted-foreground">
                                {server.description}
                            </div>

                            {server.url && (
                                <div className="mt-1 text-xs text-muted-foreground">
                                    URL: {server.url}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                ))}
            </div>

            {servers.length === 0 && (
                <Card>
                    <CardContent className="p-6 text-center text-muted-foreground">
                        등록된 MCP 서버가 없습니다. 서버를 추가해주세요.
                    </CardContent>
                </Card>
            )}

            {selected.length > 0 && (
                <div className="mt-4 p-4 bg-muted rounded-lg">
                    <h4 className="font-medium mb-2">선택된 서버 ({selected.length}개)</h4>
                    <div className="flex flex-wrap gap-2">
                        {selected.map((serverName) => (
                            <Badge key={serverName} variant="secondary">
                                {serverName}
                            </Badge>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
} 