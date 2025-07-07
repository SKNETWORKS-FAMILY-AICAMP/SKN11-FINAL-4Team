#!/usr/bin/env python3
"""
데이터베이스 테이블 목록을 확인하는 스크립트
"""

import pymysql
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

def check_database_tables():
    """데이터베이스 테이블 목록 확인"""
    
    # 데이터베이스 연결 정보
    database_url = os.getenv('DATABASE_URL', 'mysql+pymysql://portfoliouser:Ilikeyou123!@34.64.35.253:3306/AIMEX_MAIN')
    
    # URL에서 연결 정보 추출
    if database_url.startswith('mysql+pymysql://'):
        url_parts = database_url.replace('mysql+pymysql://', '').split('@')
        auth_parts = url_parts[0].split(':')
        host_db_parts = url_parts[1].split('/')
        host_port_parts = host_db_parts[0].split(':')
        
        db_config = {
            'host': host_port_parts[0],
            'port': int(host_port_parts[1]) if len(host_port_parts) > 1 else 3306,
            'user': auth_parts[0],
            'password': auth_parts[1] if len(auth_parts) > 1 else '',
            'database': host_db_parts[1],
            'charset': 'utf8mb4'
        }
    else:
        db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': 'password',
            'database': 'AIMEX_MAIN',
            'charset': 'utf8mb4'
        }
    
    try:
        # 데이터베이스 연결
        connection = pymysql.connect(
            host=db_config['host'],
            port=db_config.get('port', 3306),
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            charset=db_config['charset']
        )
        cursor = connection.cursor()
        
        print("🔍 데이터베이스 테이블 목록 확인 중...")
        
        # 모든 테이블 목록 조회
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        print(f"📊 총 {len(tables)}개의 테이블이 있습니다:")
        for table in tables:
            table_name = table[0]
            print(f"  - {table_name}")
            
            # 각 테이블의 레코드 수 확인
            try:
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
                count = cursor.fetchone()[0]
                print(f"    레코드 수: {count}")
            except Exception as e:
                print(f"    레코드 수 확인 실패: {e}")
        
        cursor.close()
        connection.close()
        
        print("\n✅ 테이블 목록 확인 완료!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        if 'connection' in locals():
            connection.close()

if __name__ == "__main__":
    check_database_tables()
