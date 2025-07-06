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
      
      // 현재 페이지 URL을 localStorage에 저장 (리다이렉트 후 돌아올 페이지)
      localStorage.setItem('social_auth_return_url', window.location.href);
      localStorage.setItem('social_auth_provider', 'instagram');
      
      // Instagram Login 스코프 (새로운 권한)
      const scopes = [
        'instagram_business_basic',
        'instagram_business_content_publish', 
        'instagram_business_manage_messages',
        'instagram_business_manage_comments'
      ].join(',');
      
      const authUrl = `https://api.instagram.com/oauth/authorize?client_id=${instagramAuth.clientId}&redirect_uri=${encodeURIComponent(instagramAuth.redirectUri)}&scope=${scopes}&response_type=code`;
      
      // 팝업 대신 현재 페이지에서 리다이렉트
      window.location.href = authUrl;
      
      // 리다이렉트 방식에서는 Promise가 의미가 없으므로 빈 Promise 반환
      // 실제 처리는 콜백 페이지에서 수행됨
      resolve({ success: true, data: { provider: 'instagram' } });
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
      
      // 현재 페이지 URL을 localStorage에 저장 (리다이렉트 후 돌아올 페이지)
      localStorage.setItem('social_auth_return_url', window.location.href);
      localStorage.setItem('social_auth_provider', 'google');
      
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
      
      // 팝업 대신 현재 페이지에서 리다이렉트
      window.location.href = authUrl;
      
      // 리다이렉트 방식에서는 Promise가 의미가 없으므로 빈 Promise 반환
      // 실제 처리는 콜백 페이지에서 수행됨
      resolve({ success: true, data: { provider: 'google' } });
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
  
  login: (): Promise<SocialAuthResult> => {
    return new Promise((resolve) => {
      if (typeof window === 'undefined') {
        resolve({ success: false, error: 'Not available in server environment' });
        return;
      }
      
      // 현재 페이지 URL을 localStorage에 저장 (리다이렉트 후 돌아올 페이지)
      localStorage.setItem('social_auth_return_url', window.location.href);
      localStorage.setItem('social_auth_provider', 'naver');
      
      // Naver OAuth2 authorization URL 생성
      const params = new URLSearchParams({
        response_type: 'code',
        client_id: naverAuth.clientId,
        redirect_uri: naverAuth.redirectUri,
        state: Math.random().toString(36).substring(2, 15)
      });
      
      const authUrl = `https://nid.naver.com/oauth2.0/authorize?${params.toString()}`;
      
      // 팝업 대신 현재 페이지에서 리다이렉트
      window.location.href = authUrl;
      
      // 리다이렉트 방식에서는 Promise가 의미가 없으므로 빈 Promise 반환
      // 실제 처리는 콜백 페이지에서 수행됨
      resolve({ success: true, data: { provider: 'naver' } });
    });
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