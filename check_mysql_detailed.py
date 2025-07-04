#!/usr/bin/env python3
"""
MySQL 서비스 및 설치 상태 자세한 확인
"""

import subprocess
import sys
from pathlib import Path

def check_all_mysql_services():
    """모든 MySQL 관련 서비스 확인"""
    print("🔍 모든 MySQL 관련 서비스 확인...")
    
    try:
        # 모든 서비스 중에서 MySQL 관련 찾기
        result = subprocess.run(['sc', 'query', 'state=', 'all'], 
                              capture_output=True, text=True, shell=True)
        
        mysql_services = []
        lines = result.stdout.split('\n')
        
        for i, line in enumerate(lines):
            if 'mysql' in line.lower() or 'MySQL' in line:
                # 서비스 이름 추출
                if 'SERVICE_NAME:' in line:
                    service_name = line.split('SERVICE_NAME:')[1].strip()
                    mysql_services.append(service_name)
                    print(f"   📋 발견된 MySQL 서비스: {service_name}")
        
        if not mysql_services:
            print("   ❌ MySQL 관련 서비스를 찾을 수 없습니다")
        
        return mysql_services
        
    except Exception as e:
        print(f"   ❌ 서비스 확인 실패: {e}")
        return []

def check_mysql_installations():
    """일반적인 MySQL 설치 경로 확인"""
    print("\n💿 MySQL 설치 경로 확인...")
    
    installation_paths = [
        r"C:\Program Files\MySQL",
        r"C:\Program Files (x86)\MySQL", 
        r"C:\MySQL",
        r"C:\xampp\mysql",
        r"C:\wamp\bin\mysql",
        r"C:\mamp\bin\mysql",
        r"C:\laragon\bin\mysql"
    ]
    
    found_installations = []
    
    for path in installation_paths:
        if Path(path).exists():
            print(f"   ✅ 설치 발견: {path}")
            found_installations.append(path)
            
            # 하위 버전 폴더 확인
            try:
                for item in Path(path).iterdir():
                    if item.is_dir() and ('server' in item.name.lower() or 'mysql' in item.name.lower()):
                        print(f"      📁 {item.name}")
                        
                        # bin 폴더 확인
                        bin_path = item / "bin"
                        if bin_path.exists():
                            mysql_exe = bin_path / "mysql.exe"
                            mysqld_exe = bin_path / "mysqld.exe"
                            if mysql_exe.exists():
                                print(f"         ✅ MySQL 클라이언트: {mysql_exe}")
                            if mysqld_exe.exists():
                                print(f"         ✅ MySQL 서버: {mysqld_exe}")
            except Exception as e:
                print(f"      ❌ 폴더 탐색 실패: {e}")
    
    if not found_installations:
        print("   ❌ MySQL 설치를 찾을 수 없습니다")
    
    return found_installations

def check_running_processes():
    """실행 중인 MySQL 프로세스 확인"""
    print("\n🔄 실행 중인 MySQL 프로세스 확인...")
    
    try:
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq mysqld.exe'], 
                              capture_output=True, text=True, shell=True)
        
        if 'mysqld.exe' in result.stdout:
            print("   ✅ MySQL 서버 프로세스가 실행 중입니다")
            print(result.stdout)
            return True
        else:
            print("   ❌ MySQL 서버 프로세스가 실행되고 있지 않습니다")
            return False
            
    except Exception as e:
        print(f"   ❌ 프로세스 확인 실패: {e}")
        return False

def check_port_3306():
    """포트 3306 사용 상태 자세히 확인"""
    print("\n🔌 포트 3306 상세 확인...")
    
    try:
        result = subprocess.run(['netstat', '-ano'], 
                              capture_output=True, text=True, shell=True)
        
        port_3306_found = False
        for line in result.stdout.split('\n'):
            if ':3306' in line:
                port_3306_found = True
                print(f"   📋 {line.strip()}")
        
        if not port_3306_found:
            print("   ❌ 포트 3306을 사용하는 프로세스가 없습니다")
            
        return port_3306_found
        
    except Exception as e:
        print(f"   ❌ 포트 확인 실패: {e}")
        return False

def suggest_solutions():
    """해결 방안 제시"""
    print("\n" + "="*60)
    print("🔧 해결 방안")
    print("="*60)
    
    print("\n📋 협업 프로젝트에서의 권장 해결책:")
    print("1. 🔄 외부 MySQL 서버 연결 복구")
    print("   - 네트워크 연결 확인")
    print("   - VPN 연결 확인") 
    print("   - 팀원에게 서버 상태 문의")
    
    print("\n2. 🏠 로컬 개발 환경 구축 (권장)")
    print("   - .env.local 파일 생성 (개인용 설정)")
    print("   - 로컬 MySQL 설치 및 설정")
    print("   - 개인 개발용 데이터베이스 구성")
    
    print("\n3. 🐳 Docker MySQL 사용")
    print("   - Docker Desktop 설치")
    print("   - MySQL 컨테이너 실행")
    print("   - 팀 환경과 독립적인 개발 환경")

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🔍 MySQL 설치 및 서비스 상태 자세한 확인")
    print("=" * 60)
    
    # 1. MySQL 서비스 확인
    mysql_services = check_all_mysql_services()
    
    # 2. MySQL 설치 경로 확인
    installations = check_mysql_installations()
    
    # 3. 실행 중인 프로세스 확인
    process_running = check_running_processes()
    
    # 4. 포트 확인
    port_in_use = check_port_3306()
    
    # 5. 결과 요약
    print("\n" + "="*60)
    print("📊 상태 요약")
    print("="*60)
    print(f"MySQL 서비스: {len(mysql_services)}개 발견")
    print(f"MySQL 설치: {len(installations)}개 발견")
    print(f"MySQL 프로세스 실행: {'✅ Yes' if process_running else '❌ No'}")
    print(f"포트 3306 사용: {'✅ Yes' if port_in_use else '❌ No'}")
    
    # 6. 해결 방안 제시
    suggest_solutions()

if __name__ == "__main__":
    main()
