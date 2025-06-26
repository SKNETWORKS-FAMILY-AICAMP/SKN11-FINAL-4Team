# AIMEX API - AI Influencer Model Management System

AIMEX는 AI 인플루언서 모델을 관리하는 FastAPI 기반 백엔드 시스템입니다.

## 🚀 주요 기능

- **AI 모델 관리**: MBTI 기반 AI 모델 생성, 수정, 삭제
- **그룹 관리**: 사용자 그룹 및 권한 관리
- **게시글 관리**: AI 모델별 게시글 생성 및 관리
- **허깅페이스 토큰 관리**: API 토큰 할당 및 관리
- **관리자 대시보드**: 시스템 통계 및 모니터링
- **사용자 인증**: JWT 기반 인증 시스템

## 🛠 기술 스택

- **Framework**: FastAPI
- **Database**: MySQL 8.0+
- **ORM**: SQLAlchemy
- **Authentication**: JWT
- **Migration**: Alembic
- **Documentation**: Swagger UI / ReDoc

## 📋 요구사항

- Python 3.8+
- MySQL 8.0+
- pip

## 🔧 설치 및 설정

### 1. 저장소 클론
```bash
git clone <repository-url>
cd SKN11-FINAL-4Team/backend
```

### 2. 가상환경 생성 및 활성화
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정
```bash
# env.example을 .env로 복사
cp env.example .env

# .env 파일을 편집하여 실제 값으로 수정
# 특히 DATABASE_URL과 SECRET_KEY를 설정하세요
```

### 5. 데이터베이스 설정
```bash
# MySQL에서 데이터베이스 생성
mysql -u root -p
CREATE DATABASE AIMEX_MAIN CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 6. 마이그레이션 실행
```bash
# 마이그레이션 스크립트 실행
python migrate.py
```

### 7. 초기 데이터 삽입 (선택사항)
```bash
# 테스트 데이터 삽입
python init_full_data.py
```

## 🚀 서버 실행

### 개발 모드
```bash
python run.py
```

### 프로덕션 모드
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 📚 API 문서

서버 실행 후 다음 URL에서 API 문서를 확인할 수 있습니다:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 🧪 테스트

### API 테스트 실행
```bash
python test_improved_api.py
```

### 개별 엔드포인트 테스트
```bash
# 그룹 목록 조회
curl http://localhost:8000/api/v1/groups/

# AI 모델 목록 조회
curl http://localhost:8000/api/v1/models/

# MBTI 목록 조회
curl http://localhost:8000/api/v1/models/mbti/
```

## 📊 데이터베이스 스키마

### 주요 테이블

1. **USER**: 사용자 정보
2. **GROUP**: 그룹 정보
3. **USER_GROUP**: 사용자-그룹 관계
4. **MODEL_MBTI**: MBTI 유형 정보
5. **ML**: AI 모델 정보
6. **BOARD**: 게시글 정보
7. **ML_API**: API 호출 정보
8. **HF_TOKEN_MANAGE**: 허깅페이스 토큰 관리
9. **SYSTEM_LOG**: 시스템 로그

## 🔐 보안

### 환경 변수 보안
- `.env` 파일은 절대 Git에 커밋하지 마세요
- 프로덕션에서는 강력한 `SECRET_KEY`를 사용하세요
- 데이터베이스 비밀번호는 안전하게 관리하세요

### 시크릿 키 생성
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 🐛 문제 해결

### 일반적인 문제

1. **데이터베이스 연결 실패**
   - MySQL 서비스가 실행 중인지 확인
   - DATABASE_URL 설정 확인
   - 데이터베이스 사용자 권한 확인

2. **마이그레이션 오류**
   - 기존 테이블과 충돌하는 경우 직접 SQL로 수정
   - `fix_database.py` 스크립트 실행

3. **포트 충돌**
   - 다른 프로세스가 8000번 포트를 사용 중인지 확인
   - `netstat -ano | findstr :8000` (Windows)
   - `lsof -i :8000` (macOS/Linux)

### 로그 확인
```bash
# 애플리케이션 로그 확인
tail -f logs/app.log

# 데이터베이스 로그 확인
tail -f /var/log/mysql/error.log
```

## 📈 성능 최적화

### 데이터베이스 최적화
- 인덱스 추가
- 쿼리 최적화
- 연결 풀 설정 조정

### API 최적화
- 캐싱 구현
- 페이지네이션 적용
- 배치 처리 구현

## 🔄 배포

### Docker 배포 (권장)
```bash
# Docker 이미지 빌드
docker build -t aimex-api .

# 컨테이너 실행
docker run -p 8000:8000 --env-file .env aimex-api
```

### 수동 배포
1. 프로덕션 서버에 코드 배포
2. 환경 변수 설정
3. 데이터베이스 마이그레이션
4. 서비스 등록 및 시작

## 🤝 기여하기

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 📞 지원

문제가 발생하거나 질문이 있으시면 이슈를 생성해 주세요.

---

**AIMEX API** - AI Influencer Model Management System 