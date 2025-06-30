#!/usr/bin/env python3
"""
데이터베이스 시드 데이터 생성 스크립트
모든 테이블에 예시 데이터를 삽입합니다.
"""

import sys
import os
import uuid
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy import select

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db
from app.models.user import User, Team, HFTokenManage, SystemLog
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
from app.core.security import get_password_hash


def seed_data():
    """시드 데이터 생성"""
    db: Session = next(get_db())
    
    try:
        print("🌱 시드 데이터 생성을 시작합니다...")
        
        # 1. 사용자 데이터 생성
        users_data = [
            {
                "provider_id": "google_123456789",
                "provider": "google",
                "user_name": "김개발",
                "email": "developer@aimex.com",
            },
            {
                "provider_id": "naver_987654321",
                "provider": "naver",
                "user_name": "이디자인",
                "email": "designer@aimex.com",
            },
            {
                "provider_id": "instagram_555666777",
                "provider": "instagram",
                "user_name": "박마케팅",
                "email": "marketing@aimex.com",
            },
            {
                "provider_id": "google_111222333",
                "provider": "google",
                "user_name": "최기획",
                "email": "planner@aimex.com",
            },
            {
                "provider_id": "naver_444555666",
                "provider": "naver",
                "user_name": "정운영",
                "email": "operator@aimex.com",
            },
        ]
        
        print("👥 사용자 데이터 생성 중...")
        created_users = []
        for user_data in users_data:
            existing_user = db.query(User).filter(User.email == user_data["email"]).first()
            if not existing_user:
                user = User(**user_data)
                db.add(user)
                created_users.append(user)
                print(f"✅ 사용자 생성: {user_data['user_name']} ({user_data['email']})")
            else:
                created_users.append(existing_user)
                print(f"ℹ️ 기존 사용자: {user_data['user_name']} ({user_data['email']})")
        
        db.commit()
        
        # 2. 팀 데이터 생성
        teams = [
            {
                "group_id": 1,
                "group_name": "관리자 팀",
                "group_description": "시스템 관리자 팀",
            },
            {
                "group_id": 2,
                "group_name": "일반 사용자 팀",
                "group_description": "일반 사용자 팀",
            },
            {
                "group_id": 3,
                "group_name": "프리미엄 사용자 팀",
                "group_description": "프리미엄 서비스 이용자 팀",
            },
        ]
        
        print("\n🏢 팀 데이터 생성 중...")
        for team_data in teams:
            existing_team = (
                db.query(Team).filter(Team.group_id == team_data["group_id"]).first()
            )
            if not existing_team:
                db_team = Team(**team_data)
                db.add(db_team)
                print(f"✅ 팀 생성: {team_data['group_name']}")
            else:
                print(f"ℹ️ 기존 팀: {team_data['group_name']}")
        
        db.commit()
        
        # 3. 사용자를 팀에 할당
        print("\n🔗 사용자-팀 관계 설정 중...")
        teams = db.query(Team).all()
        
        for i, user in enumerate(created_users):
            if i < len(teams):
                team = teams[i]
                if user not in team.users:
                    team.users.append(user)
                    print(f"✅ 사용자 {user.user_name}을 팀 {team.group_name}에 추가")
        
        db.commit()
        
        # USER_TEAM 테이블에 명시적으로 데이터 삽입
        print("🔗 USER_TEAM 테이블에 관계 데이터 삽입 중...")
        from app.models.user import user_group
        
        for i, user in enumerate(created_users):
            if i < len(teams):
                team = teams[i]
                
                # 기존 관계 확인
                existing_relation = db.execute(
                    user_group.select().where(
                        user_group.c.user_id == user.user_id,
                        user_group.c.group_id == team.group_id,
                    )
                ).first()
                
                if not existing_relation:
                    # USER_TEAM 테이블에 직접 삽입
                    stmt = user_group.insert().values(
                        user_id=user.user_id, group_id=team.group_id
                    )
                    db.execute(stmt)
                    print(f"✅ USER_TEAM 테이블에 {user.user_name}-{team.group_name} 관계 추가")
                else:
                    print(f"ℹ️ 이미 존재하는 관계: {user.user_name}-{team.group_name}")
        
        db.commit()
        
        # 4. 허깅페이스 토큰 데이터 생성
        hf_tokens_data = [
            {
                "group_id": 1,
                "hf_token_value": "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "hf_token_nickname": "개발용 토큰",
                "hf_user_name": "dev_user",
            },
            {
                "group_id": 2,
                "hf_token_value": "hf_yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
                "hf_token_nickname": "테스트용 토큰",
                "hf_user_name": "test_user",
            },
            {
                "group_id": 3,
                "hf_token_value": "hf_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",
                "hf_token_nickname": "프로덕션용 토큰",
                "hf_user_name": "prod_user",
            },
        ]
        
        print("\n🔑 허깅페이스 토큰 데이터 생성 중...")
        for token_data in hf_tokens_data:
            existing_token = (
                db.query(HFTokenManage)
                .filter(
                    HFTokenManage.group_id == token_data["group_id"],
                    HFTokenManage.hf_token_nickname == token_data["hf_token_nickname"],
                )
                .first()
            )
            if not existing_token:
                hf_token = HFTokenManage(**token_data)
                db.add(hf_token)
                print(f"✅ 토큰 생성: {token_data['hf_token_nickname']}")
            else:
                print(f"ℹ️ 기존 토큰: {token_data['hf_token_nickname']}")
        
        db.commit()
        
        # AI 인플루언서 생성 전에 MBTI, StylePreset 기본 데이터 추가
        if not db.query(ModelMBTI).filter_by(mbti_id=1).first():
            mbti = ModelMBTI(mbti_id=1, mbti_name="INTJ", mbti_traits="전략적, 논리적", mbti_speech="논리적 말투")
            db.add(mbti)
        if not db.query(StylePreset).filter_by(style_preset_id=1).first():
            style = StylePreset(
                style_preset_id=1,
                style_preset_name="기본",
                influencer_type=0,
                influencer_gender=0,
                influencer_age_group=20,
                influencer_hairstyle="단정",
                influencer_style="기본",
                influencer_personality="기본",
                influencer_speech="기본"
            )
            db.add(style)
        db.commit()
        
        # 5. AI 인플루언서 데이터 생성
        ai_influencers_data = [
            {
                "user_id": created_users[0].user_id,
                "group_id": 1,
                "influencer_name": "AI_김개발",
                "influencer_description": "개발 관련 콘텐츠를 다루는 AI 인플루언서",
                "influencer_personality": "전문적이고 논리적인 개발자",
                "influencer_tone": "친근하면서도 전문적인",
                "influencer_age_group": 20,
                "learning_status": 1,
                "chatbot_option": True,
                "voice_option": False,
                "image_option": True,
                "style_preset_id": 1,
                "mbti_id": 1,
                "influencer_model_repo": "https://huggingface.co/models/sample1",
            },
            {
                "user_id": created_users[1].user_id,
                "group_id": 2,
                "influencer_name": "AI_이디자인",
                "influencer_description": "디자인 트렌드와 창작 과정을 공유하는 AI 인플루언서",
                "influencer_personality": "창의적이고 예술적인 디자이너",
                "influencer_tone": "영감을 주는 예술가",
                "influencer_age_group": 20,
                "learning_status": 1,
                "chatbot_option": True,
                "voice_option": True,
                "image_option": True,
                "style_preset_id": 1,
                "mbti_id": 1,
                "influencer_model_repo": "https://huggingface.co/models/sample2",
            },
            {
                "user_id": created_users[2].user_id,
                "group_id": 3,
                "influencer_name": "AI_박마케팅",
                "influencer_description": "마케팅 전략과 비즈니스 인사이트를 제공하는 AI 인플루언서",
                "influencer_personality": "전략적이고 분석적인 마케터",
                "influencer_tone": "신뢰할 수 있는 비즈니스 전문가",
                "influencer_age_group": 30,
                "learning_status": 0,
                "chatbot_option": False,
                "voice_option": True,
                "image_option": False,
                "style_preset_id": 1,
                "mbti_id": 1,
                "influencer_model_repo": "https://huggingface.co/models/sample3",
            },
        ]
        
        print("\n🤖 AI 인플루언서 데이터 생성 중...")
        for influencer_data in ai_influencers_data:
            existing_influencer = (
                db.query(AIInfluencer)
                .filter(AIInfluencer.influencer_name == influencer_data["influencer_name"])
                .first()
            )
            if not existing_influencer:
                ai_influencer = AIInfluencer(**influencer_data)
                db.add(ai_influencer)
                print(f"✅ AI 인플루언서 생성: {influencer_data['influencer_name']}")
            else:
                print(f"ℹ️ 기존 AI 인플루언서: {influencer_data['influencer_name']}")
        
        db.commit()
        
        # AI 인플루언서 생성 후 DB에서 객체를 조회하여 리스트로 저장
        ai_influencers = [
            db.query(AIInfluencer).filter_by(influencer_name="AI_김개발").first(),
            db.query(AIInfluencer).filter_by(influencer_name="AI_이디자인").first(),
            db.query(AIInfluencer).filter_by(influencer_name="AI_박마케팅").first(),
        ]

        boards_data = [
            {
                "user_id": created_users[0].user_id,
                "group_id": 1,
                "influencer_id": ai_influencers[0].influencer_id if ai_influencers[0] else None,
                "board_topic": "개발자 커뮤니티",
                "board_description": "개발 관련 정보와 팁을 공유하는 게시판입니다.",
                "board_platform": 1,  # web
                "board_status": 3,   # active
                "image_url": "https://placehold.co/600x400?text=dev",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            },
            {
                "user_id": created_users[1].user_id,
                "group_id": 2,
                "influencer_id": ai_influencers[1].influencer_id if ai_influencers[1] else None,
                "board_topic": "디자인 갤러리",
                "board_description": "디자인 작품과 아이디어를 공유하는 게시판입니다.",
                "board_platform": 0,  # instagram
                "board_status": 3,   # active
                "image_url": "https://placehold.co/600x400?text=design",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            },
            {
                "user_id": created_users[2].user_id,
                "group_id": 3,
                "influencer_id": ai_influencers[2].influencer_id if ai_influencers[2] else None,
                "board_topic": "마케팅 인사이트",
                "board_description": "마케팅 전략과 트렌드를 분석하는 게시판입니다.",
                "board_platform": 2,  # youtube
                "board_status": 1,   # draft
                "image_url": "https://placehold.co/600x400?text=marketing",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            },
        ]
        
        print("\n📋 게시판 데이터 생성 중...")
        for board_data in boards_data:
            existing_board = (
                db.query(Board)
                .filter(Board.board_topic == board_data["board_topic"])
                .first()
            )
            if not existing_board:
                # BOARD 생성 전 USER_TEAM에 (user_id, group_id) 조합이 있는지 확인/삽입
                existing_relation = db.execute(
                    user_group.select().where(
                        user_group.c.user_id == board_data["user_id"],
                        user_group.c.group_id == board_data["group_id"],
                    )
                ).first()
                
                if not existing_relation:
                    stmt = user_group.insert().values(
                        user_id=board_data["user_id"], group_id=board_data["group_id"]
                    )
                    db.execute(stmt)
                    print(f"✅ USER_TEAM 관계 추가: {board_data['user_id']}-{board_data['group_id']}")
                
                board = Board(**board_data)
                db.add(board)
                print(f"✅ 게시판 생성: {board_data['board_topic']}")
            else:
                print(f"ℹ️ 기존 게시판: {board_data['board_topic']}")
        
        db.commit()
        
        print("\n🎉 시드 데이터 생성이 완료되었습니다!")
        
    except Exception as e:
        print(f"❌ 시드 데이터 생성 중 오류 발생: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
