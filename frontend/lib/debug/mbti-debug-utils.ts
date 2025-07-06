// MBTI 디버깅을 위한 전역 유틸리티 함수들
// create-model 페이지의 useEffect에서 이 함수들을 window 객체에 등록

import { ModelService, type ModelMBTI } from '@/lib/services/model.service'

// SOLID 원칙 적용: 단일 책임 원칙 (SRP) - MBTI 테스터 클래스
export class MBTIDebugger {
  private static instance: MBTIDebugger
  private cache: ModelMBTI[] = []
  private lastFetchTime: number = 0
  
  static getInstance(): MBTIDebugger {
    if (!MBTIDebugger.instance) {
      MBTIDebugger.instance = new MBTIDebugger()
    }
    return MBTIDebugger.instance
  }
  
  // API 직접 호출 테스트
  async testDirectAPI(): Promise<{
    success: boolean
    data?: ModelMBTI[]
    error?: string
    responseTime: number
    cacheUsed: boolean
  }> {
    console.log('🔍 Direct MBTI API Test Starting...')
    const startTime = Date.now()
    
    try {
      const response = await fetch('http://localhost:8000/api/v1/influencers/mbti', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      const responseTime = Date.now() - startTime
      
      if (!response.ok) {
        const error = `HTTP ${response.status}: ${response.statusText}`
        console.error('❌ API Error:', error)
        return { success: false, error, responseTime, cacheUsed: false }
      }
      
      const data = await response.json()
      this.cache = Array.isArray(data) ? data : []
      this.lastFetchTime = Date.now()
      
      console.log('✅ API Success:', {
        dataCount: this.cache.length,
        responseTime: `${responseTime}ms`,
        firstItem: this.cache[0] || null
      })
      
      return { success: true, data: this.cache, responseTime, cacheUsed: false }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      console.error('❌ API Exception:', errorMessage)
      return { 
        success: false, 
        error: errorMessage, 
        responseTime: Date.now() - startTime,
        cacheUsed: false 
      }
    }
  }
  
  // ModelService를 통한 테스트
  async testModelService(): Promise<{
    success: boolean
    data?: ModelMBTI[]
    error?: string
    responseTime: number
    cacheUsed: boolean
  }> {
    console.log('🔍 ModelService MBTI Test Starting...')
    const startTime = Date.now()
    
    try {
      const data = await ModelService.getMBTIList()
      const responseTime = Date.now() - startTime
      
      console.log('✅ ModelService Success:', {
        dataCount: data.length,
        responseTime: `${responseTime}ms`,
        firstItem: data[0] || null
      })
      
      return { success: true, data, responseTime, cacheUsed: false }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      console.error('❌ ModelService Error:', errorMessage)
      return { 
        success: false, 
        error: errorMessage, 
        responseTime: Date.now() - startTime,
        cacheUsed: false 
      }
    }
  }
  
  // 캐시된 데이터 반환
  getCachedData(): ModelMBTI[] {
    return this.cache
  }
  
  // 캐시 상태 확인
  getCacheInfo(): {
    hasData: boolean
    dataCount: number
    lastFetchTime: string
    cacheAge: number
  } {
    return {
      hasData: this.cache.length > 0,
      dataCount: this.cache.length,
      lastFetchTime: this.lastFetchTime ? new Date(this.lastFetchTime).toLocaleString() : 'Never',
      cacheAge: this.lastFetchTime ? Date.now() - this.lastFetchTime : 0
    }
  }
  
  // 데이터 유효성 검증
  validateData(data?: ModelMBTI[]): {
    isValid: boolean
    issues: string[]
    recommendations: string[]
  } {
    const testData = data || this.cache
    const issues: string[] = []
    const recommendations: string[] = []
    
    if (!Array.isArray(testData)) {
      issues.push('데이터가 배열이 아님')
      recommendations.push('백엔드에서 배열 형태로 응답하는지 확인')
    }
    
    if (testData.length === 0) {
      issues.push('데이터가 비어있음')
      recommendations.push('데이터베이스에 MBTI 데이터가 올바르게 삽입되었는지 확인')
    }
    
    // 필수 필드 검증
    testData.forEach((item, index) => {
      if (!item.mbti_id) {
        issues.push(`항목 ${index + 1}: mbti_id 누락`)
      }
      if (!item.mbti_name) {
        issues.push(`항목 ${index + 1}: mbti_name 누락`)
      }
      if (!item.mbti_traits && !item.mbti_traits) {
        issues.push(`항목 ${index + 1}: mbti_traits 또는 mbti_traits 누락`)
      }
    })
    
    // 중복 검사
    const names = testData.map(item => item.mbti_name)
    const duplicates = names.filter((name, index) => names.indexOf(name) !== index)
    if (duplicates.length > 0) {
      issues.push(`중복된 MBTI 이름: ${duplicates.join(', ')}`)
    }
    
    if (issues.length === 0) {
      recommendations.push('데이터가 유효합니다! 🎉')
    }
    
    return {
      isValid: issues.length === 0,
      issues,
      recommendations
    }
  }
  
  // 전체 시스템 상태 체크
  async performFullDiagnostic(): Promise<void> {
    console.group('🔍 MBTI 시스템 전체 진단 시작')
    
    try {
      // 1. API 연결 테스트
      console.log('1️⃣ Direct API 테스트...')
      const directResult = await this.testDirectAPI()
      
      // 2. 서비스 레이어 테스트
      console.log('2️⃣ ModelService 테스트...')
      const serviceResult = await this.testModelService()
      
      // 3. 데이터 유효성 검증
      console.log('3️⃣ 데이터 유효성 검증...')
      const validation = this.validateData(directResult.data)
      
      // 4. 캐시 상태 확인
      console.log('4️⃣ 캐시 상태 확인...')
      const cacheInfo = this.getCacheInfo()
      
      // 종합 리포트 생성
      console.group('📊 진단 결과 종합')
      console.table({
        'Direct API': directResult.success ? '✅ 성공' : '❌ 실패',
        'ModelService': serviceResult.success ? '✅ 성공' : '❌ 실패',
        'Data Validation': validation.isValid ? '✅ 유효' : '❌ 문제있음',
        'Cache Status': cacheInfo.hasData ? '✅ 있음' : '❌ 없음'
      })
      
      if (validation.issues.length > 0) {
        console.warn('⚠️ 발견된 문제들:', validation.issues)
        console.info('💡 권장사항:', validation.recommendations)
      }
      
      console.groupEnd()
      
    } catch (error) {
      console.error('❌ 진단 중 오류 발생:', error)
    } finally {
      console.groupEnd()
    }
  }
  
  // 개발자 도움말 출력
  printHelp(): void {
    console.group('🛠️ MBTI 디버거 사용법')
    console.log('사용 가능한 함수들:')
    console.log('• window.mbtiDebugger.testDirectAPI() - API 직접 호출 테스트')
    console.log('• window.mbtiDebugger.testModelService() - ModelService를 통한 테스트')
    console.log('• window.mbtiDebugger.getCachedData() - 캐시된 데이터 조회')
    console.log('• window.mbtiDebugger.getCacheInfo() - 캐시 상태 정보')
    console.log('• window.mbtiDebugger.validateData() - 데이터 유효성 검증')
    console.log('• window.mbtiDebugger.performFullDiagnostic() - 전체 시스템 진단')
    console.log('• window.mbtiDebugger.printHelp() - 이 도움말 출력')
    console.log('')
    console.log('💡 빠른 시작: window.mbtiDebugger.performFullDiagnostic()')
    console.groupEnd()
  }
}

// 전역 함수들을 window 객체에 등록하는 함수
export function registerGlobalMBTIDebugger(): void {
  const mbtiDebugger = MBTIDebugger.getInstance()  // 'debugger' 예약어 사용 금지
  
  // @ts-ignore
  window.mbtiDebugger = mbtiDebugger
  
  // 편의 함수들도 전역으로 등록
  // @ts-ignore
  window.testMBTI = () => mbtiDebugger.performFullDiagnostic()
  // @ts-ignore
  window.mbtiHelp = () => mbtiDebugger.printHelp()
  
  console.log('🔧 MBTI 디버거가 전역으로 등록되었습니다!')
  console.log('💡 사용법: window.mbtiHelp() 또는 window.testMBTI()')
}

// 백엔드 연결 상태 체커
export class BackendConnectionChecker {
  private static baseURL = 'http://localhost:8000'
  
  // AbortController를 사용한 타임아웃 구현
  private static createTimeoutController(timeoutMs: number): AbortController {
    const controller = new AbortController()
    setTimeout(() => controller.abort(), timeoutMs)
    return controller
  }
  
  static async checkConnection(): Promise<{
    isConnected: boolean
    responseTime: number
    error?: string
  }> {
    const startTime = Date.now()
    
    try {
      const controller = this.createTimeoutController(5000)
      const response = await fetch(`${this.baseURL}/health`, {
        method: 'GET',
        signal: controller.signal
      })
      
      const responseTime = Date.now() - startTime
      
      return {
        isConnected: response.ok,
        responseTime,
        error: response.ok ? undefined : `HTTP ${response.status}`
      }
    } catch (error) {
      return {
        isConnected: false,
        responseTime: Date.now() - startTime,
        error: error instanceof Error ? error.message : 'Connection failed'
      }
    }
  }
  
  static async checkMBTIEndpoint(): Promise<{
    isAvailable: boolean
    responseTime: number
    dataCount?: number
    error?: string
  }> {
    const startTime = Date.now()
    
    try {
      const controller = this.createTimeoutController(5000)
      const response = await fetch(`${this.baseURL}/api/v1/influencers/mbti`, {
        method: 'GET',
        signal: controller.signal
      })
      
      const responseTime = Date.now() - startTime
      
      if (!response.ok) {
        return {
          isAvailable: false,
          responseTime,
          error: `HTTP ${response.status}: ${response.statusText}`
        }
      }
      
      const data = await response.json()
      
      return {
        isAvailable: true,
        responseTime,
        dataCount: Array.isArray(data) ? data.length : 0
      }
    } catch (error) {
      return {
        isAvailable: false,
        responseTime: Date.now() - startTime,
        error: error instanceof Error ? error.message : 'Endpoint check failed'
      }
    }
  }
}