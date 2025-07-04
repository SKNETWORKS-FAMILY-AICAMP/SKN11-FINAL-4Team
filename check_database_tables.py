#!/usr/bin/env python3
"""
데이터베이스 테이블 목록 확인 스크립트
"""

import mysql.connector
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

def parse_database_url(database_url):
    """DATABASE_URL을 파싱하여 개별 연결 정보 추출"""
    parsed = urlparse(database_url)
    return {
        'host': parsed.hostname,
        'port': parsed.port or 3306,
        'user': parsed.username,
        'password': parsed.password,
        'database': parsed.path.lstrip('/')
    }

def check_tables():
    """데이터베이스 테이블 목록 확인"""
    load_dotenv('backend/.env')
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL 환경변수가 설정되지 않았습니다.")
        return False
    
    try:
        db_config = parse_database_url(database_url)
        print(f"데이터베이스 연결: {db_config['user']}@{db_config['host']}:{db_config['port']}/{db_config['database']}")
        
        connection = mysql.connector.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database']
        )
        
        cursor = connection.cursor()
        
        print("\n=== 현재 데이터베이스의 모든 테이블 ===")
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        for table in tables:
            print(f"  📋 {table[0]}")
        
        print(f"\n총 {len(tables)}개의 테이블이 존재합니다.")
        
        # USER-TEAM 관련 테이블 찾기
        user_team_tables = [table[0] for table in tables if 'USER' in table[0] and ('TEAM' in table[0] or 'GROUP' in table[0])]
        
        if user_team_tables:
            print(f"\n=== 사용자-팀 관련 테이블 ===")
            for table_name in user_team_tables:
                print(f"  🔍 {table_name}")
                cursor.execute(f"DESCRIBE {table_name}")
                columns = cursor.fetchall()
                for column in columns:
                    print(f"    - {column[0]:<15} {column[1]:<15} {column[2]:<5}")
        else:
            print("\n❌ 사용자-팀 관련 테이블을 찾을 수 없습니다.")
        
        # USER와 TEAM 테이블 구조 확인
        for table_name in ['USER', 'TEAM']:
            if any(table[0] == table_name for table in tables):
                print(f"\n=== {table_name} 테이블 구조 ===")
                cursor.execute(f"DESCRIBE {table_name}")
                columns = cursor.fetchall()
                for column in columns:
                    print(f"  {column[0]:<20} {column[1]:<15} {column[2]:<5} {column[4] or 'NULL'}")
        
        return True
        
    except mysql.connector.Error as e:
        print(f"❌ 데이터베이스 연결 오류: {e}")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        return False
    finally:
        try:
            if 'connection' in locals() and connection.is_connected():
                cursor.close()
                connection.close()
        except:
            pass

if __name__ == "__main__":
    print("데이터베이스 테이블 목록 확인 스크립트")
    print("=" * 50)
    check_tables()
