declare global {
  interface Window {
    FB: any;
    gapi: any;
    naver: any;
  }
}

export interface SocialAuthResult {
  success: boolean;
  data?: {
    id: string;
    email: string;
    name: string;
    picture?: string;
    provider: string;
  };
  error?: string;
}

// Instagram Login API (Direct Instagram Authentication)
export const instagramAuth = {
  clientId: process.env.NEXT_PUBLIC_INSTAGRAM_APP_ID || '',
  redirectUri: process.env.NEXT_PUBLIC_INSTAGRAM_REDIRECT_URI || (typeof window !== 'undefined' ? `${window.location.origin}/api/auth/callback/instagram` : ''),
  
  login: (): Promise<SocialAuthResult> => {
    return new Promise((resolve) => {
      if (typeof window === 'undefined') {
        resolve({ success: false, error: 'Not available in server environment' });
        return;
      }
      
      // Instagram Login 스코프 (새로운 권한)
      const scopes = [
        'instagram_business_basic',
        'instagram_business_content_publish', 
        'instagram_business_manage_messages',
        'instagram_business_manage_comments'
      ].join(',');
      
      const authUrl = `https://api.instagram.com/oauth/authorize?client_id=${instagramAuth.clientId}&redirect_uri=${encodeURIComponent(instagramAuth.redirectUri)}&scope=${scopes}&response_type=code`;
      
      const popup = window.open(authUrl, 'instagram-auth', 'width=500,height=600,scrollbars=yes,resizable=yes');
      
      const checkClosed = setInterval(() => {
        if (popup?.closed) {
          clearInterval(checkClosed);
          resolve({
            success: false,
            error: 'Authentication cancelled'
          });
        }
      }, 1000);

      // 메시지 리스너로 콜백 결과 수신
      const messageHandler = async (event: MessageEvent) => {
        if (event.origin !== window.location.origin) return;
        
        if (event.data.type === 'INSTAGRAM_AUTH_SUCCESS') {
          clearInterval(checkClosed);
          popup?.close();
          window.removeEventListener('message', messageHandler);
          
          try {
            // 백엔드에 authorization code 전달
            const { BackendAuthService } = await import('./backend-auth');
            const backendResponse = await BackendAuthService.exchangeCodeForToken(
              'instagram',
              event.data.code,
              instagramAuth.redirectUri
            );
            
            resolve({
              success: true,
              data: {
                ...backendResponse.user,
                backendToken: backendResponse.access_token,
                provider: 'instagram'
              }
            });
          } catch (error) {
            resolve({
              success: false,
              error: error instanceof Error ? error.message : 'Backend authentication failed'
            });
          }
        } else if (event.data.type === 'INSTAGRAM_AUTH_ERROR') {
          clearInterval(checkClosed);
          popup?.close();
          window.removeEventListener('message', messageHandler);
          
          resolve({
            success: false,
            error: event.data.error
          });
        }
      };

      window.addEventListener('message', messageHandler);
      
      // 타임아웃 설정 (30초)
      setTimeout(() => {
        clearInterval(checkClosed);
        window.removeEventListener('message', messageHandler);
        if (popup && !popup.closed) {
          popup.close();
        }
        resolve({
          success: false,
          error: 'Authentication timeout'
        });
      }, 30000);
    });
  }
};

// Google OAuth
export const googleAuth = {
  clientId: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '',
  redirectUri: process.env.NEXT_PUBLIC_GOOGLE_REDIRECT_URI || (typeof window !== 'undefined' ? `${window.location.origin}/api/auth/callback/google` : ''),
  
  login: (): Promise<SocialAuthResult> => {
    return new Promise((resolve) => {
      if (typeof window === 'undefined') {
        resolve({ success: false, error: 'Not available in server environment' });
        return;
      }
      
      // Google OAuth2 authorization URL 생성
      const params = new URLSearchParams({
        client_id: googleAuth.clientId,
        redirect_uri: googleAuth.redirectUri,
        response_type: 'code',
        scope: 'openid email profile',
        access_type: 'offline',
        prompt: 'consent',
        state: Math.random().toString(36).substring(2, 15)
      });
      
      const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
      
      const popup = window.open(authUrl, 'google-auth', 'width=500,height=600,scrollbars=yes,resizable=yes');
      
      const checkClosed = setInterval(() => {
        if (popup?.closed) {
          clearInterval(checkClosed);
          resolve({
            success: false,
            error: 'Authentication cancelled'
          });
        }
      }, 1000);

      // 메시지 리스너로 콜백 결과 수신
      const messageHandler = async (event: MessageEvent) => {
        if (event.origin !== window.location.origin) return;
        
        if (event.data.type === 'GOOGLE_AUTH_SUCCESS') {
          clearInterval(checkClosed);
          popup?.close();
          window.removeEventListener('message', messageHandler);
          
          resolve({
            success: true,
            data: {
              code: event.data.code,
              redirect_uri: googleAuth.redirectUri,
              provider: 'google'
            }
          });
        } else if (event.data.type === 'GOOGLE_AUTH_ERROR') {
          clearInterval(checkClosed);
          popup?.close();
          window.removeEventListener('message', messageHandler);
          
          resolve({
            success: false,
            error: event.data.error
          });
        }
      };

      window.addEventListener('message', messageHandler);
      
      // 타임아웃 설정 (30초)
      setTimeout(() => {
        clearInterval(checkClosed);
        window.removeEventListener('message', messageHandler);
        if (popup && !popup.closed) {
          popup.close();
        }
        resolve({
          success: false,
          error: 'Authentication timeout'
        });
      }, 30000);
    });
  }
};

// Naver OAuth
export const naverAuth = {
  clientId: process.env.NEXT_PUBLIC_NAVER_CLIENT_ID || '',
  redirectUri: process.env.NEXT_PUBLIC_NAVER_REDIRECT_URI || (typeof window !== 'undefined' ? `${window.location.origin}/api/auth/callback/naver` : ''),
  
  loadScript: (): Promise<void> => {
    return new Promise((resolve, reject) => {
      if (typeof window === 'undefined') {
        reject(new Error('Not available in server environment'));
        return;
      }
      
      if (window.naver) {
        resolve();
        return;
      }
      
      const script = document.createElement('script');
      script.src = 'https://static.nid.naver.com/js/naveridlogin_js_sdk_2.0.2.js';
      script.onload = () => {
        const naverLogin = new window.naver.LoginWithNaverId({
          clientId: naverAuth.clientId,
          callbackUrl: naverAuth.redirectUri,
          isPopup: true,
          loginButton: {color: "green", type: 3, height: 58}
        });
        naverLogin.init();
        window.naver.loginInstance = naverLogin;
        resolve();
      };
      script.onerror = reject;
      document.head.appendChild(script);
    });
  },
  
  login: async (): Promise<SocialAuthResult> => {
    try {
      await naverAuth.loadScript();
      
      return new Promise((resolve) => {
        const naverLogin = window.naver.loginInstance;
        
        naverLogin.getLoginStatus((status: boolean) => {
          if (status) {
            const user = naverLogin.user;
            resolve({
              success: true,
              data: {
                id: user.getId(),
                email: user.getEmail(),
                name: user.getName(),
                picture: user.getProfileImage(),
                provider: 'naver'
              }
            });
          } else {
            naverLogin.authorize();
            
            const checkAuth = setInterval(() => {
              naverLogin.getLoginStatus((newStatus: boolean) => {
                if (newStatus) {
                  clearInterval(checkAuth);
                  const user = naverLogin.user;
                  resolve({
                    success: true,
                    data: {
                      id: user.getId(),
                      email: user.getEmail(),
                      name: user.getName(),
                      picture: user.getProfileImage(),
                      provider: 'naver'
                    }
                  });
                }
              });
            }, 1000);
            
            setTimeout(() => {
              clearInterval(checkAuth);
              resolve({
                success: false,
                error: 'Authentication timeout'
              });
            }, 30000);
          }
        });
      });
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Naver authentication failed'
      };
    }
  }
};

export const socialLogin = async (provider: 'instagram' | 'google' | 'naver'): Promise<SocialAuthResult> => {
  switch (provider) {
    case 'instagram':
      return instagramAuth.login();
    case 'google':
      return googleAuth.login();
    case 'naver':
      return naverAuth.login();
    default:
      return {
        success: false,
        error: 'Unsupported provider'
      };
  }
};