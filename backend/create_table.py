#!/usr/bin/env python3
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

# 데이터베이스 연결 정보
host = "34.64.35.253"
user = "portfoliouser"
password = "Ilikeyou123!"
database = "AIMEX_MAIN"

# SQL 스크립트
sql = """
CREATE TABLE IF NOT EXISTS content_enhancements (
    enhancement_id VARCHAR(36) NOT NULL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    original_content TEXT NOT NULL,
    enhanced_content TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    openai_model VARCHAR(50) NULL,
    openai_tokens_used INT NULL,
    openai_cost FLOAT NULL,
    board_id VARCHAR(36) NULL,
    influencer_id VARCHAR(36) NULL,
    enhancement_prompt TEXT NULL,
    improvement_notes TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
    approved_at DATETIME NULL,
    INDEX idx_content_enhancements_user_id (user_id),
    INDEX idx_content_enhancements_enhancement_id (enhancement_id)
);
"""

try:
    # 데이터베이스 연결
    connection = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        charset='utf8mb4'
    )
    
    with connection.cursor() as cursor:
        # 테이블 생성 실행
        cursor.execute(sql)
        connection.commit()
        print("content_enhancements 테이블이 성공적으로 생성되었습니다.")
        
        # 테이블 존재 확인
        cursor.execute("SHOW TABLES LIKE 'content_enhancements'")
        result = cursor.fetchone()
        if result:
            print("테이블 생성이 확인되었습니다.")
        else:
            print("테이블 생성 실패.")
            
except Exception as e:
    print(f"오류 발생: {e}")
finally:
    if 'connection' in locals():
        connection.close()