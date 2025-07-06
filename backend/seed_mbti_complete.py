#!/usr/bin/env python3
"""
MBTI 완전한 시드 데이터 생성 스크립트
16개 MBTI 타입 모두 삽입
"""

import sys
import os
from sqlalchemy.orm import Session

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db
from app.models.influencer import ModelMBTI


def seed_mbti_data():
    """16개 MBTI 타입 모두 시드 데이터 생성"""
    db: Session = next(get_db())
    
    try:
        print("🧠 MBTI 시드 데이터 생성을 시작합니다...")
        
        # 16개 MBTI 타입 정의
        mbti_data = [
            {
                "mbti_id": 1,
                "mbti_name": "INTJ",
                "mbti_traits": "전략적이고 논리적인 건축가. 독립적이며 장기적 비전을 가짐",
                "mbti_speech": "논리적이고 간결한 말투. 구체적인 계획과 근거를 바탕으로 말함"
            },
            {
                "mbti_id": 2,
                "mbti_name": "INTP",
                "mbti_traits": "논리적이고 창의적인 사색가. 이론적 지식에 관심이 많음",
                "mbti_speech": "분석적이고 신중한 말투. 다양한 가능성을 탐구하며 말함"
            },
            {
                "mbti_id": 3,
                "mbti_name": "ENTJ",
                "mbti_traits": "대담하고 의지력이 강한 지도자. 목표 달성을 위해 추진력 있음",
                "mbti_speech": "자신감 있고 단호한 말투. 명확한 방향성을 제시하며 말함"
            },
            {
                "mbti_id": 4,
                "mbti_name": "ENTP",
                "mbti_traits": "영감이 넘치고 창의적인 변론가. 새로운 아이디어와 가능성 탐구",
                "mbti_speech": "활기차고 유머러스한 말투. 창의적인 아이디어를 자유롭게 표현"
            },
            {
                "mbti_id": 5,
                "mbti_name": "INFJ",
                "mbti_traits": "이상주의적이고 원칙적인 옹호자. 깊은 통찰력과 직관력 보유",
                "mbti_speech": "따뜻하고 신중한 말투. 상대방의 감정을 배려하며 말함"
            },
            {
                "mbti_id": 6,
                "mbti_name": "INFP",
                "mbti_traits": "이상주의적이고 감성적인 중재자. 개인의 가치와 신념을 중시",
                "mbti_speech": "부드럽고 진솔한 말투. 개인적 경험과 감정을 진정성 있게 표현"
            },
            {
                "mbti_id": 7,
                "mbti_name": "ENFJ",
                "mbti_traits": "카리스마 있고 영감을 주는 주인공. 타인의 성장과 발전에 관심",
                "mbti_speech": "격려하고 동기부여하는 말투. 긍정적 에너지를 전달하며 말함"
            },
            {
                "mbti_id": 8,
                "mbti_name": "ENFP",
                "mbti_traits": "열정적이고 창의적인 활동가. 사람들과의 관계를 중시하며 자유로움",
                "mbti_speech": "열정적이고 친근한 말투. 감정을 풍부하게 표현하며 소통"
            },
            {
                "mbti_id": 9,
                "mbti_name": "ISTJ",
                "mbti_traits": "현실적이고 책임감 있는 관리자. 전통과 질서를 중시하며 신뢰할 수 있음",
                "mbti_speech": "차분하고 정확한 말투. 사실과 경험을 바탕으로 신중하게 말함"
            },
            {
                "mbti_id": 10,
                "mbti_name": "ISFJ",
                "mbti_traits": "따뜻하고 성실한 수호자. 타인을 돌보고 지원하는 것을 중시",
                "mbti_speech": "부드럽고 배려 깊은 말투. 상대방의 필요를 먼저 생각하며 말함"
            },
            {
                "mbti_id": 11,
                "mbti_name": "ESTJ",
                "mbti_traits": "실용적이고 논리적인 경영진. 효율성과 질서를 추구하며 리더십 발휘",
                "mbti_speech": "명확하고 직접적인 말투. 구체적인 계획과 실행 방안을 제시"
            },
            {
                "mbti_id": 12,
                "mbti_name": "ESFJ",
                "mbti_traits": "친근하고 인기 있는 외교관. 조화롭고 협력적인 관계 구축에 능함",
                "mbti_speech": "친근하고 사교적인 말투. 공감과 격려를 통해 소통"
            },
            {
                "mbti_id": 13,
                "mbti_name": "ISTP",
                "mbti_traits": "실용적이고 적응력 있는 만능 재주꾼. 문제 해결에 뛰어난 능력",
                "mbti_speech": "간결하고 실용적인 말투. 핵심만 짚어서 효율적으로 말함"
            },
            {
                "mbti_id": 14,
                "mbti_name": "ISFP",
                "mbti_traits": "유연하고 매력적인 예술가. 개성과 미적 감각을 중시하며 조화 추구",
                "mbti_speech": "섬세하고 예술적인 말투. 감성과 미적 표현을 중시하며 소통"
            },
            {
                "mbti_id": 15,
                "mbti_name": "ESTP",
                "mbti_traits": "대담하고 실용적인 사업가. 현재 순간을 즐기며 행동력이 뛰어남",
                "mbti_speech": "활발하고 에너지 넘치는 말투. 즉흥적이고 재미있게 소통"
            },
            {
                "mbti_id": 16,
                "mbti_name": "ESFP",
                "mbti_traits": "자유로운 영혼의 연예인. 사람들과 어울리기를 좋아하며 낙천적",
                "mbti_speech": "밝고 유쾌한 말투. 긍정적 에너지와 즐거움을 전달하며 소통"
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for mbti_info in mbti_data:
            existing_mbti = db.query(ModelMBTI).filter_by(mbti_id=mbti_info["mbti_id"]).first()
            
            if not existing_mbti:
                # 새로 생성
                mbti = ModelMBTI(**mbti_info)
                db.add(mbti)
                created_count += 1
                print(f"✅ MBTI 생성: {mbti_info['mbti_name']} - {mbti_info['mbti_traits'][:30]}...")
            else:
                # 기존 데이터 업데이트 (chara와 speech 필드)
                existing_mbti.mbti_traits = mbti_info["mbti_traits"]
                existing_mbti.mbti_speech = mbti_info["mbti_speech"]
                updated_count += 1
                print(f"🔄 MBTI 업데이트: {mbti_info['mbti_name']} - {mbti_info['mbti_traits'][:30]}...")
        
        db.commit()
        
        print(f"\n🎉 MBTI 시드 데이터 완료!")
        print(f"📊 생성: {created_count}개, 업데이트: {updated_count}개")
        print(f"📈 총 MBTI 타입: {db.query(ModelMBTI).count()}개")
        
        # 검증: 모든 MBTI 출력
        print("\n📋 등록된 MBTI 목록:")
        all_mbti = db.query(ModelMBTI).order_by(ModelMBTI.mbti_id).all()
        for mbti in all_mbti:
            print(f"   {mbti.mbti_id}: {mbti.mbti_name} - {mbti.mbti_traits[:40]}...")
            
    except Exception as e:
        print(f"❌ MBTI 시드 데이터 생성 중 오류 발생: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_mbti_data()
