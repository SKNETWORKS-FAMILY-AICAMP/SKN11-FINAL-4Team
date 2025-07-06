#!/usr/bin/env python3
"""
MySQL 상태 확인 스크립트
로컬 MySQL 서버 연결 및 상태 확인
"""

import pymysql
import os
import subprocess
import sys
from pathlib import Path

def check_mysql_service():
    """Windows MySQL 서비스 상태 확인"""
    print("🔍 MySQL 서비스 상태 확인...")
    
    try:
        # MySQL80 서비스 확인
        result = subprocess.run(['sc', 'query', 'MySQL80'], 
                              capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print("✅ MySQL80 서비스가 실행 중입니다")
            print(result.stdout)
            return True
    except Exception:
        pass
    
    try:
        # MySQL 서비스 확인
        result = subprocess.run(['sc', 'query', 'MySQL'], 
                              capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print("✅ MySQL 서비스가 실행 중입니다")
            print(result.stdout)
            return True
    except Exception:
        pass
    
    print("❌ MySQL 서비스를 찾을 수 없습니다")
    return False

def check_mysql_port():
    """MySQL 포트(3306) 확인"""
    print("\n🔌 MySQL 포트(3306) 확인...")
    
    try:
        result = subprocess.run(['netstat', '-an'], 
                              capture_output=True, text=True, shell=True)
        if ':3306' in result.stdout:
            print("✅ 포트 3306이 사용 중입니다")
            # 3306 포트 관련 줄만 출력
            for line in result.stdout.split('\n'):
                if ':3306' in line:
                    print(f"   {line.strip()}")
            return True
        else:
            print("❌ 포트 3306이 사용되고 있지 않습니다")
            return False
    except Exception as e:
        print(f"❌ 포트 확인 실패: {e}")
        return False

def test_mysql_connection(host='localhost', port=3306, user='root', password=''):
    """MySQL 연결 테스트"""
    print(f"\n🔗 MySQL 연결 테스트 ({host}:{port})...")
    
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset='utf8mb4',
            connect_timeout=5
        )
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print(f"✅ MySQL 연결 성공! 버전: {version[0]}")
            
            # 데이터베이스 목록 확인
            cursor.execute("SHOW DATABASES")
            databases = cursor.fetchall()
            print("\n📊 데이터베이스 목록:")
            for db in databases:
                if db[0] == 'AIMEX_MAIN':
                    print(f"   ✅ {db[0]} (AIMEX 데이터베이스 존재)")
                else:
                    print(f"   📁 {db[0]}")
            
        connection.close()
        return True
        
    except pymysql.err.OperationalError as e:
        error_code = e.args[0]
        if error_code == 1045:
            print("❌ 인증 실패: 사용자 이름 또는 비밀번호가 잘못되었습니다")
            return False
        elif error_code == 2003:
            print("❌ 연결 실패: MySQL 서버에 연결할 수 없습니다")
            return False
        else:
            print(f"❌ MySQL 연결 오류: {e}")
            return False
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        return False

def test_different_credentials():
    """다양한 인증 정보로 연결 테스트"""
    print("\n🔑 다양한 인증 정보로 연결 테스트...")
    
    # 일반적인 MySQL 사용자 설정들
    credentials = [
        {'user': 'root', 'password': ''},
        {'user': 'root', 'password': 'root'},
        {'user': 'root', 'password': 'password'},
        {'user': 'root', 'password': '1234'},
        {'user': 'root', 'password': 'mysql'},
        {'user': 'portfoliouser', 'password': 'Ilikeyou123!'},  # 기존 설정
    ]
    
    for cred in credentials:
        print(f"\n🔐 {cred['user']}:{('*' * len(cred['password'])) if cred['password'] else '(비밀번호 없음)'} 로 시도...")
        if test_mysql_connection(user=cred['user'], password=cred['password']):
            print(f"✅ 성공! 올바른 인증 정보: {cred}")
            return cred
    
    print("❌ 모든 인증 정보 실패")
    return None

def check_mysql_installation():
    """MySQL 설치 상태 확인"""
    print("\n💿 MySQL 설치 상태 확인...")
    
    # MySQL 실행 파일 확인
    try:
        result = subprocess.run(['mysql', '--version'], 
                              capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print(f"✅ MySQL 클라이언트: {result.stdout.strip()}")
            return True
    except Exception:
        pass
    
    # 일반적인 설치 경로 확인
    common_paths = [
        r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
        r"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysql.exe",
        r"C:\MySQL\bin\mysql.exe",
        r"C:\xampp\mysql\bin\mysql.exe",
    ]
    
    for path in common_paths:
        if Path(path).exists():
            print(f"✅ MySQL 설치 확인: {path}")
            return True
    
    print("❌ MySQL 설치를 찾을 수 없습니다")
    return False

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🔍 AIMEX MySQL 상태 확인 도구")
    print("=" * 60)
    
    # 1. MySQL 설치 확인
    mysql_installed = check_mysql_installation()
    
    # 2. MySQL 서비스 확인
    service_running = check_mysql_service()
    
    # 3. 포트 확인
    port_open = check_mysql_port()
    
    # 4. 연결 테스트
    if service_running and port_open:
        successful_cred = test_different_credentials()
        
        if successful_cred:
            print("\n🎉 MySQL 연결 성공!")
            print(f"\n📋 권장 DATABASE_URL:")
            password_part = f":{successful_cred['password']}" if successful_cred['password'] else ""
            print(f"mysql+pymysql://{successful_cred['user']}{password_part}@localhost:3306/AIMEX_MAIN")
            
            print(f"\n🔧 backend/.env 파일을 다음과 같이 수정하세요:")
            print(f"DATABASE_URL=mysql+pymysql://{successful_cred['user']}{password_part}@localhost:3306/AIMEX_MAIN")
            
        else:
            print("\n❌ MySQL 연결 실패")
            print("\n🔧 해결 방법:")
            print("1. MySQL 서비스 시작: net start MySQL80")
            print("2. 사용자 권한 확인")
            print("3. 비밀번호 재설정")
    else:
        print("\n❌ MySQL 서비스 또는 포트 문제")
        print("\n🔧 해결 방법:")
        if not mysql_installed:
            print("1. MySQL 8.0+ 설치")
        if not service_running:
            print("2. MySQL 서비스 시작: net start MySQL80")
        if not port_open:
            print("3. 포트 3306 확인")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
