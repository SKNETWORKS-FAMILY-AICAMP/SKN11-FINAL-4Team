-- BOARD 테이블에 published_at 컬럼 추가
ALTER TABLE BOARD ADD COLUMN published_at TIMESTAMP NULL COMMENT '게시물 발행 시각';