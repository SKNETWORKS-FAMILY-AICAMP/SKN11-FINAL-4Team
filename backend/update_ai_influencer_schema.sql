-- ===================================================
-- AIMEX AI_INFLUENCER 테이블 스키마 업데이트
-- 누락된 필드들 추가
-- ===================================================

USE AIMEX_MAIN;

-- 컬럼이 이미 존재할 경우 오류가 발생할 수 있지만, 
-- 이는 정상적인 동작입니다.

-- AI_INFLUENCER 테이블에 누락된 필드들 추가
ALTER TABLE AI_INFLUENCER 
ADD COLUMN influencer_description TEXT COMMENT 'AI 인플루언서 설명';

ALTER TABLE AI_INFLUENCER 
ADD COLUMN influencer_personality TEXT COMMENT 'AI 인플루언서 성격';

ALTER TABLE AI_INFLUENCER 
ADD COLUMN influencer_tone TEXT COMMENT 'AI 인플루언서 말투/톤';

ALTER TABLE AI_INFLUENCER 
ADD COLUMN influencer_age_group INTEGER COMMENT 'AI 인플루언서 연령대';

ALTER TABLE AI_INFLUENCER 
ADD COLUMN voice_option BOOLEAN DEFAULT FALSE COMMENT '음성 생성 옵션';

ALTER TABLE AI_INFLUENCER 
ADD COLUMN image_option BOOLEAN DEFAULT FALSE COMMENT '이미지 생성 옵션';

-- Instagram 연동 관련 필드들
ALTER TABLE AI_INFLUENCER 
ADD COLUMN instagram_id VARCHAR(255) COMMENT '연동된 인스타그램 계정 ID';

ALTER TABLE AI_INFLUENCER 
ADD COLUMN instagram_access_token TEXT COMMENT '인스타그램 액세스 토큰';

ALTER TABLE AI_INFLUENCER 
ADD COLUMN instagram_connected_at TIMESTAMP COMMENT '인스타그램 계정 연동 일시';

ALTER TABLE AI_INFLUENCER 
ADD COLUMN instagram_is_active BOOLEAN DEFAULT FALSE COMMENT '인스타그램 연동 활성화 여부';

ALTER TABLE AI_INFLUENCER 
ADD COLUMN instagram_token_expires_at TIMESTAMP COMMENT '인스타그램 액세스 토큰 만료 일시';

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