#!/usr/bin/env python3
"""
BOARD 테이블 구조 확인 및 수정 스크립트
"""

import mysql.connector
import os
from dotenv import load_dotenv

def check_board_table():
    """BOARD 테이블 구조 확인"""
    load_dotenv('backend/.env')
    
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_DATABASE', 'AIMEX_MAIN')
        )
        
        cursor = connection.cursor()
        
        print("=== BOARD 테이블 구조 확인 ===")
        cursor.execute("DESCRIBE BOARD")
        columns = cursor.fetchall()
        
        for column in columns:
            print(f"Column: {column[0]}, Type: {column[1]}, Null: {column[2]}, Default: {column[4]}")
        
        print("\n=== 테이블 생성 구문 확인 ===")
        cursor.execute("SHOW CREATE TABLE BOARD")
        create_table = cursor.fetchone()
        print(create_table[1])
        
        return True
        
    except mysql.connector.Error as e:
        print(f"데이터베이스 연결 오류: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def fix_board_table():
    """BOARD 테이블 수정"""
    load_dotenv('backend/.env')
    
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_DATABASE', 'AIMEX_MAIN')
        )
        
        cursor = connection.cursor()
        
        print("=== BOARD 테이블 수정 시작 ===")
        
        # 1. group_id를 team_id로 변경 (만약 존재한다면)
        try:
            cursor.execute("ALTER TABLE BOARD CHANGE group_id team_id INTEGER NOT NULL COMMENT '팀 고유 식별자'")
            print("✓ group_id를 team_id로 변경 완료")
        except mysql.connector.Error as e:
            print(f"group_id -> team_id 변경 스킵 (이미 처리되었거나 필요없음): {e}")
        
        # 2. created_at 컬럼 수정 (DEFAULT 값 추가)
        try:
            cursor.execute("""
                ALTER TABLE BOARD 
                MODIFY COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '게시글 생성 시각'
            """)
            print("✓ created_at 컬럼 DEFAULT 값 설정 완료")
        except mysql.connector.Error as e:
            print(f"created_at 수정 실패: {e}")
        
        # 3. updated_at 컬럼 수정 (DEFAULT 값 및 ON UPDATE 추가)
        try:
            cursor.execute("""
                ALTER TABLE BOARD 
                MODIFY COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '게시글 수정 시각'
            """)
            print("✓ updated_at 컬럼 DEFAULT 값 및 ON UPDATE 설정 완료")
        except mysql.connector.Error as e:
            print(f"updated_at 수정 실패: {e}")
        
        connection.commit()
        print("=== BOARD 테이블 수정 완료 ===")
        
        return True
        
    except mysql.connector.Error as e:
        print(f"데이터베이스 연결 오류: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == "__main__":
    print("1. 테이블 구조 확인")
    check_board_table()
    
    print("\n" + "="*50)
    response = input("테이블을 수정하시겠습니까? (y/n): ")
    
    if response.lower() == 'y':
        print("\n2. 테이블 수정 실행")
        fix_board_table()
        
        print("\n3. 수정 후 테이블 구조 재확인")
        check_board_table()
    else:
        print("수정을 건너뜁니다.")
