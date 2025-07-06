#!/usr/bin/env python3
"""
간단한 데이터베이스 확인 스크립트
현재 인플루언서 데이터 상태 확인
"""

import sys
import os
from pathlib import Path

# 백엔드 경로 추가
backend_path = Path(__file__).parent / "backend"
sys.path.append(str(backend_path))

def check_influencer_data():
    try:
        # 환경 설정 로드
        print("🔍 데이터베이스 인플루언서 데이터 확인")
        print("=" * 50)
        
        from app.core.config import settings
        from app.database import test_database_connection
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import create_engine
        
        # 데이터베이스 연결 확인
        if not test_database_connection():
            print("❌ 데이터베이스 연결 실패")
            return
        
        print("✅ 데이터베이스 연결 성공")
        
        # 세션 생성
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            from app.models.influencer import AIInfluencer, ModelMBTI, StylePreset
            
            # 인플루언서 데이터 확인
            total_influencers = db.query(AIInfluencer).count()
            ready_influencers = db.query(AIInfluencer).filter(AIInfluencer.learning_status == 1).count()
            
            print(f"📊 총 인플루언서: {total_influencers}개")
            print(f"📊 사용 가능한 인플루언서: {ready_influencers}개")
            
            if total_influencers > 0:
                print("\n📋 인플루언서 목록:")
                influencers = db.query(AIInfluencer).limit(5).all()
                for inf in influencers:
                    status_text = "사용가능" if inf.learning_status == 1 else "학습중"
                    print(f"  - {inf.influencer_name} (ID: {inf.influencer_id[:8]}..., 상태: {status_text})")
            
            # MBTI 데이터 확인
            mbti_count = db.query(ModelMBTI).count()
            print(f"\n📊 MBTI 데이터: {mbti_count}개")
            
            # 스타일 프리셋 확인
            preset_count = db.query(StylePreset).count()
            print(f"📊 스타일 프리셋: {preset_count}개")
            
            # 권장사항
            print("\n" + "=" * 50)
            print("💡 권장사항:")
            
            if total_influencers == 0:
                print("❌ 인플루언서 데이터가 없습니다.")
                print("   해결책: 샘플 인플루언서 생성 필요")
                print("   방법: 프론트엔드에서 인플루언서 생성 또는 SQL 직접 입력")
                
                print("\n🔧 빠른 해결책 - 샘플 데이터 생성:")
                print("   다음 SQL을 직접 실행하세요:")
                print("""
   INSERT INTO AI_INFLUENCER (
       influencer_id, user_id, team_id, style_preset_id, 
       influencer_name, learning_status, influencer_model_repo, chatbot_option
   ) VALUES (
       UUID(), 'test_user_id', 1, 
       (SELECT style_preset_id FROM PRESET LIMIT 1),
       '테스트 인플루언서', 1, 'test_repo', TRUE
   );
                """)
            
            elif ready_influencers == 0:
                print("⚠️ 사용 가능한 인플루언서가 없습니다.")
                print("   해결책: 기존 인플루언서의 learning_status를 1로 변경")
                print(f"   SQL: UPDATE AI_INFLUENCER SET learning_status = 1 LIMIT 1;")
            
            else:
                print("✅ 데이터가 정상적으로 준비되어 있습니다!")
                print("   프론트엔드에서 API 호출이 정상 작동해야 합니다.")
                
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    check_influencer_data()
