-- ===================================================
-- AIMEX 데이터베이스 DDL
-- 작성자: 김상익
-- 작성일: 2025.06.21
-- DBMS: MySQL 8.0 이상 (UUID() 함수 사용)
-- DB Name: AIMEX_MAIN
-- Schema Name: AIMEX_MAIN_schema
-- 
-- 주의: MySQL 8.0 미만 버전에서는 UUID() 대신 애플리케이션에서 UUID 생성 필요
-- ===================================================

-- 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS AIMEX_MAIN;
USE AIMEX_MAIN;

-- ===================================================
-- 1. USER 테이블 (유저)
-- 설명: 사용자 정보 테이블
-- ===================================================
CREATE TABLE USER (
    user_id VARCHAR(255) NOT NULL DEFAULT (UUID()) COMMENT '내부 사용자 고유 id',
    provider_id VARCHAR(255) NOT NULL COMMENT '소셜 제공자의 고유 사용자 식별자',
    provider VARCHAR(20) NOT NULL COMMENT '소셜 로그인 제공자',
    user_name VARCHAR(20) NOT NULL COMMENT '사용자 이름',
    email VARCHAR(50) NOT NULL COMMENT '사용자 이메일',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '사용자가 처음 가입한 시각',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '사용자의 정보가 마지막으로 수정된 시각',
    PRIMARY KEY (user_id),
    UNIQUE KEY uk_user_id (user_id),
    UNIQUE KEY uk_provider_id (provider_id),
    UNIQUE KEY uk_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='사용자 정보 테이블';

-- ===================================================
-- 2. SYSTEM_LOG 테이블 (시스템 로그)
-- 설명: 각종 시스템 로그 데이터
-- ===================================================
CREATE TABLE SYSTEM_LOG (
    log_id VARCHAR(255) NOT NULL DEFAULT (UUID()) COMMENT '로그 고유 식별자',
    user_id VARCHAR(255) NOT NULL COMMENT '내부 사용자 고유 식별자',
    log_type TINYINT NOT NULL COMMENT '0: API요청, 1: 시스템오류, 2: 인증관련',
    log_content TEXT NOT NULL COMMENT 'API 요청 내용, 오류 메시지 등 상세한 로그 내용, JSON 형식으로 저장',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '로그 생성일',
    PRIMARY KEY (log_id),
    UNIQUE KEY uk_log_id (log_id),
    FOREIGN KEY (user_id) REFERENCES USER(user_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='각종 시스템 로그 데이터';

-- ===================================================
-- 3. GROUP 테이블 (그룹)
-- 설명: 사용자 그룹, 관리자 그룹 데이터
-- ===================================================
CREATE TABLE `GROUP` (
    group_id INTEGER NOT NULL AUTO_INCREMENT COMMENT '그룹 고유 식별자',
    group_name VARCHAR(100) NOT NULL COMMENT '그룹명',
    group_description TEXT COMMENT '그룹 설명',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '그룹 생성 시각',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '그룹 정보 마지막 수정 시각',
    PRIMARY KEY (group_id),
    UNIQUE KEY uk_group_id (group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='사용자 그룹, 관리자 그룹 데이터';

-- ===================================================
-- 4. HF_TOKEN_MANAGE 테이블 (허깅페이스토큰관리)
-- 설명: 그룹이 사용할 허깅페이스 토큰 데이터
-- ===================================================
CREATE TABLE HF_TOKEN_MANAGE (
    hf_manage_id VARCHAR(255) NOT NULL DEFAULT (UUID()) COMMENT '허깅페이스 토큰 관리 고유 식별자',
    group_id INTEGER NOT NULL COMMENT '그룹 고유 식별자',
    hf_token_value TEXT NOT NULL COMMENT '허깅페이스 실제 토큰 값 (암호화)',
    hf_token_nickname VARCHAR(100) NOT NULL COMMENT '사용자에게 보여지는 허깅페이스 토큰 별칭',
    hf_user_name VARCHAR(50) NOT NULL COMMENT '허깅페이스 계정 사용자 이름',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '허깅페이스 토큰 생성 시각',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '허깅페이스 토큰 마지막 수정 시각',
    PRIMARY KEY (hf_manage_id),
    UNIQUE KEY uk_hf_manage_id (hf_manage_id),
    FOREIGN KEY (group_id) REFERENCES `GROUP`(group_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='그룹이 사용할 허깅페이스 토큰 데이터';

-- ===================================================
-- 5. USER_GROUP 테이블 (유저-그룹)
-- 설명: 유저, 그룹 교차 테이블
-- ===================================================
CREATE TABLE USER_GROUP (
    user_id VARCHAR(255) NOT NULL COMMENT '내부 사용자 고유 식별자',
    group_id INTEGER NOT NULL COMMENT '그룹 고유 식별자',
    PRIMARY KEY (user_id, group_id),
    FOREIGN KEY (user_id) REFERENCES USER(user_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (group_id) REFERENCES `GROUP`(group_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='유저, 그룹 교차 테이블';

-- ===================================================
-- 6. MODEL_MBTI 테이블 (모델 MBTI)
-- 설명: AI 인플루언서 예시 성격 MBTI
-- ===================================================
CREATE TABLE MODEL_MBTI (
    mbti_id INTEGER NOT NULL COMMENT 'MBTI 성격 고유 식별자',
    mbti_name VARCHAR(100) NOT NULL COMMENT 'MBTI 이름',
    mbti_chara VARCHAR(255) NOT NULL COMMENT 'MBTI 별 성격, 특성',
    mbti_speech TEXT NOT NULL COMMENT 'MBTI 말투 설명',
    PRIMARY KEY (mbti_id),
    UNIQUE KEY uk_mbti_id (mbti_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI 인플루언서 예시 성격 MBTI';

-- ===================================================
-- 7. STYLE_PRESET 테이블 (스타일 프리셋)
-- 설명: AI 인플루언서 설정에서 입력하는 폼 항목 또는 공유 할 수 있는 프리셋
-- ===================================================
CREATE TABLE STYLE_PRESET (
    style_preset_id VARCHAR(255) NOT NULL DEFAULT (UUID()) COMMENT '스타일 프리셋 고유 식별자',
    style_preset_name VARCHAR(100) NOT NULL COMMENT '스타일 프리셋 이름',
    influencer_type TINYINT NOT NULL COMMENT '인플루언서 유형',
    influencer_gender TINYINT NOT NULL COMMENT '인플루언서 성별, 0:남성, 1:여성, 2:없음',
    influencer_age_group TINYINT NOT NULL COMMENT '인플루언서 연령대, (20대,30대, ...)',
    influencer_hairstyle VARCHAR(100) NOT NULL COMMENT '인플루언서 헤어 스타일',
    influencer_style VARCHAR(255) NOT NULL COMMENT '인플루언서 전체 스타일(힙함, 청순 등)',
    influencer_personality TEXT NOT NULL COMMENT '인플루언서 성격',
    influencer_speech TEXT NOT NULL COMMENT '인플루언서 말투',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '인플루언서 특징 생성 시각',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '인플루언서 특징 수정 시각',
    PRIMARY KEY (style_preset_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI 인플루언서 설정에서 입력하는 폼 항목 또는 공유 할 수 있는 프리셋';

-- ===================================================
-- 8. AI_INFLUENCER 테이블 (AI 인플루언서)
-- 설명: 사용자 학습 AI 인플로언서 모델
-- ===================================================
CREATE TABLE AI_INFLUENCER (
    influencer_id VARCHAR(255) NOT NULL COMMENT '인플루언서 고유 식별자',
    user_id VARCHAR(255) NOT NULL COMMENT '내부 사용자 고유 식별자',
    group_id INTEGER NOT NULL COMMENT '그룹 고유 식별자',
    style_preset_id VARCHAR(255) NOT NULL COMMENT '스타일 프리셋 고유 식별자',
    mbti_id INTEGER COMMENT 'MBTI 성격 고유 식별자',
    influencer_name VARCHAR(100) NOT NULL COMMENT 'AI 인플루언서 이름',
    image_url TEXT COMMENT '인플루언서 이미지를 받아오면 그대로 사용, 없다면 정보를 기반으로 만들어서 사용',
    influencer_data_url VARCHAR(255) COMMENT '인플루언서 학습 데이터셋 URL 경로',
    learning_status TINYINT NOT NULL COMMENT '인플루언서 학습 상태, 0: 학습 중, 1: 사용가능',
    influencer_model_repo VARCHAR(255) NOT NULL COMMENT '허깅페이스 repo URL 경로',
    chatbot_option BOOLEAN NOT NULL COMMENT '챗봇 생성 여부',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '인플루언서 생성시점',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '인플루언서 마지막 수정일',
    PRIMARY KEY (influencer_id, user_id, group_id),
    UNIQUE KEY uk_influencer_id (influencer_id),
    UNIQUE KEY uk_influencer_name (influencer_name),
    FOREIGN KEY (user_id, group_id) REFERENCES USER_GROUP(user_id, group_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (style_preset_id) REFERENCES STYLE_PRESET(style_preset_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (mbti_id) REFERENCES MODEL_MBTI(mbti_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='사용자 학습 AI 인플로언서 모델';

-- ===================================================
-- 9. BATCH_KEY 테이블 (배치키)
-- 설명: AI 인플루언서 데이터 셋 생성 ~ 학습까지 작업이 완료되었는지 확인시 보내는 요청 배치키이다. 작업이 완료되면 데이터 값은 사라진다.
-- ===================================================
CREATE TABLE BATCH_KEY (
    batch_key_id VARCHAR(255) NOT NULL DEFAULT (UUID()) COMMENT '배치키 고유 식별자',
    influencer_id VARCHAR(255) NOT NULL COMMENT '인플루언서 고유 식별자',
    batch_key VARCHAR(255) NOT NULL COMMENT '배치키 값',
    PRIMARY KEY (batch_key_id),
    UNIQUE KEY uk_batch_key_id (batch_key_id),
    FOREIGN KEY (influencer_id) REFERENCES AI_INFLUENCER(influencer_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI 인플루언서 데이터 셋 생성 ~ 학습까지 작업이 완료되었는지 확인시 보내는 요청 배치키';

-- ===================================================
-- 10. CHAT_MESSAGE 테이블 (대화 메시지)
-- 설명: 만들어진 모델과 챗봇 대화 기록을 저장하는 테이블
-- ===================================================
CREATE TABLE CHAT_MESSAGE (
    session_id INTEGER NOT NULL AUTO_INCREMENT COMMENT '대화 세션 고유 식별자',
    influencer_id VARCHAR(255) NOT NULL DEFAULT (UUID()) COMMENT '인플루언서 고유 식별자',
    message_content TEXT NOT NULL COMMENT '총 대화 내용, JSON 형식으로 저장',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '대화 시작 시각',
    end_at TIMESTAMP NOT NULL COMMENT '대화 종료 시각',
    PRIMARY KEY (session_id),
    FOREIGN KEY (influencer_id) REFERENCES AI_INFLUENCER(influencer_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='만들어진 모델과 챗봇 대화 기록을 저장하는 테이블';

-- ===================================================
-- 11. INFLUENCER_API 테이블 (인플루언서 API)
-- 설명: AI 인플루언서 대화 API 키 관리
-- ===================================================
CREATE TABLE INFLUENCER_API (
    api_id VARCHAR(255) NOT NULL DEFAULT (UUID()) COMMENT 'API 고유 식별자',
    influencer_id VARCHAR(255) NOT NULL COMMENT '모델 고유 식별자',
    api_value VARCHAR(255) NOT NULL COMMENT '발급된 API 값',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'API 최초 생성 시각',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'API 발급정보 마지막 수정 일시',
    PRIMARY KEY (api_id, influencer_id),
    UNIQUE KEY uk_api_id (api_id),
    UNIQUE KEY uk_api_value (api_value),
    FOREIGN KEY (influencer_id) REFERENCES AI_INFLUENCER(influencer_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI 인플루언서 대화 API 키 관리';

-- ===================================================
-- 12. API_CALL_AGGREGATION 테이블 (API호출 집계)
-- 설명: API 호출에 대해서 집계하여 저장하는 데이터
-- ===================================================
CREATE TABLE API_CALL_AGGREGATION (
    api_call_id VARCHAR(255) NOT NULL DEFAULT (UUID()) COMMENT 'API호출 집계 고유 식별자',
    api_id VARCHAR(255) NOT NULL COMMENT 'API 고유 식별자',
    influencer_id VARCHAR(255) NOT NULL COMMENT '모델 고유 식별자',
    daily_call_count INTEGER NOT NULL DEFAULT 0 COMMENT '일일 API 호출 횟수',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '일일 API 집계 데이터 생성일',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '일일 API 집계 데이터 수정일',
    PRIMARY KEY (api_call_id, api_id, influencer_id),
    UNIQUE KEY uk_api_call_id (api_call_id),
    FOREIGN KEY (api_id, influencer_id) REFERENCES INFLUENCER_API(api_id, influencer_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='API 호출에 대해서 집계하여 저장하는 데이터';

-- ===================================================
-- 13. BOARD 테이블 (게시글)
-- 설명: AI 인플루언서 작성 게시글 데이터
-- ===================================================
CREATE TABLE BOARD (
    board_id VARCHAR(255) NOT NULL DEFAULT (UUID()) COMMENT '게시물 고유 식별자',
    influencer_id VARCHAR(255) NOT NULL COMMENT '인플루언서 고유 식별자',
    user_id VARCHAR(255) NOT NULL COMMENT '내부 사용자 고유 식별자',
    group_id INTEGER NOT NULL COMMENT '그룹 고유 식별자',
    board_topic VARCHAR(255) NOT NULL COMMENT '게시글의 주제 또는 카테고리명',
    board_description TEXT COMMENT '게시글의 상세 설명',
    board_platform TINYINT NOT NULL COMMENT '0:인스타그램, 1:블로그, 2:페이스북',
    board_hash_tag TEXT COMMENT '해시태그 리스트, JSON 형식으로 저장',
    board_status TINYINT NOT NULL DEFAULT 0 COMMENT '0:최초생성, 1:임시저장, 2:예약, 3:발행됨',
    image_url TEXT NOT NULL COMMENT '게시글 썸네일 또는 대표 이미지 URL 경로',
    reservation_at TIMESTAMP COMMENT '게시글 예약 발행 일시',
    pulished_at TIMESTAMP COMMENT '게시물 발행 시각',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '게시글 생성 시각',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '게시글 수정 시각',
    PRIMARY KEY (board_id),
    UNIQUE KEY uk_board_id (board_id),
    FOREIGN KEY (influencer_id) REFERENCES AI_INFLUENCER(influencer_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (user_id, group_id) REFERENCES USER_GROUP(user_id, group_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI 인플루언서 작성 게시글 데이터';

-- ===================================================
-- DDL 생성 완료
-- ===================================================