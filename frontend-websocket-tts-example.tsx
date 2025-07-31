import React, { useState, useRef, useEffect } from 'react';

interface ChatMessage {
  id: string;
  content: string;
  sender: 'user' | 'ai';
  timestamp: Date;
  audioUrl?: string;
  audioBase64?: string;
}

// base64를 Blob으로 변환하는 헬퍼 함수
const base64ToBlob = (base64: string, contentType: string): Blob => {
  const byteCharacters = atob(base64);
  const byteNumbers = new Array(byteCharacters.length);
  
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  
  const byteArray = new Uint8Array(byteNumbers);
  return new Blob([byteArray], { type: contentType });
};

const ChatWithTTS: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [currentAudioUrl, setCurrentAudioUrl] = useState<string | null>(null);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const currentMessageRef = useRef<string>('');
  
  // WebSocket 연결
  const connectWebSocket = () => {
    const token = localStorage.getItem('authToken'); // 실제 토큰 가져오기
    const wsUrl = `ws://localhost:8000/api/v1/chatbot/chatbot/${token}`;
    
    wsRef.current = new WebSocket(wsUrl);
    
    wsRef.current.onopen = () => {
      console.log('WebSocket 연결됨');
      setIsConnected(true);
    };
    
    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'token':
          // 스트리밍 토큰 처리
          currentMessageRef.current += data.content;
          updateCurrentMessage();
          break;
          
        case 'complete':
          // 메시지 완료
          if (currentMessageRef.current) {
            const newMessage: ChatMessage = {
              id: Date.now().toString(),
              content: currentMessageRef.current,
              sender: 'ai',
              timestamp: new Date()
            };
            setMessages(prev => [...prev, newMessage]);
            currentMessageRef.current = '';
            setIsTyping(false);
          }
          break;
          
        case 'audio':
          // TTS 음성 데이터 수신
          if (messages.length > 0) {
            if (data.audio_base64) {
              // base64 오디오 데이터 처리
              const audioBlob = base64ToBlob(data.audio_base64, `audio/${data.format || 'mp3'}`);
              const audioUrl = URL.createObjectURL(audioBlob);
              
              setMessages(prev => {
                const updated = [...prev];
                updated[updated.length - 1].audioUrl = audioUrl;
                updated[updated.length - 1].audioBase64 = data.audio_base64;
                return updated;
              });
              setCurrentAudioUrl(audioUrl);
              console.log('음성 base64 수신 (크기):', data.audio_base64.length);
            } else if (data.audio_url) {
              // URL 방식 (폴백)
              setMessages(prev => {
                const updated = [...prev];
                updated[updated.length - 1].audioUrl = data.audio_url;
                return updated;
              });
              setCurrentAudioUrl(data.audio_url);
              console.log('음성 URL 수신:', data.audio_url);
            }
          }
          break;
          
        case 'error':
          console.error('WebSocket 오류:', data.message);
          break;
      }
    };
    
    wsRef.current.onerror = (error) => {
      console.error('WebSocket 에러:', error);
    };
    
    wsRef.current.onclose = () => {
      console.log('WebSocket 연결 종료');
      setIsConnected(false);
    };
  };
  
  // 현재 입력 중인 메시지 업데이트
  const updateCurrentMessage = () => {
    if (currentMessageRef.current) {
      setMessages(prev => {
        const updated = [...prev];
        if (updated.length > 0 && updated[updated.length - 1].sender === 'ai' && !updated[updated.length - 1].audioUrl) {
          updated[updated.length - 1].content = currentMessageRef.current;
        } else {
          updated.push({
            id: 'typing',
            content: currentMessageRef.current,
            sender: 'ai',
            timestamp: new Date()
          });
        }
        return updated;
      });
    }
  };
  
  // 메시지 전송
  const sendMessage = () => {
    if (!inputMessage.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }
    
    // 사용자 메시지 추가
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      content: inputMessage,
      sender: 'user',
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);
    
    // WebSocket으로 메시지 전송
    wsRef.current.send(JSON.stringify({
      message: inputMessage,
      influencer_id: 'your_influencer_id' // 실제 인플루언서 ID
    }));
    
    setInputMessage('');
    setIsTyping(true);
    currentMessageRef.current = '';
  };
  
  // 음성 재생
  const playAudio = (audioUrl: string) => {
    if (!audioUrl) return;
    
    setIsPlayingAudio(true);
    
    if (audioRef.current) {
      audioRef.current.pause();
    }
    
    audioRef.current = new Audio(audioUrl);
    
    audioRef.current.onended = () => {
      setIsPlayingAudio(false);
    };
    
    audioRef.current.onerror = (error) => {
      console.error('오디오 재생 오류:', error);
      setIsPlayingAudio(false);
    };
    
    audioRef.current.play().catch(error => {
      console.error('오디오 재생 실패:', error);
      setIsPlayingAudio(false);
    });
  };
  
  // 음성 정지
  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setIsPlayingAudio(false);
    }
  };
  
  // 컴포넌트 마운트 시 WebSocket 연결
  useEffect(() => {
    connectWebSocket();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (audioRef.current) {
        audioRef.current.pause();
      }
      // Blob URL 정리
      messages.forEach(msg => {
        if (msg.audioUrl && msg.audioBase64) {
          URL.revokeObjectURL(msg.audioUrl);
        }
      });
    };
  }, []);
  
  return (
    <div className="chat-container">
      <div className="chat-header">
        <h2>AI 챗봇 (음성 지원)</h2>
        <span className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
          {isConnected ? '연결됨' : '연결 끊김'}
        </span>
      </div>
      
      <div className="chat-messages">
        {messages.map((message) => (
          <div key={message.id} className={`message ${message.sender}`}>
            <div className="message-content">{message.content}</div>
            {message.audioUrl && (
              <button
                className="audio-button"
                onClick={() => isPlayingAudio ? stopAudio() : playAudio(message.audioUrl!)}
              >
                {isPlayingAudio ? '⏸️ 정지' : '🔊 재생'}
              </button>
            )}
            <div className="message-time">
              {message.timestamp.toLocaleTimeString()}
            </div>
          </div>
        ))}
        {isTyping && !currentMessageRef.current && (
          <div className="typing-indicator">AI가 입력 중...</div>
        )}
      </div>
      
      <div className="chat-input">
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="메시지를 입력하세요..."
          disabled={!isConnected}
        />
        <button onClick={sendMessage} disabled={!isConnected || !inputMessage.trim()}>
          전송
        </button>
      </div>
      
      {/* 현재 재생 중인 오디오 정보 */}
      {isPlayingAudio && (
        <div className="audio-playing-indicator">
          🎵 음성 재생 중...
        </div>
      )}
    </div>
  );
};

// CSS 스타일 예제
const styles = `
.chat-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  font-family: Arial, sans-serif;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  border-bottom: 2px solid #e0e0e0;
  margin-bottom: 20px;
}

.connection-status {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
}

.connection-status.connected {
  background-color: #4caf50;
  color: white;
}

.connection-status.disconnected {
  background-color: #f44336;
  color: white;
}

.chat-messages {
  height: 400px;
  overflow-y: auto;
  border: 1px solid #e0e0e0;
  padding: 20px;
  margin-bottom: 20px;
  background-color: #f9f9f9;
}

.message {
  margin-bottom: 15px;
  padding: 10px;
  border-radius: 8px;
  max-width: 70%;
}

.message.user {
  background-color: #2196f3;
  color: white;
  margin-left: auto;
  text-align: right;
}

.message.ai {
  background-color: #e3f2fd;
  color: #333;
  margin-right: auto;
}

.message-content {
  margin-bottom: 5px;
}

.message-time {
  font-size: 11px;
  opacity: 0.7;
}

.audio-button {
  margin-top: 8px;
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  background-color: #4caf50;
  color: white;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.3s;
}

.audio-button:hover {
  background-color: #45a049;
}

.typing-indicator {
  color: #666;
  font-style: italic;
  margin-bottom: 10px;
}

.chat-input {
  display: flex;
  gap: 10px;
}

.chat-input input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 16px;
}

.chat-input button {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  background-color: #2196f3;
  color: white;
  cursor: pointer;
  font-size: 16px;
  transition: background-color 0.3s;
}

.chat-input button:hover:not(:disabled) {
  background-color: #1976d2;
}

.chat-input button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.audio-playing-indicator {
  position: fixed;
  bottom: 20px;
  right: 20px;
  background-color: #4caf50;
  color: white;
  padding: 10px 20px;
  border-radius: 20px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.2);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
  100% {
    transform: scale(1);
  }
}
`;

export default ChatWithTTS;