"use client"

import React, { useState, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { AlertCircle, CheckCircle, ChevronDown, ChevronRight, RefreshCw, Zap, Bug } from "lucide-react"
import { ModelService, ModelMBTI } from "@/lib/services/model.service"

// SOLID 원칙 적용: 인터페이스 분리 원칙 (ISP)
interface APITester {
  testAPI(): Promise<APITestResult>
}

interface LogViewer {
  getLogs(): LogEntry[]
  clearLogs(): void
}

interface StatusMonitor {
  getStatus(): ServiceStatus
}

// 테스트 결과 타입 정의
interface APITestResult {
  success: boolean
  data?: ModelMBTI[]
  error?: string
  responseTime: number
  statusCode?: number
  timestamp: string
}

interface LogEntry {
  level: 'info' | 'warn' | 'error' | 'success'
  message: string
  timestamp: string
  details?: any
}

interface ServiceStatus {
  isLoading: boolean
  dataCount: number
  lastUpdate: string
  hasError: boolean
}

interface MBTIDebugPanelProps {
  mbtiList: ModelMBTI[]
  isVisible?: boolean
  onToggleVisibility?: () => void
}

// SOLID 원칙 적용: 단일 책임 원칙 (SRP) - MBTI API 테스터
class MBTIAPITester implements APITester {
  async testAPI(): Promise<APITestResult> {
    const startTime = Date.now()
    const timestamp = new Date().toISOString()
    
    try {
      // 직접 API 호출 (서비스 레이어 우회하여 순수 테스트)
      const response = await fetch('http://localhost:8000/api/v1/influencers/mbti', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      const responseTime = Date.now() - startTime
      
      if (!response.ok) {
        return {
          success: false,
          error: `HTTP ${response.status}: ${response.statusText}`,
          responseTime,
          statusCode: response.status,
          timestamp
        }
      }
      
      const data = await response.json()
      
      return {
        success: true,
        data: Array.isArray(data) ? data : [],
        responseTime,
        statusCode: response.status,
        timestamp
      }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        responseTime: Date.now() - startTime,
        timestamp
      }
    }
  }
}

// SOLID 원칙 적용: 단일 책임 원칙 (SRP) - 로그 관리자
class DebugLogger implements LogViewer {
  private logs: LogEntry[] = []
  
  addLog(level: LogEntry['level'], message: string, details?: any) {
    const log: LogEntry = {
      level,
      message,
      timestamp: new Date().toLocaleTimeString(),
      details
    }
    this.logs.unshift(log) // 최신 로그를 위에 표시
    
    // 최대 50개 로그만 유지
    if (this.logs.length > 50) {
      this.logs = this.logs.slice(0, 50)
    }
  }
  
  getLogs(): LogEntry[] {
    return this.logs
  }
  
  clearLogs(): void {
    this.logs = []
  }
}

// SOLID 원칙 적용: 단일 책임 원칙 (SRP) - 상태 모니터
class MBTIStatusMonitor implements StatusMonitor {
  constructor(private mbtiList: ModelMBTI[]) {}
  
  getStatus(): ServiceStatus {
    return {
      isLoading: false,
      dataCount: this.mbtiList.length,
      lastUpdate: new Date().toLocaleTimeString(),
      hasError: this.mbtiList.length === 0
    }
  }
}

export function MBTIDebugPanel({ mbtiList, isVisible = true, onToggleVisibility }: MBTIDebugPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [testResult, setTestResult] = useState<APITestResult | null>(null)
  const [isTestingAPI, setIsTestingAPI] = useState(false)
  const [logger] = useState(() => new DebugLogger())
  const [logs, setLogs] = useState<LogEntry[]>([])
  
  // SOLID 원칙 적용: 의존 역전 원칙 (DIP) - 추상화에 의존
  const apiTester = new MBTIAPITester()
  const statusMonitor = new MBTIStatusMonitor(mbtiList)
  
  const addLog = useCallback((level: LogEntry['level'], message: string, details?: any) => {
    logger.addLog(level, message, details)
    setLogs(logger.getLogs())
  }, [logger])
  
  const handleAPITest = async () => {
    setIsTestingAPI(true)
    addLog('info', 'MBTI API 테스트 시작...')
    
    try {
      const result = await apiTester.testAPI()
      setTestResult(result)
      
      if (result.success) {
        addLog('success', `API 테스트 성공 (응답시간: ${result.responseTime}ms)`, {
          dataCount: result.data?.length || 0,
          statusCode: result.statusCode
        })
      } else {
        addLog('error', `API 테스트 실패: ${result.error}`, {
          statusCode: result.statusCode,
          responseTime: result.responseTime
        })
      }
    } catch (error) {
      addLog('error', '예상치 못한 오류 발생', error)
    } finally {
      setIsTestingAPI(false)
    }
  }
  
  const handleServiceLayerTest = async () => {
    addLog('info', 'ModelService를 통한 MBTI 로드 테스트 시작...')
    
    try {
      const data = await ModelService.getMBTIList()
      addLog('success', `ModelService 테스트 성공`, {
        dataCount: data.length,
        firstItem: data[0] || null
      })
    } catch (error) {
      addLog('error', 'ModelService 테스트 실패', error)
    }
  }
  
  const status = statusMonitor.getStatus()
  
  if (!isVisible) return null
  
  return (
    <Card className="border-2 border-blue-200 bg-gradient-to-r from-blue-50 to-indigo-50">
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-blue-100/50 transition-colors">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Bug className="h-5 w-5 text-blue-600" />
                <CardTitle className="text-lg text-blue-900">MBTI API 디버그 패널</CardTitle>
                <Badge variant={status.hasError ? "destructive" : "default"}>
                  {status.hasError ? "오류" : "정상"}
                </Badge>
              </div>
              <div className="flex items-center space-x-2">
                <Badge variant="outline" className="text-xs">
                  {status.dataCount}개 로드됨
                </Badge>
                {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </div>
            </div>
            <CardDescription className="text-blue-700">
              MBTI API 상태 모니터링 및 테스트 도구
            </CardDescription>
          </CardHeader>
        </CollapsibleTrigger>
        
        <CollapsibleContent>
          <CardContent className="space-y-6">
            {/* 상태 요약 */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="flex items-center space-x-2">
                {status.hasError ? (
                  <AlertCircle className="h-4 w-4 text-red-500" />
                ) : (
                  <CheckCircle className="h-4 w-4 text-green-500" />
                )}
                <span className="text-sm font-medium">
                  상태: {status.hasError ? "데이터 로드 실패" : "정상 작동"}
                </span>
              </div>
              <div className="text-sm">
                <span className="font-medium">데이터 개수:</span> {status.dataCount}개
              </div>
              <div className="text-sm">
                <span className="font-medium">마지막 업데이트:</span> {status.lastUpdate}
              </div>
            </div>
            
            {/* API 테스트 섹션 */}
            <div className="space-y-3">
              <h4 className="font-medium text-gray-900 flex items-center space-x-2">
                <Zap className="h-4 w-4 text-yellow-500" />
                <span>API 테스트</span>
              </h4>
              <div className="flex space-x-2">
                <Button
                  onClick={handleAPITest}
                  disabled={isTestingAPI}
                  size="sm"
                  variant="outline"
                  className="flex items-center space-x-1"
                >
                  {isTestingAPI ? (
                    <RefreshCw className="h-3 w-3 animate-spin" />
                  ) : (
                    <Zap className="h-3 w-3" />
                  )}
                  <span>직접 API 호출</span>
                </Button>
                <Button
                  onClick={handleServiceLayerTest}
                  size="sm"
                  variant="outline"
                >
                  ModelService 테스트
                </Button>
                <Button
                  onClick={() => {
                    setLogs([])
                    logger.clearLogs()
                  }}
                  size="sm"
                  variant="ghost"
                >
                  로그 클리어
                </Button>
              </div>
            </div>
            
            {/* 테스트 결과 */}
            {testResult && (
              <div className="space-y-2">
                <h4 className="font-medium text-gray-900">최근 테스트 결과</h4>
                <div className={`p-3 rounded-lg border ${
                  testResult.success ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
                }`}>
                  <div className="text-sm space-y-1">
                    <div className="flex justify-between">
                      <span className="font-medium">상태:</span>
                      <span className={testResult.success ? 'text-green-700' : 'text-red-700'}>
                        {testResult.success ? '성공' : '실패'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="font-medium">응답 시간:</span>
                      <span>{testResult.responseTime}ms</span>
                    </div>
                    {testResult.statusCode && (
                      <div className="flex justify-between">
                        <span className="font-medium">상태 코드:</span>
                        <span>{testResult.statusCode}</span>
                      </div>
                    )}
                    {testResult.success && testResult.data && (
                      <div className="flex justify-between">
                        <span className="font-medium">데이터 개수:</span>
                        <span>{testResult.data.length}개</span>
                      </div>
                    )}
                    {testResult.error && (
                      <div className="mt-2">
                        <span className="font-medium text-red-700">오류:</span>
                        <p className="text-red-600 text-xs mt-1">{testResult.error}</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
            
            {/* 실시간 로그 */}
            <div className="space-y-2">
              <h4 className="font-medium text-gray-900">실시간 로그</h4>
              <div className="bg-gray-900 text-green-400 p-3 rounded-lg font-mono text-xs max-h-32 overflow-y-auto">
                {logs.length === 0 ? (
                  <div className="text-gray-500">로그가 없습니다. API 테스트를 실행해보세요.</div>
                ) : (
                  logs.map((log, index) => (
                    <div key={index} className={`mb-1 ${
                      log.level === 'error' ? 'text-red-400' :
                      log.level === 'warn' ? 'text-yellow-400' :
                      log.level === 'success' ? 'text-green-400' :
                      'text-blue-400'
                    }`}>
                      <span className="text-gray-500">[{log.timestamp}]</span> {log.message}
                      {log.details && (
                        <div className="text-gray-400 ml-4 text-xs">
                          {JSON.stringify(log.details, null, 2)}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
            
            {/* MBTI 데이터 미리보기 */}
            {mbtiList.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-medium text-gray-900">로드된 MBTI 데이터 미리보기</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {mbtiList.slice(0, 4).map((mbti) => (
                    <div key={mbti.mbti_id} className="p-2 bg-white border rounded text-xs">
                      <div className="font-semibold">{mbti.mbti_name}</div>
                      <div className="text-gray-600 truncate">
                        {mbti.mbti_traits || mbti.mbti_traits || '설명 없음'}
                      </div>
                    </div>
                  ))}
                </div>
                {mbtiList.length > 4 && (
                  <div className="text-xs text-gray-500">
                    ... 외 {mbtiList.length - 4}개 더
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  )
}