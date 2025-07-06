#!/usr/bin/env python3
"""
사용자를 기본 팀에 추가하는 스크립트
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

def setup_default_team_and_user():
    """기본 팀 생성 및 사용자 추가"""
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
        
        print("=== 현재 팀 및 사용자 상태 확인 ===")
        
        # 현재 팀 목록 확인
        cursor.execute("SELECT group_id, group_name FROM TEAM")
        teams = cursor.fetchall()
        print(f"현재 팀 수: {len(teams)}")
        for team in teams:
            print(f"  팀 ID: {team[0]}, 팀명: {team[1]}")
        
        # 현재 사용자 목록 확인
        cursor.execute("SELECT user_id, user_name, email FROM USER")
        users = cursor.fetchall()
        print(f"\n현재 사용자 수: {len(users)}")
        for user in users:
            print(f"  사용자 ID: {user[0]}, 이름: {user[1]}, 이메일: {user[2]}")
        
        # USER_GROUP 관계 확인
        cursor.execute("SELECT user_id, group_id FROM USER_GROUP")
        user_groups = cursor.fetchall()
        print(f"\n현재 사용자-팀 관계 수: {len(user_groups)}")
        for ug in user_groups:
            print(f"  사용자: {ug[0]}, 팀: {ug[1]}")
        
        # 기본 팀이 없으면 생성
        if not teams:
            print("\n=== 기본 팀 생성 ===")
            cursor.execute("""
                INSERT INTO TEAM (group_id, group_name, group_description, created_at, updated_at)
                VALUES (1, 'Default Team', '기본 팀', NOW(), NOW())
            """)
            print("✅ 기본 팀(ID: 1) 생성 완료")
        
        # 팀이 없는 사용자들을 기본 팀에 추가
        if users:
            print("\n=== 사용자를 기본 팀에 추가 ===")
            for user in users:
                user_id = user[0]
                
                # 이미 팀에 속해 있는지 확인
                cursor.execute("SELECT COUNT(*) FROM USER_GROUP WHERE user_id = %s", (user_id,))
                count = cursor.fetchone()[0]
                
                if count == 0:
                    # 기본 팀에 추가
                    cursor.execute("""
                        INSERT IGNORE INTO USER_GROUP (user_id, group_id)
                        VALUES (%s, 1)
                    """, (user_id,))
                    print(f"✅ 사용자 {user_id}를 기본 팀에 추가")
                else:
                    print(f"⚠️ 사용자 {user_id}는 이미 팀에 속해 있음")
        
        connection.commit()
        
        # 최종 상태 확인
        print("\n=== 최종 상태 확인 ===")
        cursor.execute("""
            SELECT u.user_id, u.user_name, t.group_id, t.group_name
            FROM USER u
            JOIN USER_GROUP ug ON u.user_id = ug.user_id
            JOIN TEAM t ON ug.group_id = t.group_id
        """)
        final_state = cursor.fetchall()
        
        print(f"사용자-팀 관계:")
        for state in final_state:
            print(f"  {state[1]} ({state[0]}) → 팀: {state[3]} (ID: {state[2]})")
        
        return True
        
    except mysql.connector.Error as e:
        print(f"❌ 데이터베이스 오류: {e}")
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
    print("사용자 팀 설정 스크립트")
    print("=" * 50)
    
    success = setup_default_team_and_user()
    
    if success:
        print("\n✅ 팀 설정이 완료되었습니다!")
        print("이제 게시글 생성을 다시 시도해보세요.")
    else:
        print("\n❌ 팀 설정 중 오류가 발생했습니다.")
