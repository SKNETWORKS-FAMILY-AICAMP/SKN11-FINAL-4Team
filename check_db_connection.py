#!/usr/bin/env python3
"""
데이터베이스 연결 정보 확인 스크립트
"""

import os
from dotenv import load_dotenv
from urllib.parse import urlparse

def check_database_config():
    """데이터베이스 설정 확인"""
    load_dotenv('backend/.env')
    
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ DATABASE_URL 환경변수가 설정되지 않았습니다.")
        return
    
    print(f"📋 DATABASE_URL: {database_url}")
    
    try:
        parsed = urlparse(database_url)
        
        print("\n📊 연결 정보:")
        print(f"  호스트: {parsed.hostname}")
        print(f"  포트: {parsed.port or 3306}")
        print(f"  사용자: {parsed.username}")
        print(f"  비밀번호: {'*' * len(parsed.password) if parsed.password else 'None'}")
        print(f"  데이터베이스: {parsed.path.lstrip('/')}")
        
        # MySQL 연결 테스트 (비밀번호 마스킹)
        import mysql.connector
        
        connection = mysql.connector.connect(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip('/')
        )
        
        if connection.is_connected():
            print("\n✅ 데이터베이스 연결 성공!")
            
            cursor = connection.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print(f"📋 MySQL 버전: {version[0]}")
            
            cursor.execute("SHOW TABLES LIKE 'BOARD'")
            result = cursor.fetchone()
            if result:
                print("✅ BOARD 테이블이 존재합니다.")
            else:
                print("❌ BOARD 테이블이 존재하지 않습니다.")
            
            cursor.close()
            connection.close()
        
    except Exception as e:
        print(f"\n❌ 연결 실패: {e}")

if __name__ == "__main__":
    print("데이터베이스 연결 정보 확인")
    print("=" * 40)
    check_database_config()
