/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true,
  },
  experimental: {
    serverActions: {
      bodySizeLimit: '10mb', // 10MB로 증가
    },
  },
  // HTTPS 리다이렉트 비활성화
  async redirects() {
    return []
  },
  // HTTP 사용 강제
  assetPrefix: process.env.NODE_ENV === 'development' ? '' : undefined,
  // HTTPS 관련 설정 비활성화
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=0'
          }
        ]
      }
    ]
  }
}

export default nextConfig
