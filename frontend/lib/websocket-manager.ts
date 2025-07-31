/**
 * WebSocket 연결을 관리하는 싱글톤 클래스
 * 중복 연결을 방지하고 연결 상태를 중앙에서 관리
 */
class WebSocketManager {
  private static instance: WebSocketManager;
  private connections: Map<string, WebSocket> = new Map();
  private connecting: Set<string> = new Set();

  private constructor() {}

  static getInstance(): WebSocketManager {
    if (!WebSocketManager.instance) {
      WebSocketManager.instance = new WebSocketManager();
    }
    return WebSocketManager.instance;
  }

  getConnection(key: string): WebSocket | null {
    const ws = this.connections.get(key);
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return ws;
    }
    return null;
  }

  isConnecting(key: string): boolean {
    return this.connecting.has(key);
  }

  setConnecting(key: string, value: boolean): void {
    if (value) {
      this.connecting.add(key);
    } else {
      this.connecting.delete(key);
    }
  }

  setConnection(key: string, ws: WebSocket): void {
    // 기존 연결이 있으면 먼저 닫기
    const existing = this.connections.get(key);
    if (existing && (existing.readyState === WebSocket.OPEN || existing.readyState === WebSocket.CONNECTING)) {
      console.log(`🔌 기존 WebSocket 연결 종료: ${key}`);
      existing.close();
    }
    
    this.connections.set(key, ws);
    
    // 연결이 닫히면 자동으로 제거
    ws.addEventListener('close', () => {
      this.connections.delete(key);
      this.connecting.delete(key);
    });
  }

  closeConnection(key: string): void {
    const ws = this.connections.get(key);
    if (ws) {
      console.log(`🔌 WebSocket 연결 종료: ${key}`);
      ws.close();
      this.connections.delete(key);
    }
    this.connecting.delete(key);
  }

  closeAllConnections(): void {
    console.log('🔌 모든 WebSocket 연결 종료');
    this.connections.forEach((ws, key) => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    });
    this.connections.clear();
    this.connecting.clear();
  }
}

export default WebSocketManager.getInstance();