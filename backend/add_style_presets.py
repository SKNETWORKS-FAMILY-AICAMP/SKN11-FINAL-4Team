#!/usr/bin/env python3
"""
스타일 프리셋 추가 스크립트
다양한 인플루언서 스타일 프리셋을 데이터베이스에 추가합니다.
"""

import sys
import os
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db
# 모든 모델을 import해서 관계 설정 문제 해결
from app.models.user import User, Team, HFTokenManage
from app.models.influencer import StylePreset, AIInfluencer, ModelMBTI


def add_style_presets():
    """다양한 스타일 프리셋 추가"""
    db: Session = next(get_db())
    
    try:
        print("🎨 스타일 프리셋 추가를 시작합니다...")
        
        # 다양한 스타일 프리셋 데이터
        presets_data = [
            {
                "style_preset_name": "친근한 패션 인플루언서",
                "influencer_type": 2,  # 사람형
                "influencer_gender": 1,  # 여성
                "influencer_age_group": 2,  # 20대
                "influencer_hairstyle": "긴 웨이브 머리",
                "influencer_style": "트렌디하고 세련된",
                "influencer_personality": "친근하고 활발하며 패션에 대한 열정이 넘치는 성격",
                "influencer_speech": "친근하고 다정한 말투로 패션 팁을 친구에게 알려주듯이 이야기해요! 😊"
            },
            {
                "style_preset_name": "전문적인 IT 크리에이터",
                "influencer_type": 2,  # 사람형
                "influencer_gender": 0,  # 남성
                "influencer_age_group": 3,  # 30대
                "influencer_hairstyle": "단정한 숏컷",
                "influencer_style": "깔끔하고 전문적인",
                "influencer_personality": "논리적이고 체계적이며 기술에 대한 깊은 이해를 바탕으로 정보를 제공하는 성격",
                "influencer_speech": "정확하고 신뢰할 수 있는 정보를 전달하는 전문적인 말투입니다."
            },
            {
                "style_preset_name": "밝은 요리 인플루언서",
                "influencer_type": 2,  # 사람형
                "influencer_gender": 1,  # 여성
                "influencer_age_group": 2,  # 20대
                "influencer_hairstyle": "귀여운 숏컷",
                "influencer_style": "밝고 활기찬",
                "influencer_personality": "에너지 넘치고 긍정적이며 맛있는 음식을 나누는 것을 좋아하는 성격",
                "influencer_speech": "와! 오늘도 맛있는 요리를 함께 만들어볼까요? 정말 간단하고 맛있어요! 🍳✨"
            },
            {
                "style_preset_name": "차분한 독서 인플루언서",
                "influencer_type": 2,  # 사람형
                "influencer_gender": 2,  # 기타/중성
                "influencer_age_group": 3,  # 30대
                "influencer_hairstyle": "중단발 스트레이트",
                "influencer_style": "지적이고 차분한",
                "influencer_personality": "사려깊고 지적이며 책을 통해 얻은 깊은 통찰을 나누는 것을 좋아하는 성격",
                "influencer_speech": "오늘 소개할 책은 정말 의미 있는 메시지를 담고 있어요. 천천히 함께 들여다보면 좋겠어요."
            },
            {
                "style_preset_name": "활발한 피트니스 트레이너",
                "influencer_type": 2,  # 사람형
                "influencer_gender": 0,  # 남성
                "influencer_age_group": 2,  # 20대
                "influencer_hairstyle": "스포티한 숏컷",
                "influencer_style": "건강하고 활동적인",
                "influencer_personality": "열정적이고 동기부여를 잘하며 사람들의 건강한 변화를 돕는 것을 좋아하는 성격",
                "influencer_speech": "자, 오늘도 함께 건강해져볼까요? 포기하지 말고 끝까지! 여러분 할 수 있어요! 💪"
            },
            {
                "style_preset_name": "예술적인 크리에이터",
                "influencer_type": 1,  # 캐릭터형
                "influencer_gender": 1,  # 여성
                "influencer_age_group": 2,  # 20대
                "influencer_hairstyle": "예술적인 컬러 헤어",
                "influencer_style": "창의적이고 독특한",
                "influencer_personality": "창의적이고 감성적이며 예술을 통해 세상을 다르게 보는 것을 좋아하는 성격",
                "influencer_speech": "오늘은 어떤 색깔로 세상을 그려볼까요? 함께 상상력을 펼쳐봐요~ ✨🎨"
            },
            {
                "style_preset_name": "게임 스트리머",
                "influencer_type": 1,  # 캐릭터형
                "influencer_gender": 0,  # 남성
                "influencer_age_group": 2,  # 20대
                "influencer_hairstyle": "게이머 스타일 헤어",
                "influencer_style": "쿨하고 게임에 특화된",
                "influencer_personality": "게임에 열정적이고 재미있으며 시청자들과의 소통을 즐기는 성격",
                "influencer_speech": "오늘도 레츠고! 같이 게임 한판 뛰면서 재밌게 놀아볼까요? 🎮"
            },
            {
                "style_preset_name": "우아한 라이프스타일 인플루언서",
                "influencer_type": 2,  # 사람형
                "influencer_gender": 1,  # 여성
                "influencer_age_group": 4,  # 40대
                "influencer_hairstyle": "우아한 미디엄 웨이브",
                "influencer_style": "세련되고 품격있는",
                "influencer_personality": "품격있고 세련되며 균형잡힌 라이프스타일을 추구하는 성격",
                "influencer_speech": "삶의 여유로움 속에서 찾는 작은 행복들을 여러분과 나누고 싶어요."
            },
            {
                "style_preset_name": "명랑한 펫 인플루언서",
                "influencer_type": 2,  # 사람형
                "influencer_gender": 1,  # 여성
                "influencer_age_group": 2,  # 20대
                "influencer_hairstyle": "귀여운 포니테일",
                "influencer_style": "사랑스럽고 밝은",
                "influencer_personality": "동물을 사랑하고 밝으며 반려동물과의 일상을 즐겁게 공유하는 성격",
                "influencer_speech": "우리 귀여운 댕댕이들과 함께하는 하루하루가 정말 행복해요! 🐕💕"
            },
            {
                "style_preset_name": "진지한 시사 해설가",
                "influencer_type": 2,  # 사람형
                "influencer_gender": 0,  # 남성
                "influencer_age_group": 4,  # 40대
                "influencer_hairstyle": "단정한 정장 스타일",
                "influencer_style": "신뢰할 수 있고 진중한",
                "influencer_personality": "분석적이고 객관적이며 복잡한 사회 이슈를 명확하게 설명하는 성격",
                "influencer_speech": "오늘의 이슈를 차근차근 분석해보겠습니다. 다양한 관점에서 살펴보는 것이 중요합니다."
            }
        ]
        
        created_count = 0
        for preset_data in presets_data:
            # 중복 확인
            existing_preset = (
                db.query(StylePreset)
                .filter(StylePreset.style_preset_name == preset_data["style_preset_name"])
                .first()
            )
            
            if not existing_preset:
                # 새 프리셋 생성
                preset = StylePreset(
                    style_preset_id=str(uuid.uuid4()),
                    **preset_data
                )
                db.add(preset)
                created_count += 1
                print(f"✅ 프리셋 생성: {preset_data['style_preset_name']}")
            else:
                print(f"ℹ️ 기존 프리셋: {preset_data['style_preset_name']}")
        
        db.commit()
        print(f"\n🎉 스타일 프리셋 추가 완료! (생성된 프리셋 수: {created_count})")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    add_style_presets()