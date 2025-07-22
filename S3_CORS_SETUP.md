# S3 CORS 설정 가이드

## 문제 상황
음성 파일이 S3에 저장되어 있지만, 브라우저에서 재생/다운로드 시 CORS 오류가 발생할 수 있습니다.

## 해결 방법

### 1. AWS S3 콘솔 접속
1. AWS 콘솔에 로그인
2. S3 서비스로 이동
3. `aimex-influencers` 버킷 선택

### 2. CORS 설정 추가
1. 버킷 선택 후 "권한(Permissions)" 탭 클릭
2. "CORS(Cross-origin resource sharing)" 섹션까지 스크롤
3. "편집" 버튼 클릭
4. 다음 CORS 구성 추가:

```json
[
    {
        "AllowedHeaders": [
            "*"
        ],
        "AllowedMethods": [
            "GET",
            "HEAD",
            "PUT",
            "POST",
            "DELETE"
        ],
        "AllowedOrigins": [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://localhost:3000",
            "https://127.0.0.1:3000"
        ],
        "ExposeHeaders": [
            "Content-Type",
            "Content-Length",
            "Content-Range",
            "Accept-Ranges",
            "ETag",
            "x-amz-request-id",
            "x-amz-id-2"
        ],
        "MaxAgeSeconds": 3600
    }
]
```

### 3. 버킷 정책 확인 (선택사항)
presigned URL을 사용하므로 일반적으로 버킷 정책 수정은 필요하지 않습니다.
하지만 문제가 지속되면 다음 정책을 추가할 수 있습니다:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::aimex-influencers/tts/*",
            "Condition": {
                "StringLike": {
                    "aws:Referer": [
                        "http://localhost:3000/*",
                        "https://localhost:3000/*",
                        "http://127.0.0.1:3000/*",
                        "https://127.0.0.1:3000/*"
                    ]
                }
            }
        }
    ]
}
```

## 프로덕션 배포 시
프로덕션 환경에서는 `AllowedOrigins`를 실제 도메인으로 변경해야 합니다:
- 예: `https://yourdomain.com`

## 테스트 방법
1. 브라우저 개발자 도구 열기 (F12)
2. Network 탭 선택
3. 음성 재생 버튼 클릭
4. 음성 파일 요청 확인
5. Response Headers에서 CORS 헤더 확인

## 문제 해결
- 캐시 문제: 브라우저 캐시 삭제 또는 시크릿 모드로 테스트
- presigned URL 만료: 백엔드에서 새로운 URL 생성
- 네트워크 문제: VPN 또는 프록시 비활성화