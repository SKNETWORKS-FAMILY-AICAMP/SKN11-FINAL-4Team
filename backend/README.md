# AIMEX Backend API

AI 인플루언서 모델 관리 시스템의 FastAPI 백엔드

## 설치 및 실행

### 1. 가상환경 활성화
```bash
conda activate AIMEX_backend
```

### 2. 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정
`.env` 파일을 생성하고 다음 내용을 추가:
```
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/AIMEX_MAIN
SECRET_KEY=your-secret-key-here
```

### 4. 서버 실행
```bash
python run.py
```

또는
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API 문서

서버 실행 후 다음 URL에서 API 문서를 확인할 수 있습니다:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 주요 기능

### 인증 (Authentication)
- `/api/v1/auth/login` - 사용자 로그인
- `/api/v1/auth/register` - 사용자 등록

### 사용자 관리 (Users)
- `/api/v1/users/` - 사용자 목록 조회
- `/api/v1/users/{user_uuid}` - 특정 사용자 조회

### AI 모델 관리 (Models)
- `/api/v1/models/` - AI 모델 목록 조회
- `/api/v1/models/{model_uuid}` - 특정 모델 조회
- `/api/v1/models/` (POST) - 새 모델 생성
- `/api/v1/models/{model_uuid}` (PUT) - 모델 수정
- `/api/v1/models/{model_uuid}` (DELETE) - 모델 삭제

### 게시글 관리 (Posts)
- `/api/v1/posts/` - 게시글 목록 조회
- `/api/v1/posts/{post_uuid}` - 특정 게시글 조회
- `/api/v1/posts/` (POST) - 새 게시글 생성

### 그룹 관리 (Groups)
- `/api/v1/groups/` - 그룹 목록 조회
- `/api/v1/groups/{group_uuid}` - 특정 그룹 조회
- `/api/v1/groups/` (POST) - 새 그룹 생성

### 관리자 기능 (Admin)
- `/api/v1/admin/dashboard` - 대시보드 통계
- `/api/v1/admin/system-logs` - 시스템 로그 조회

## 데이터베이스 스키마

MySQL 데이터베이스를 사용하며, 다음 테이블들이 포함됩니다:
- USER - 사용자 정보
- GROUP - 그룹 정보
- USER_GROUP - 사용자-그룹 관계
- MODEL_MBTI - MBTI 성격 정보
- ML - AI 모델 정보
- BOARD - 게시글 정보
- ML_API - API 관리
- API_CALL_AGGREGATION - API 호출 집계
- HF_TOKEN_MANAGE - 허깅페이스 토큰 관리
- SYSTEM_LOG - 시스템 로그 