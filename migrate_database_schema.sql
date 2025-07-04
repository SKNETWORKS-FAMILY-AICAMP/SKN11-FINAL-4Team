-- AIMEX 데이터베이스 스키마 업데이트 스크립트
-- 실행 전에 반드시 데이터베이스 백업을 수행하세요!

USE AIMEX_MAIN;

-- 1. 기존 테이블들 확인
SHOW TABLES;

-- 2. TEAM 테이블 수정 (group_id -> team_id, group_name -> team_name 등)
-- 2-1. 새로운 컬럼들 추가
ALTER TABLE TEAM ADD COLUMN team_id INTEGER AUTO_INCREMENT PRIMARY KEY FIRST;
ALTER TABLE TEAM ADD COLUMN team_name VARCHAR(100) NOT NULL AFTER team_id;
ALTER TABLE TEAM ADD COLUMN team_description TEXT AFTER team_name;

-- 2-2. 기존 데이터 복사 (만약 group_id, group_name 등이 존재한다면)
-- UPDATE TEAM SET team_id = group_id, team_name = group_name, team_description = group_description;

-- 2-3. 기존 컬럼들 삭제 (데이터 이전 후)
-- ALTER TABLE TEAM DROP COLUMN group_id;
-- ALTER TABLE TEAM DROP COLUMN group_name;
-- ALTER TABLE TEAM DROP COLUMN group_description;

-- 3. USER-TEAM 테이블 생성 (USER_GROUP 대신)
CREATE TABLE IF NOT EXISTS `USER-TEAM` (
    `user_id` VARCHAR(255) NOT NULL,
    `team_id` INTEGER NOT NULL,
    PRIMARY KEY (`user_id`, `team_id`),
    FOREIGN KEY (`user_id`) REFERENCES `USER`(`user_id`) ON DELETE CASCADE,
    FOREIGN KEY (`team_id`) REFERENCES `TEAM`(`team_id`) ON DELETE CASCADE
);

-- 4. 기존 USER_GROUP 데이터를 USER-TEAM으로 이전 (필요시)
-- INSERT INTO `USER-TEAM` (user_id, team_id) 
-- SELECT user_id, group_id FROM USER_GROUP;

-- 5. BOARD 테이블 수정
-- 5-1. team_id 컬럼 추가 (group_id 대신)
ALTER TABLE BOARD ADD COLUMN team_id_new INTEGER NOT NULL AFTER user_id;

-- 5-2. 기존 group_id 데이터를 team_id_new로 복사 (필요시)
-- UPDATE BOARD SET team_id_new = group_id;

-- 5-3. 기존 group_id 컬럼 삭제하고 team_id_new를 team_id로 변경
-- ALTER TABLE BOARD DROP COLUMN group_id;
ALTER TABLE BOARD CHANGE team_id_new team_id INTEGER NOT NULL;

-- 5-4. created_at, updated_at 컬럼 수정
ALTER TABLE BOARD 
MODIFY COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '게시글 생성 시각';

ALTER TABLE BOARD 
MODIFY COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '게시글 수정 시각';

-- 5-5. 외래키 제약조건 재설정
ALTER TABLE BOARD DROP FOREIGN KEY IF EXISTS FK_USER_GROUP_TO_BOARD;
ALTER TABLE BOARD ADD CONSTRAINT FK_USER_TEAM_TO_BOARD 
FOREIGN KEY (user_id, team_id) REFERENCES `USER-TEAM`(user_id, team_id) ON DELETE CASCADE;

-- 6. AI_INFLUENCER 테이블 수정
-- 6-1. team_id 컬럼 추가
ALTER TABLE AI_INFLUENCER ADD COLUMN team_id_new INTEGER NOT NULL AFTER user_id;

-- 6-2. 기존 group_id 데이터 복사 (필요시)
-- UPDATE AI_INFLUENCER SET team_id_new = group_id;

-- 6-3. 기존 group_id 삭제하고 team_id_new를 team_id로 변경
-- ALTER TABLE AI_INFLUENCER DROP COLUMN group_id;
ALTER TABLE AI_INFLUENCER CHANGE team_id_new team_id INTEGER NOT NULL;

-- 7. HF_TOKEN_MANAGE 테이블 수정
-- 7-1. team_id 컬럼 추가
ALTER TABLE HF_TOKEN_MANAGE ADD COLUMN team_id_new INTEGER NOT NULL AFTER hf_manage_id;

-- 7-2. 기존 group_id 데이터 복사 (필요시)
-- UPDATE HF_TOKEN_MANAGE SET team_id_new = group_id;

-- 7-3. 기존 group_id 삭제하고 team_id_new를 team_id로 변경
-- ALTER TABLE HF_TOKEN_MANAGE DROP COLUMN group_id;
ALTER TABLE HF_TOKEN_MANAGE CHANGE team_id_new team_id INTEGER NOT NULL;

-- 8. 외래키 제약조건들 재설정
ALTER TABLE AI_INFLUENCER ADD CONSTRAINT FK_TEAM_TO_AI_INFLUENCER 
FOREIGN KEY (team_id) REFERENCES TEAM(team_id) ON DELETE CASCADE;

ALTER TABLE HF_TOKEN_MANAGE ADD CONSTRAINT FK_TEAM_TO_HF_TOKEN_MANAGE 
FOREIGN KEY (team_id) REFERENCES TEAM(team_id) ON DELETE CASCADE;

-- 9. 수정 후 테이블 구조 확인
DESCRIBE TEAM;
DESCRIBE `USER-TEAM`;
DESCRIBE BOARD;
DESCRIBE AI_INFLUENCER;
DESCRIBE HF_TOKEN_MANAGE;

-- 10. 기존 USER_GROUP 테이블 삭제 (데이터 이전이 완료된 후)
-- DROP TABLE IF EXISTS USER_GROUP;

COMMIT;
