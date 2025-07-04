#!/usr/bin/env python3
"""
데이터베이스 데이터 확인 스크립트
현재 데이터베이스에 필요한 샘플 데이터가 있는지 확인
"""

import sys
import os
from pathlib import Path

# 백엔드 경로 추가
backend_path = Path(__file__).parent / "backend"
sys.path.append(str(backend_path))

def main():
    print("🔍 AIMEX 데이터베이스 데이터 확인")
    print("=" * 50)
    
    try:
        # 1. 환경 설정 로드
        print("1. 환경 설정 로드 중...")
        from app.core.config import settings
        print(f"✅ PROJECT_NAME: {settings.PROJECT_NAME}")
        print(f"✅ DATABASE_URL: {settings.DATABASE_URL[:50]}...")
        
        # 2. 데이터베이스 연결 테스트
        print("\n2. 데이터베이스 연결 테스트...")
        from app.database import get_db, test_database_connection
        
        if not test_database_connection():
            print("❌ 데이터베이스 연결 실패")
            print("MySQL 서버가 실행 중인지 확인하세요.")
            return
        
        print("✅ 데이터베이스 연결 성공")
        
        # 3. 모델 임포트
        print("\n3. 모델 임포트 중...")
        from app.models.influencer import ModelMBTI, StylePreset, AIInfluencer
        from app.models.user import User, Team
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import create_engine
        
        # 4. 세션 생성
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            # 5. 데이터 확인
            print("\n4. 데이터 확인 중...")
            
            # MBTI 데이터 확인
            mbti_count = db.query(ModelMBTI).count()
            print(f"📊 MBTI 데이터: {mbti_count}개")
            
            if mbti_count > 0:
                sample_mbti = db.query(ModelMBTI).first()
                print(f"   샘플: {sample_mbti.mbti_name} - {sample_mbti.mbti_traits[:50]}...")
            
            # StylePreset 데이터 확인
            preset_count = db.query(StylePreset).count()
            print(f"📊 스타일 프리셋: {preset_count}개")
            
            if preset_count > 0:
                sample_preset = db.query(StylePreset).first()
                print(f"   샘플: {sample_preset.style_preset_name}")
            
            # AI 인플루언서 데이터 확인
            influencer_count = db.query(AIInfluencer).count()
            print(f"📊 AI 인플루언서: {influencer_count}개")
            
            if influencer_count > 0:
                sample_influencer = db.query(AIInfluencer).first()
                print(f"   샘플: {sample_influencer.influencer_name} (상태: {sample_influencer.learning_status})")
                
                # 사용 가능한 인플루언서 수
                ready_count = db.query(AIInfluencer).filter(AIInfluencer.learning_status == 1).count()
                print(f"   사용 가능한 인플루언서: {ready_count}개")
            
            # User 데이터 확인
            user_count = db.query(User).count()
            print(f"📊 사용자: {user_count}개")
            
            # Team 데이터 확인  
            team_count = db.query(Team).count()
            print(f"📊 팀: {team_count}개")
            
            print("\n" + "=" * 50)
            print("📋 요약")
            print("=" * 50)
            
            if mbti_count == 0:
                print("❌ MBTI 데이터가 비어있습니다")
                print("   해결방법: python backend/seed_mbti_complete.py 실행")
            
            if preset_count == 0:
                print("❌ 스타일 프리셋 데이터가 비어있습니다")
                print("   해결방법: python create_seed_data.py 실행")
            
            if influencer_count == 0:
                print("❌ AI 인플루언서 데이터가 비어있습니다")
                print("   해결방법: 프론트엔드에서 인플루언서 생성 또는 샘플 데이터 추가")
            
            if team_count == 0:
                print("❌ 팀 데이터가 비어있습니다")
                print("   해결방법: python backend/init_admin_group.py 실행")
            
            if mbti_count > 0 and preset_count > 0 and influencer_count > 0:
                print("✅ 모든 필수 데이터가 준비되었습니다!")
                print("🚀 프론트엔드 테스트를 시작할 수 있습니다.")
            
        finally:
            db.close()
            
    except ImportError as e:
        print(f"❌ 임포트 오류: {e}")
        print("가상환경을 활성화하고 의존성을 설치했는지 확인하세요.")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    main()
