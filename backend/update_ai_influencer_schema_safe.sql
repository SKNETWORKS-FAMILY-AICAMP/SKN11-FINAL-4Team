-- ===================================================
-- AIMEX AI_INFLUENCER 테이블 스키마 업데이트 (오류 무시 버전)
-- 누락된 필드들 추가 - 중복 컬럼 오류 무시
-- ===================================================

USE AIMEX_MAIN;

-- 각 컬럼을 개별적으로 추가 (오류 발생 시 무시하고 계속)
SET sql_mode = '';

-- 1. influencer_description 추가 시도
SET @sql = 'ALTER TABLE AI_INFLUENCER ADD COLUMN influencer_description TEXT COMMENT ''AI 인플루언서 설명''';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
    AND TABLE_NAME = 'AI_INFLUENCER' 
    AND COLUMN_NAME = 'influencer_description') = 0, @sql, 'SELECT ''influencer_description already exists'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2. influencer_personality 추가 시도
SET @sql = 'ALTER TABLE AI_INFLUENCER ADD COLUMN influencer_personality TEXT COMMENT ''AI 인플루언서 성격''';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
    AND TABLE_NAME = 'AI_INFLUENCER' 
    AND COLUMN_NAME = 'influencer_personality') = 0, @sql, 'SELECT ''influencer_personality already exists'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. influencer_tone 추가 시도
SET @sql = 'ALTER TABLE AI_INFLUENCER ADD COLUMN influencer_tone TEXT COMMENT ''AI 인플루언서 말투/톤''';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
    AND TABLE_NAME = 'AI_INFLUENCER' 
    AND COLUMN_NAME = 'influencer_tone') = 0, @sql, 'SELECT ''influencer_tone already exists'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 4. influencer_age_group 추가 시도
SET @sql = 'ALTER TABLE AI_INFLUENCER ADD COLUMN influencer_age_group INTEGER COMMENT ''AI 인플루언서 연령대''';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
    AND TABLE_NAME = 'AI_INFLUENCER' 
    AND COLUMN_NAME = 'influencer_age_group') = 0, @sql, 'SELECT ''influencer_age_group already exists'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 5. voice_option 추가 시도
SET @sql = 'ALTER TABLE AI_INFLUENCER ADD COLUMN voice_option BOOLEAN DEFAULT FALSE COMMENT ''음성 생성 옵션''';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
    AND TABLE_NAME = 'AI_INFLUENCER' 
    AND COLUMN_NAME = 'voice_option') = 0, @sql, 'SELECT ''voice_option already exists'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 6. image_option 추가 시도
SET @sql = 'ALTER TABLE AI_INFLUENCER ADD COLUMN image_option BOOLEAN DEFAULT FALSE COMMENT ''이미지 생성 옵션''';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
    AND TABLE_NAME = 'AI_INFLUENCER' 
    AND COLUMN_NAME = 'image_option') = 0, @sql, 'SELECT ''image_option already exists'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 7. instagram_id 추가 시도
SET @sql = 'ALTER TABLE AI_INFLUENCER ADD COLUMN instagram_id VARCHAR(255) COMMENT ''연동된 인스타그램 계정 ID''';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
    AND TABLE_NAME = 'AI_INFLUENCER' 
    AND COLUMN_NAME = 'instagram_id') = 0, @sql, 'SELECT ''instagram_id already exists'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 8. instagram_access_token 추가 시도
SET @sql = 'ALTER TABLE AI_INFLUENCER ADD COLUMN instagram_access_token TEXT COMMENT ''인스타그램 액세스 토큰''';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
    AND TABLE_NAME = 'AI_INFLUENCER' 
    AND COLUMN_NAME = 'instagram_access_token') = 0, @sql, 'SELECT ''instagram_access_token already exists'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 9. instagram_connected_at 추가 시도
SET @sql = 'ALTER TABLE AI_INFLUENCER ADD COLUMN instagram_connected_at TIMESTAMP COMMENT ''인스타그램 계정 연동 일시''';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
    AND TABLE_NAME = 'AI_INFLUENCER' 
    AND COLUMN_NAME = 'instagram_connected_at') = 0, @sql, 'SELECT ''instagram_connected_at already exists'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 10. instagram_is_active 추가 시도
SET @sql = 'ALTER TABLE AI_INFLUENCER ADD COLUMN instagram_is_active BOOLEAN DEFAULT FALSE COMMENT ''인스타그램 연동 활성화 여부''';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
    AND TABLE_NAME = 'AI_INFLUENCER' 
    AND COLUMN_NAME = 'instagram_is_active') = 0, @sql, 'SELECT ''instagram_is_active already exists'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 11. instagram_token_expires_at 추가 시도
SET @sql = 'ALTER TABLE AI_INFLUENCER ADD COLUMN instagram_token_expires_at TIMESTAMP COMMENT ''인스타그램 액세스 토큰 만료 일시''';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'AIMEX_MAIN' 
    AND TABLE_NAME = 'AI_INFLUENCER' 
    AND COLUMN_NAME = 'instagram_token_expires_at') = 0, @sql, 'SELECT ''instagram_token_expires_at already exists'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 최종 테이블 구조 확인
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