#!/usr/bin/env python3
"""
데이터베이스 시드 데이터 생성 스크립트
모든 테이블에 예시 데이터를 삽입합니다.
"""

import uuid
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.database import SessionLocal, engine
from app.models.user import User, Group, HFTokenManage, SystemLog
from app.models.influencer import (
    ModelMBTI,
    StylePreset,
    AIInfluencer,
    BatchKey,
    ChatMessage,
    InfluencerAPI,
    APICallAggregation,
)
from app.models.board import Board


def create_sample_data():
    """샘플 데이터 생성 및 삽입"""
    db = SessionLocal()

    try:
        print("🌱 데이터베이스 시드 데이터 생성 시작...")

        # 1. MBTI 데이터 생성
        print("📝 MBTI 데이터 생성 중...")
        mbti_data = [
            {
                "mbti_id": 1,
                "mbti_name": "INTJ",
                "mbti_chara": "전략적 사고, 독립적, 분석적",
                "mbti_speech": "논리적이고 분석적인 말투를 사용하며, 명확하고 간결한 표현을 선호합니다.",
            },
            {
                "mbti_id": 2,
                "mbti_name": "ENFP",
                "mbti_chara": "열정적, 창의적, 공감능력 뛰어남",
                "mbti_speech": "에너지 넘치고 열정적인 말투를 사용하며, 감정적이고 표현력이 풍부합니다.",
            },
            {
                "mbti_id": 3,
                "mbti_name": "ISTP",
                "mbti_chara": "실용적, 문제해결 능력 뛰어남, 침착함",
                "mbti_speech": "실용적이고 간결한 말투를 사용하며, 구체적이고 명확한 표현을 선호합니다.",
            },
            {
                "mbti_id": 4,
                "mbti_name": "ESFJ",
                "mbti_chara": "사교적, 책임감 강함, 협력적",
                "mbti_speech": "따뜻하고 친근한 말투를 사용하며, 다른 사람을 배려하는 표현을 자주 사용합니다.",
            },
        ]

        for mbti in mbti_data:
            existing_mbti = (
                db.query(ModelMBTI).filter(ModelMBTI.mbti_id == mbti["mbti_id"]).first()
            )
            if not existing_mbti:
                db_mbti = ModelMBTI(**mbti)
                db.add(db_mbti)

        # 2. 스타일 프리셋 데이터 생성
        print("🎨 스타일 프리셋 데이터 생성 중...")
        style_presets = [
            {
                "style_preset_name": "힙한 스트리트 패션",
                "influencer_type": 1,
                "influencer_gender": 0,
                "influencer_age_group": 20,
                "influencer_hairstyle": "레이어드 컷",
                "influencer_style": "힙하고 스트리트한 패션",
                "influencer_personality": "자유분방하고 트렌디한 성격",
                "influencer_speech": "젊고 힙한 말투, 영어 단어를 자주 섞어 사용",
            },
            {
                "style_preset_name": "청순한 여성",
                "influencer_type": 2,
                "influencer_gender": 1,
                "influencer_age_group": 20,
                "influencer_hairstyle": "긴 생머리",
                "influencer_style": "청순하고 깔끔한 스타일",
                "influencer_personality": "차분하고 예의 바른 성격",
                "influencer_speech": "부드럽고 예의 바른 말투, 존댓말 사용",
            },
            {
                "style_preset_name": "비즈니스맨",
                "influencer_type": 3,
                "influencer_gender": 0,
                "influencer_age_group": 30,
                "influencer_hairstyle": "단정한 단발",
                "influencer_style": "정장과 비즈니스 캐주얼",
                "influencer_personality": "신뢰감 있고 전문적인 성격",
                "influencer_speech": "정중하고 전문적인 말투, 비즈니스 용어 사용",
            },
        ]

        for style in style_presets:
            existing_style = (
                db.query(StylePreset)
                .filter(StylePreset.style_preset_name == style["style_preset_name"])
                .first()
            )
            if not existing_style:
                db_style = StylePreset(**style)
                db.add(db_style)

        # 3. 그룹 데이터 생성
        print("👥 그룹 데이터 생성 중...")
        groups = [
            {
                "group_id": 1,
                "group_name": "관리자 그룹",
                "group_description": "시스템 관리자 그룹",
            },
            {
                "group_id": 2,
                "group_name": "일반 사용자 그룹",
                "group_description": "일반 사용자 그룹",
            },
            {
                "group_id": 3,
                "group_name": "프리미엄 사용자 그룹",
                "group_description": "프리미엄 서비스 이용자 그룹",
            },
        ]

        for group_data in groups:
            existing_group = (
                db.query(Group).filter(Group.group_id == group_data["group_id"]).first()
            )
            if not existing_group:
                db_group = Group(**group_data)
                db.add(db_group)

        # 4. 사용자 데이터 생성
        print("👤 사용자 데이터 생성 중...")
        users = [
            {
                "provider_id": "google_123456",
                "provider": "google",
                "user_name": "김철수",
                "email": "kim@example.com",
            },
            {
                "provider_id": "kakao_789012",
                "provider": "kakao",
                "user_name": "이영희",
                "email": "lee@example.com",
            },
            {
                "provider_id": "naver_345678",
                "provider": "naver",
                "user_name": "박민수",
                "email": "park@example.com",
            },
        ]

        db_users = []
        for user_data in users:
            existing_user = (
                db.query(User).filter(User.email == user_data["email"]).first()
            )
            if not existing_user:
                db_user = User(**user_data)
                db.add(db_user)
                db_users.append(db_user)
                print(
                    f"✅ 새 사용자 생성: {user_data['user_name']} ({user_data['email']})"
                )
            else:
                db_users.append(existing_user)
                print(
                    f"ℹ️ 기존 사용자 사용: {existing_user.user_name} ({existing_user.email})"
                )

        # 사용자 생성 확인
        print(f"📊 총 {len(db_users)}명의 사용자가 준비되었습니다.")
        for i, user in enumerate(db_users):
            print(f"  {i+1}. {user.user_name} (ID: {user.user_id})")

        # 사용자-그룹 관계 설정
        print("🔗 사용자-그룹 관계 설정 중...")
        groups = db.query(Group).all()
        for i, user in enumerate(db_users):
            if i < len(groups):
                group = groups[i]
                if user not in group.users:
                    group.users.append(user)
                    print(
                        f"✅ 사용자 {user.user_name}을 그룹 {group.group_name}에 추가"
                    )

        # USER_GROUP 테이블에 명시적으로 데이터 삽입
        print("🔗 USER_GROUP 테이블에 관계 데이터 삽입 중...")
        from app.models.user import user_group

        for i, user in enumerate(db_users):
            if i < len(groups):
                group = groups[i]
                # 중복 체크
                existing_relation = db.execute(
                    user_group.select().where(
                        and_(
                            user_group.c.user_id == user.user_id,
                            user_group.c.group_id == group.group_id,
                        )
                    )
                ).first()
                if not existing_relation:
                    # USER_GROUP 테이블에 직접 삽입
                    stmt = user_group.insert().values(
                        user_id=user.user_id, group_id=group.group_id
                    )
                    db.execute(stmt)
                    print(
                        f"✅ USER_GROUP 테이블에 {user.user_name}-{group.group_name} 관계 추가"
                    )
                else:
                    print(f"ℹ️ 이미 존재하는 관계: {user.user_name}-{group.group_name}")

        db.commit()  # 중간 커밋

        # 5. HF 토큰 관리 데이터 생성
        print("🔑 HF 토큰 데이터 생성 중...")
        hf_tokens = [
            {
                "hf_manage_id": str(uuid.uuid4()),
                "group_id": 1,
                "hf_token_value": "hf_encrypted_token_123",
                "hf_token_nickname": "관리자 토큰",
                "hf_user_name": "admin_user",
            },
            {
                "hf_manage_id": str(uuid.uuid4()),
                "group_id": 2,
                "hf_token_value": "hf_encrypted_token_456",
                "hf_token_nickname": "일반 사용자 토큰",
                "hf_user_name": "normal_user",
            },
        ]

        for token_data in hf_tokens:
            existing_token = (
                db.query(HFTokenManage)
                .filter(HFTokenManage.hf_manage_id == token_data["hf_manage_id"])
                .first()
            )
            if not existing_token:
                db_token = HFTokenManage(**token_data)
                db.add(db_token)

        # 6. AI 인플루언서 데이터 생성
        print("🤖 AI 인플루언서 데이터 생성 중...")

        # 스타일 프리셋 ID를 가져오기
        style_presets_db = db.query(StylePreset).all()
        preset_map = {}
        for preset in style_presets_db:
            preset_map[str(preset.style_preset_name)] = str(preset.style_preset_id)

        # 사용자 ID를 가져오기
        users_db = db.query(User).all()
        user_emails = ["kim@example.com", "lee@example.com", "park@example.com"]
        user_map = {user.email: user.user_id for user in users_db}

        # 사용자 수 확인
        if len(db_users) < 3:
            print(f"⚠️ 경고: 사용자가 {len(db_users)}명만 있습니다. 3명이 필요합니다.")
            return

        ai_influencers = [
            {
                "influencer_id": "16bbe9a9-cbe4-4437-adb1-86de1bfd0807",
                "user_id": db_users[0].user_id,
                "group_id": 1,
                "style_preset_id": (
                    preset_map["힙한 스트리트 패션"]
                    if "힙한 스트리트 패션" in preset_map
                    else None
                ),
                "mbti_id": 1,
                "influencer_name": "힙한스트리터",
                "image_url": "https://example.com/images/hip_streeter.jpg",
                "influencer_data_url": "https://example.com/data/hip_streeter_dataset",
                "learning_status": 1,
                "influencer_model_repo": "https://huggingface.co/models/hip_streeter",
                "chatbot_option": True,
            },
            {
                "influencer_id": "4a1ffb13-06b8-4a2c-ae91-cb0319e40bd2",
                "user_id": db_users[1].user_id,
                "group_id": 2,
                "style_preset_id": (
                    preset_map["청순한 여성"] if "청순한 여성" in preset_map else None
                ),
                "mbti_id": 2,
                "influencer_name": "청순여신",
                "image_url": "https://example.com/images/pure_goddess.jpg",
                "influencer_data_url": "https://example.com/data/pure_goddess_dataset",
                "learning_status": 1,
                "influencer_model_repo": "https://huggingface.co/models/pure_goddess",
                "chatbot_option": True,
            },
            {
                "influencer_id": "b1f435e6-50ce-4aa4-8611-ba7cb0724b36",
                "user_id": db_users[2].user_id,
                "group_id": 3,
                "style_preset_id": (
                    preset_map["비즈니스맨"] if "비즈니스맨" in preset_map else None
                ),
                "mbti_id": 3,
                "influencer_name": "비즈니스맨",
                "image_url": "https://example.com/images/business_man.jpg",
                "influencer_data_url": "https://example.com/data/business_man_dataset",
                "learning_status": 0,
                "influencer_model_repo": "https://huggingface.co/models/business_man",
                "chatbot_option": False,
            },
        ]

        # AI 인플루언서 생성 전 사용자 ID 확인
        print("🔍 AI 인플루언서 생성 전 사용자 ID 확인:")
        for i, influencer_data in enumerate(ai_influencers):
            print(
                f"  {i+1}. {influencer_data['influencer_name']}: user_id = {influencer_data['user_id']}"
            )

        db_influencers = []
        for influencer_data in ai_influencers:
            existing_influencer = (
                db.query(AIInfluencer)
                .filter(
                    AIInfluencer.influencer_name == influencer_data["influencer_name"]
                )
                .first()
            )
            if not existing_influencer:
                # style_preset_id가 None인 경우 처리
                if influencer_data["style_preset_id"] is None:
                    print(
                        f"⚠️ 스타일 프리셋을 찾을 수 없습니다: {influencer_data['influencer_name']}"
                    )
                    continue

                db_influencer = AIInfluencer(**influencer_data)
                db.add(db_influencer)
                db_influencers.append(db_influencer)
                print(f"✅ AI 인플루언서 생성: {influencer_data['influencer_name']}")
            else:
                print(
                    f"ℹ️ 이미 존재하는 AI 인플루언서: {influencer_data['influencer_name']}"
                )
                db_influencers.append(existing_influencer)

        # 7. 배치키 데이터 생성
        print("🔐 배치키 데이터 생성 중...")
        for influencer in db_influencers:
            batch_key_data = {
                "batch_key_id": str(uuid.uuid4()),
                "influencer_id": influencer.influencer_id,
                "batch_key": f"batch_key_{influencer.influencer_name}_{uuid.uuid4().hex[:8]}",
            }
            existing_batch_key = (
                db.query(BatchKey)
                .filter(BatchKey.influencer_id == influencer.influencer_id)
                .first()
            )
            if not existing_batch_key:
                db_batch_key = BatchKey(**batch_key_data)
                db.add(db_batch_key)

        # 8. 채팅 메시지 데이터 생성
        print("💬 채팅 메시지 데이터 생성 중...")
        for influencer in db_influencers:
            chat_data = {
                "influencer_id": influencer.influencer_id,
                "message_content": json.dumps(
                    {
                        "messages": [
                            {"role": "user", "content": "안녕하세요!"},
                            {
                                "role": "assistant",
                                "content": f"안녕하세요! 저는 {influencer.influencer_name}입니다.",
                            },
                        ]
                    }
                ),
                "created_at": datetime.now(),
                "end_at": datetime.now() + timedelta(minutes=30),
            }
            db_chat = ChatMessage(**chat_data)
            db.add(db_chat)

        # 9. 인플루언서 API 데이터 생성
        print("🔌 인플루언서 API 데이터 생성 중...")
        for influencer in db_influencers:
            api_data = {
                "api_id": str(uuid.uuid4()),
                "influencer_id": influencer.influencer_id,
                "api_value": f"api_key_{influencer.influencer_name}_{uuid.uuid4().hex[:16]}",
            }
            existing_api = (
                db.query(InfluencerAPI)
                .filter(InfluencerAPI.influencer_id == influencer.influencer_id)
                .first()
            )
            if not existing_api:
                db_api = InfluencerAPI(**api_data)
                db.add(db_api)

        # 10. API 호출 집계 데이터 생성
        print("📊 API 호출 집계 데이터 생성 중...")
        apis = db.query(InfluencerAPI).all()
        for api in apis:
            aggregation_data = {
                "api_call_id": str(uuid.uuid4()),
                "api_id": api.api_id,
                "influencer_id": api.influencer_id,
                "daily_call_count": 150,
            }
            existing_aggregation = (
                db.query(APICallAggregation)
                .filter(APICallAggregation.api_id == api.api_id)
                .first()
            )
            if not existing_aggregation:
                db_aggregation = APICallAggregation(**aggregation_data)
                db.add(db_aggregation)

        # 11. 게시글 데이터 생성
        print("📝 게시글 데이터 생성 중...")
        platforms = [0, 1, 2]  # 0:인스타그램, 1:블로그, 2:페이스북
        statuses = [0, 1, 2, 3]  # 0:최초생성, 1:임시저장, 2:예약, 3:발행됨

        for i, influencer in enumerate(db_influencers):
            user_id = influencer.user_id
            group_id = influencer.group_id
            # BOARD 생성 전 USER_GROUP에 (user_id, group_id) 조합이 있는지 확인/삽입
            existing_relation = db.execute(
                user_group.select().where(
                    and_(
                        user_group.c.user_id == user_id,
                        user_group.c.group_id == group_id,
                    )
                )
            ).first()
            if not existing_relation:
                db.execute(
                    user_group.insert().values(user_id=user_id, group_id=group_id)
                )
                print(f"✅ BOARD용 USER_GROUP 추가: {user_id} - {group_id}")

            now = datetime.now()
            board_data = {
                "board_id": str(uuid.uuid4()),
                "influencer_id": influencer.influencer_id,
                "user_id": user_id,
                "group_id": group_id,
                "board_topic": f"{influencer.influencer_name}의 일상",
                "board_description": f"{influencer.influencer_name}의 일상과 팁을 공유합니다.",
                "board_platform": platforms[i % len(platforms)],
                "board_hash_tag": json.dumps(["일상", "팁", "라이프스타일"]),
                "board_status": statuses[i % len(statuses)],
                "image_url": f"https://example.com/thumbnails/{influencer.influencer_name}_thumb.jpg",
                "reservation_at": (
                    datetime.now() + timedelta(days=1) if i % 2 == 0 else None
                ),
                "pulished_at": datetime.now() if i % 3 == 0 else None,
                "created_at": now,
                "updated_at": now,
            }
            db_board = Board(**board_data)
            db.add(db_board)

        # 12. 시스템 로그 데이터 생성
        print("📋 시스템 로그 데이터 생성 중...")
        log_types = [0, 1, 2]  # 0: API요청, 1: 시스템오류, 2: 인증관련
        for user in db_users:
            for i in range(3):
                log_data = {
                    "log_id": str(uuid.uuid4()),
                    "user_id": user.user_id,
                    "log_type": log_types[i],
                    "log_content": json.dumps(
                        {
                            "action": f"사용자 {user.user_name}의 {i+1}번째 활동",
                            "timestamp": datetime.now().isoformat(),
                            "details": f"상세 로그 내용 {i+1}",
                        }
                    ),
                    "created_at": datetime.now(),
                }
                db_log = SystemLog(**log_data)
                db.add(db_log)

        # 데이터베이스에 커밋
        db.commit()
        print("✅ 모든 시드 데이터가 성공적으로 생성되었습니다!")

        # 생성된 데이터 통계 출력
        print("\n📊 생성된 데이터 통계:")
        print(f"- MBTI: {db.query(ModelMBTI).count()}개")
        print(f"- 스타일 프리셋: {db.query(StylePreset).count()}개")
        print(f"- 그룹: {db.query(Group).count()}개")
        print(f"- 사용자: {db.query(User).count()}개")
        print(f"- HF 토큰: {db.query(HFTokenManage).count()}개")
        print(f"- AI 인플루언서: {db.query(AIInfluencer).count()}개")
        print(f"- 배치키: {db.query(BatchKey).count()}개")
        print(f"- 채팅 메시지: {db.query(ChatMessage).count()}개")
        print(f"- 인플루언서 API: {db.query(InfluencerAPI).count()}개")
        print(f"- API 호출 집계: {db.query(APICallAggregation).count()}개")
        print(f"- 게시글: {db.query(Board).count()}개")
        print(f"- 시스템 로그: {db.query(SystemLog).count()}개")

    except Exception as e:
        db.rollback()
        print(f"❌ 데이터 생성 중 오류 발생: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_sample_data()
