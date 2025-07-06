-- ===================================================
-- AIMEX AI_INFLUENCER 테이블 스키마 업데이트 (수정된 버전)
-- 누락된 필드들 추가 - MySQL 8.0 이전 버전 호환
-- ===================================================

USE AIMEX_MAIN;

-- 컬럼 추가 함수 (MySQL 8.0 이전 버전 호환)
DELIMITER $$

-- influencer_description 컬럼 추가
DROP PROCEDURE IF EXISTS AddColumnIfNotExists$$
CREATE PROCEDURE AddColumnIfNotExists()
BEGIN
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
        AND TABLE_NAME = 'AI_INFLUENCER' 
        AND COLUMN_NAME = 'influencer_description'
    ) THEN
        ALTER TABLE AI_INFLUENCER ADD COLUMN influencer_description TEXT COMMENT 'AI 인플루언서 설명';
    END IF;
END$$

CALL AddColumnIfNotExists()$$
DROP PROCEDURE AddColumnIfNotExists$$

-- influencer_personality 컬럼 추가
CREATE PROCEDURE AddColumnIfNotExists()
BEGIN
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
        AND TABLE_NAME = 'AI_INFLUENCER' 
        AND COLUMN_NAME = 'influencer_personality'
    ) THEN
        ALTER TABLE AI_INFLUENCER ADD COLUMN influencer_personality TEXT COMMENT 'AI 인플루언서 성격';
    END IF;
END$$

CALL AddColumnIfNotExists()$$
DROP PROCEDURE AddColumnIfNotExists$$

-- influencer_tone 컬럼 추가
CREATE PROCEDURE AddColumnIfNotExists()
BEGIN
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
        AND TABLE_NAME = 'AI_INFLUENCER' 
        AND COLUMN_NAME = 'influencer_tone'
    ) THEN
        ALTER TABLE AI_INFLUENCER ADD COLUMN influencer_tone TEXT COMMENT 'AI 인플루언서 말투/톤';
    END IF;
END$$

CALL AddColumnIfNotExists()$$
DROP PROCEDURE AddColumnIfNotExists$$

-- influencer_age_group 컬럼 추가
CREATE PROCEDURE AddColumnIfNotExists()
BEGIN
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
        AND TABLE_NAME = 'AI_INFLUENCER' 
        AND COLUMN_NAME = 'influencer_age_group'
    ) THEN
        ALTER TABLE AI_INFLUENCER ADD COLUMN influencer_age_group INTEGER COMMENT 'AI 인플루언서 연령대';
    END IF;
END$$

CALL AddColumnIfNotExists()$$
DROP PROCEDURE AddColumnIfNotExists$$

-- voice_option 컬럼 추가
CREATE PROCEDURE AddColumnIfNotExists()
BEGIN
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
        AND TABLE_NAME = 'AI_INFLUENCER' 
        AND COLUMN_NAME = 'voice_option'
    ) THEN
        ALTER TABLE AI_INFLUENCER ADD COLUMN voice_option BOOLEAN DEFAULT FALSE COMMENT '음성 생성 옵션';
    END IF;
END$$

CALL AddColumnIfNotExists()$$
DROP PROCEDURE AddColumnIfNotExists$$

-- image_option 컬럼 추가
CREATE PROCEDURE AddColumnIfNotExists()
BEGIN
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
        AND TABLE_NAME = 'AI_INFLUENCER' 
        AND COLUMN_NAME = 'image_option'
    ) THEN
        ALTER TABLE AI_INFLUENCER ADD COLUMN image_option BOOLEAN DEFAULT FALSE COMMENT '이미지 생성 옵션';
    END IF;
END$$

CALL AddColumnIfNotExists()$$
DROP PROCEDURE AddColumnIfNotExists$$

-- instagram_id 컬럼 추가
CREATE PROCEDURE AddColumnIfNotExists()
BEGIN
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
        AND TABLE_NAME = 'AI_INFLUENCER' 
        AND COLUMN_NAME = 'instagram_id'
    ) THEN
        ALTER TABLE AI_INFLUENCER ADD COLUMN instagram_id VARCHAR(255) COMMENT '연동된 인스타그램 계정 ID';
    END IF;
END$$

CALL AddColumnIfNotExists()$$
DROP PROCEDURE AddColumnIfNotExists$$

-- instagram_access_token 컬럼 추가
CREATE PROCEDURE AddColumnIfNotExists()
BEGIN
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
        AND TABLE_NAME = 'AI_INFLUENCER' 
        AND COLUMN_NAME = 'instagram_access_token'
    ) THEN
        ALTER TABLE AI_INFLUENCER ADD COLUMN instagram_access_token TEXT COMMENT '인스타그램 액세스 토큰';
    END IF;
END$$

CALL AddColumnIfNotExists()$$
DROP PROCEDURE AddColumnIfNotExists$$

-- instagram_connected_at 컬럼 추가
CREATE PROCEDURE AddColumnIfNotExists()
BEGIN
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
        AND TABLE_NAME = 'AI_INFLUENCER' 
        AND COLUMN_NAME = 'instagram_connected_at'
    ) THEN
        ALTER TABLE AI_INFLUENCER ADD COLUMN instagram_connected_at TIMESTAMP COMMENT '인스타그램 계정 연동 일시';
    END IF;
END$$

CALL AddColumnIfNotExists()$$
DROP PROCEDURE AddColumnIfNotExists$$

-- instagram_is_active 컬럼 추가
CREATE PROCEDURE AddColumnIfNotExists()
BEGIN
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
        AND TABLE_NAME = 'AI_INFLUENCER' 
        AND COLUMN_NAME = 'instagram_is_active'
    ) THEN
        ALTER TABLE AI_INFLUENCER ADD COLUMN instagram_is_active BOOLEAN DEFAULT FALSE COMMENT '인스타그램 연동 활성화 여부';
    END IF;
END$$

CALL AddColumnIfNotExists()$$
DROP PROCEDURE AddColumnIfNotExists$$

-- instagram_token_expires_at 컬럼 추가
CREATE PROCEDURE AddColumnIfNotExists()
BEGIN
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
        AND TABLE_NAME = 'AI_INFLUENCER' 
        AND COLUMN_NAME = 'instagram_token_expires_at'
    ) THEN
        ALTER TABLE AI_INFLUENCER ADD COLUMN instagram_token_expires_at TIMESTAMP COMMENT '인스타그램 액세스 토큰 만료 일시';
    END IF;
END$$

CALL AddColumnIfNotExists()$$
DROP PROCEDURE AddColumnIfNotExists$$

DELIMITER ;

-- 스키마 업데이트 완료 확인
SELECT 
    COLUMN_NAME, 
    DATA_TYPE, 
    IS_NULLABLE, 
    COLUMN_DEFAULT, 
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
  AND TABLE_NAME = 'AI_INFLUENCER'
ORDER BY ORDINAL_POSITION;

COMMIT;