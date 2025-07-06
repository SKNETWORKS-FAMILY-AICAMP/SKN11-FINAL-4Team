#!/usr/bin/env python3
"""
데이터베이스 컬럼명 변경 스크립트 (group_id -> team_id)
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

def execute_column_rename():
    """컬럼명 변경 실행"""
    load_dotenv('backend/.env')
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL 환경변수가 설정되지 않았습니다.")
        return False
    
    try:
        db_config = parse_database_url(database_url)
        print(f"데이터베이스 연결 시도: {db_config['user']}@{db_config['host']}:{db_config['port']}/{db_config['database']}")
        
        connection = mysql.connector.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database']
        )
        
        cursor = connection.cursor()
        
        print("=== 컬럼명 변경 시작 ===")
        
        # BOARD 테이블의 group_id -> team_id 변경
        try:
            cursor.execute("""
                ALTER TABLE BOARD 
                CHANGE group_id team_id INT NOT NULL COMMENT '팀 고유 식별자'
            """)
            print("✅ BOARD.group_id → team_id 변경 완료")
        except mysql.connector.Error as e:
            print(f"⚠️ BOARD.group_id 변경 오류: {e}")
        
        connection.commit()
        print("=== 컬럼명 변경 완료 ===")
        
        # 수정 후 테이블 구조 확인
        print("\n=== 수정 후 BOARD 테이블 구조 ===")
        cursor.execute("DESCRIBE BOARD")
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
                print("\n📝 데이터베이스 연결이 정상적으로 종료되었습니다.")
        except:
            pass

if __name__ == "__main__":
    print("BOARD 테이블 컬럼명 변경 스크립트 (group_id → team_id)")
    print("=" * 60)
    
    success = execute_column_rename()
    
    if success:
        print("\n✅ 컬럼명 변경이 완료되었습니다!")
        print("이제 백엔드 서버를 재시작하세요:")
        print("  cd backend && python run.py")
    else:
        print("\n❌ 변경 중 오류가 발생했습니다.")
