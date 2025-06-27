from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any
from datetime import datetime, timedelta

from app.database import get_db
from app.models.influencer import APICallAggregation, InfluencerAPI, AIInfluencer
from app.models.board import Board
from app.models.user import User
from app.schemas.influencer import APICallAggregation as APICallAggregationSchema
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()


@router.get("/api-calls/", response_model=List[APICallAggregationSchema])
async def get_api_call_analytics(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """API 호출 집계 데이터 조회"""
    # 사용자의 인플루언서들의 API 호출 집계 조회
    aggregations = (
        db.query(APICallAggregation)
        .join(InfluencerAPI, APICallAggregation.api_id == InfluencerAPI.api_id)
        .join(AIInfluencer, InfluencerAPI.influencer_id == AIInfluencer.influencer_id)
        .filter(AIInfluencer.user_id == current_user.user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    return aggregations


@router.get("/api-calls/daily")
async def get_daily_api_calls(
    date: str = Query(..., description="YYYY-MM-DD 형식의 날짜"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """특정 날짜의 API 호출 집계 조회"""
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD",
        )

    # 해당 날짜의 API 호출 집계 조회
    daily_calls = (
        db.query(APICallAggregation)
        .join(InfluencerAPI, APICallAggregation.api_id == InfluencerAPI.api_id)
        .join(AIInfluencer, InfluencerAPI.influencer_id == AIInfluencer.influencer_id)
        .filter(
            AIInfluencer.user_id == current_user.user_id,
            func.date(APICallAggregation.created_at) == target_date,
        )
        .all()
    )

    return {
        "date": date,
        "total_calls": sum(call.daily_call_count for call in daily_calls),
        "calls_by_influencer": [
            {"influencer_id": call.influencer_id, "call_count": call.daily_call_count}
            for call in daily_calls
        ],
    }


@router.get("/boards/stats")
async def get_board_statistics(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """게시글 통계 조회"""
    # 전체 게시글 수
    total_boards = (
        db.query(func.count(Board.board_id))
        .filter(Board.user_id == current_user.user_id)
        .scalar()
    )

    # 상태별 게시글 수
    status_counts = (
        db.query(Board.board_status, func.count(Board.board_id))
        .filter(Board.user_id == current_user.user_id)
        .group_by(Board.board_status)
        .all()
    )

    # 플랫폼별 게시글 수
    platform_counts = (
        db.query(Board.board_platform, func.count(Board.board_id))
        .filter(Board.user_id == current_user.user_id)
        .group_by(Board.board_platform)
        .all()
    )

    return {
        "total_boards": total_boards,
        "status_distribution": {status: count for status, count in status_counts},
        "platform_distribution": {
            platform: count for platform, count in platform_counts
        },
    }


@router.get("/influencers/stats")
async def get_influencer_statistics(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """인플루언서 통계 조회"""
    # 전체 인플루언서 수
    total_influencers = (
        db.query(func.count(AIInfluencer.influencer_id))
        .filter(AIInfluencer.user_id == current_user.user_id)
        .scalar()
    )

    # 학습 상태별 인플루언서 수
    learning_status_counts = (
        db.query(AIInfluencer.learning_status, func.count(AIInfluencer.influencer_id))
        .filter(AIInfluencer.user_id == current_user.user_id)
        .group_by(AIInfluencer.learning_status)
        .all()
    )

    # 챗봇 옵션별 인플루언서 수
    chatbot_counts = (
        db.query(AIInfluencer.chatbot_option, func.count(AIInfluencer.influencer_id))
        .filter(AIInfluencer.user_id == current_user.user_id)
        .group_by(AIInfluencer.chatbot_option)
        .all()
    )

    return {
        "total_influencers": total_influencers,
        "learning_status_distribution": {
            status: count for status, count in learning_status_counts
        },
        "chatbot_distribution": {
            str(has_chatbot): count for has_chatbot, count in chatbot_counts
        },
    }
