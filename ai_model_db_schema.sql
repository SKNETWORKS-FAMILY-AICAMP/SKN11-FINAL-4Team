-- ============================================
-- AIMEX AI 인플루언서 모델 관리 시스템
-- 테이블 명세서 기반 정확한 데이터베이스 스키마
-- ============================================\]8ㅈ5
-- 시스템/서비스: AIMEX
-- 작성자: 김상익
-- 작성일: 2025.06.21
-- 프로젝트명: AIMEX
-- DBMS: MySQL
-- DB Name: AIMEX_MAIN
-- Schema Name: AIMEX_MAIN_schema
-- ============================================

-- 데이터베이스 생성 및 설정
CREATE DATABASE IF NOT EXISTS AIMEX_MAIN
CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE AIMEX_MAIN;

-- ============================================
-- 1. 사용자 정보 테이블 (USER)
-- ============================================
DROP TABLE IF EXISTS `USER`;
CREATE TABLE `USER` (
    user_uuid CHAR(36) PRIMARY KEY DEFAULT (UUID()) COMMENT '사용자 고유 식별자',
    provider_id VARCHAR(20) NOT NULL COMMENT '소셜 로그인 제공자별 사용자 ID',
    provider VARCHAR(20) NOT NULL COMMENT '소셜 로그인 제공자 구분',
    user_name VARCHAR(20) NOT NULL COMMENT '사용자 이름',
    email VARCHAR(50) NOT NULL COMMENT '사용자 이메일',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '사용자 등록일시',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '사용자 정보 수정일시'
) COMMENT '사용자 정보 테이블';

-- ============================================
-- 2. 사용자 그룹, 관리자 그룹 데이터 (`GROUP`)
-- ============================================
DROP TABLE IF EXISTS `GROUP`;
CREATE TABLE `GROUP` (
    group_uuid CHAR(36) PRIMARY KEY DEFAULT (UUID()) COMMENT '그룹 고유 식별자',
    group_name VARCHAR(100) NOT NULL COMMENT '그룹 이름',
    group_description TEXT NULL COMMENT '그룹 설명',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '그룹 생성일시',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '그룹 수정일시'
) COMMENT '사용자 그룹, 관리자 그룹 데이터';

-- ============================================
-- 3. 유저, 그룹 교차 테이블 (USER_GROUP)
-- ============================================
DROP TABLE IF EXISTS USER_GROUP;
CREATE TABLE USER_GROUP (
    user_uuid CHAR(36) NOT NULL COMMENT '사용자 고유 식별자',
    group_uuid CHAR(36) NOT NULL COMMENT '그룹 고유 식별자',
    
    PRIMARY KEY (user_uuid, group_uuid),
    FOREIGN KEY (user_uuid) REFERENCES `USER`(user_uuid) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (group_uuid) REFERENCES `GROUP`(group_uuid) ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT '유저, 그룹 교차 테이블';

-- ============================================
-- 4. AI 인플루언서 예시 성격 MBTI (MODEL_MBTI)
-- ============================================
DROP TABLE IF EXISTS MODEL_MBTI;
CREATE TABLE MODEL_MBTI (
    mbti_id INT PRIMARY KEY AUTO_INCREMENT COMMENT 'MBTI 성격 고유 식별자',
    mbti_name VARCHAR(100) NOT NULL COMMENT 'MBTI 성격 이름',
    mbti_chara VARCHAR(255) NOT NULL COMMENT 'MBTI 성격 특성',
    mbti_speaks TEXT NOT NULL COMMENT 'MBTI 말투 특성',
    mbti_data_url VARCHAR(255) NOT NULL COMMENT 'MBTI 관련 데이터 URL'
) COMMENT 'AI 인플루언서 예시 성격 MBTI';

-- ============================================
-- 5. 사용자 학습 AI 인플로언서 모델 (ML)
-- ============================================
DROP TABLE IF EXISTS ML;
CREATE TABLE ML (
    model_uuid CHAR(36) PRIMARY KEY DEFAULT (UUID()) COMMENT '모델 고유 id',
    group_uuid CHAR(36) NOT NULL COMMENT '그룹 고유 식별자',
    mbti_id INT NOT NULL COMMENT 'MBTI 성격 고유 식별자',
    model_name VARCHAR(100) NOT NULL COMMENT '모델 이름',
    model_description TEXT NULL COMMENT '모델 설명',
    model_personality VARCHAR(50) NOT NULL COMMENT '모델 성격',
    model_speaks VARCHAR(50) NOT NULL COMMENT '모델 말투',
    model_repo VARCHAR(255) NOT NULL COMMENT '허깅페이스 repo URL',
    image_url VARCHAR(255) NULL COMMENT '대표 이미지 파일 URL',
    model_status TINYINT NOT NULL DEFAULT 0 COMMENT '0: 학습 중, 1: 사용가능',
    model_data_url VARCHAR(255) NULL COMMENT '모델 학습 데이터셋 url',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '모델 생성시점',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '모델 마지막 수정일',
    
    UNIQUE KEY uk_model_name (model_name),
    FOREIGN KEY (group_uuid) REFERENCES `GROUP`(group_uuid) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (mbti_id) REFERENCES MODEL_MBTI(mbti_id) ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT '사용자 학습 AI 인플로언서 모델';

-- ============================================
-- 6. AI 인플루언서 작성 게시글 데이터 (BOARD)
-- ============================================
DROP TABLE IF EXISTS BOARD;
CREATE TABLE BOARD (
    board_uuid CHAR(36) PRIMARY KEY DEFAULT (UUID()) COMMENT '게시글 고유 식별자',
    group_uuid CHAR(36) NOT NULL COMMENT '그룹 고유 식별자',
    model_uuid CHAR(36) NOT NULL COMMENT '모델 고유 식별자',
    board_topic VARCHAR(100) NOT NULL COMMENT '게시글 주제',
    board_description TEXT NULL COMMENT '게시글 상세 설명',
    board_platform TINYINT NOT NULL COMMENT '게시 플랫폼 구분',
    board_hash_tag JSON NULL COMMENT '해시태그 목록',
    reservation_at TIMESTAMP NULL COMMENT '게시글 예약 시간',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '게시글 생성 시간',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '게시글 수정 시간',
    board_status TINYINT NOT NULL COMMENT '게시글 상태',
    pulished_at TIMESTAMP NULL COMMENT '게시글 발행 시간',
    image_url JSON NULL COMMENT '첨부 이미지 경로들',
    
    FOREIGN KEY (group_uuid) REFERENCES `GROUP`(group_uuid) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (model_uuid) REFERENCES ML(model_uuid) ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT 'AI 인플루언서 작성 게시글 데이터';

-- ============================================
-- 7. AI 인플루언서 대화 API 관리 (ML_API)
-- ============================================
DROP TABLE IF EXISTS ML_API;
CREATE TABLE ML_API (
    api_uuid CHAR(36) PRIMARY KEY DEFAULT (UUID()) COMMENT 'API 고유 식별자',
    model_uuid CHAR(36) NOT NULL COMMENT '모델 고유 식별자',
    group_uuid CHAR(36) NOT NULL COMMENT '그룹 고유 식별자',
    api_value VARCHAR(255) NOT NULL COMMENT 'API 키 값',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'API 생성일',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'API 수정일',
    
    FOREIGN KEY (model_uuid) REFERENCES ML(model_uuid) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (group_uuid) REFERENCES `GROUP`(group_uuid) ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT 'AI 인플루언서 대화 API 관리';

-- ============================================
-- 8. API 호출에 대해서 집계하여 저장하는 데이터 (API_CALL_AGGREGATION)
-- ============================================
DROP TABLE IF EXISTS API_CALL_AGGREGATION;
CREATE TABLE API_CALL_AGGREGATION (
    api_call_uuid CHAR(36) PRIMARY KEY DEFAULT (UUID()) COMMENT 'API 호출 집계 고유 식별자',
    api_uuid CHAR(36) NOT NULL COMMENT 'API 고유 식별자',
    model_uuid CHAR(36) NOT NULL COMMENT '모델 고유 식별자',
    group_uuid CHAR(36) NOT NULL COMMENT '그룹 고유 식별자',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '집계 데이터 생성일',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '집계 데이터 수정일',
    daily_call_count INT NOT NULL COMMENT '일일 API 호출 횟수',
    
    FOREIGN KEY (api_uuid) REFERENCES ML_API(api_uuid) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (model_uuid) REFERENCES ML(model_uuid) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (group_uuid) REFERENCES `GROUP`(group_uuid) ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT 'API 호출에 대해서 집계하여 저장하는 데이터';

-- ============================================
-- 9. 그룹이 사용할 허깅페이스 토큰 데이터 (HF_TOKEN_MANAGE)
-- ============================================
DROP TABLE IF EXISTS HF_TOKEN_MANAGE;
CREATE TABLE HF_TOKEN_MANAGE (
    hf_manage_uuid CHAR(36) PRIMARY KEY DEFAULT (UUID()) COMMENT '허깅페이스 토큰 관리 고유 식별자',
    group_uuid CHAR(36) NOT NULL COMMENT '그룹 고유 식별자',
    hf_token_value TEXT NOT NULL COMMENT '허깅페이스 토큰 값',
    hf_token_nickname VARCHAR(100) NOT NULL COMMENT '허깅페이스 토큰 별칭',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '토큰 생성일시',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '토큰 수정일시',
    hf_user_name VARCHAR(50) NOT NULL COMMENT '허깅페이스 사용자명',
    
    FOREIGN KEY (group_uuid) REFERENCES `GROUP`(group_uuid) ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT '그룹이 사용할 허깅페이스 토큰 데이터';

-- ============================================
-- 10. 각종 시스템 로그 데이터 (SYSTEM_LOG)
-- ============================================
DROP TABLE IF EXISTS SYSTEM_LOG;
CREATE TABLE SYSTEM_LOG (
    log_uuid CHAR(36) PRIMARY KEY DEFAULT (UUID()) COMMENT '로그 고유 식별자',
    user_uuid CHAR(36) NOT NULL COMMENT '사용자 고유 식별자',
    created_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '로그 생성일시',
    log_type TINYINT NOT NULL COMMENT '로그 유형',
    log_content JSON NOT NULL COMMENT '로그 내용',
    
    FOREIGN KEY (user_uuid) REFERENCES `USER`(user_uuid) ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT '각종 시스템 로그 데이터';

-- ============================================
-- 데이터베이스 생성 완료 메시지
-- ============================================

SELECT 'AIMEX 데이터베이스 스키마 생성이 완료되었습니다.' as message,
       'CSV 명세서의 정확한 구현 (인덱스 제외)' as note;