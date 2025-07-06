-- BOARD 테이블 수정 SQL 스크립트
-- 실행 전에 백업을 권장합니다.

USE AIMEX_MAIN;

-- 1. 현재 테이블 구조 확인
DESCRIBE BOARD;

-- 2. group_id가 존재하는지 확인하고 team_id로 변경 (필요시)
-- 이 쿼리는 group_id 컬럼이 존재할 때만 실행하세요
-- ALTER TABLE BOARD CHANGE group_id team_id INTEGER NOT NULL COMMENT '팀 고유 식별자';

-- 3. created_at 컬럼 수정 (DEFAULT 값 추가)
ALTER TABLE BOARD 
MODIFY COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '게시글 생성 시각';

-- 4. updated_at 컬럼 수정 (DEFAULT 값 및 ON UPDATE 추가)
ALTER TABLE BOARD 
MODIFY COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '게시글 수정 시각';

-- 5. 수정 후 테이블 구조 재확인
DESCRIBE BOARD;

-- 6. 테이블 생성 구문 확인
SHOW CREATE TABLE BOARD;
