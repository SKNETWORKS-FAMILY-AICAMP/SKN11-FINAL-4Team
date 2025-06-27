from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
import uuid
from sqlalchemy import update

from app.database import get_db
from app.models.board import Board
from app.models.user import User
from app.schemas.board import (
    BoardCreate,
    BoardUpdate,
    Board as BoardSchema,
    BoardWithInfluencer,
)
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()


@router.get("/", response_model=List[BoardSchema])
async def get_boards(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user),  # 임시로 주석 처리
):
    """게시글 목록 조회 (임시로 인증 없이 접근 가능)"""
    boards = (
        db.query(Board)
        # .filter(Board.user_id == current_user.user_id)  # 임시로 주석 처리
        .offset(skip)
        .limit(limit)
        .all()
    )
    return boards


@router.get("/{board_id}", response_model=BoardWithInfluencer)
async def get_board(
    board_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """특정 게시글 조회"""
    board = (
        db.query(Board)
        .filter(Board.board_id == board_id, Board.user_id == current_user.user_id)
        .first()
    )

    if board is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Board not found"
        )
    return board


@router.post("/", response_model=BoardSchema)
async def create_board(
    board_data: BoardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """새 게시글 생성"""
    board = Board(
        board_id=str(uuid.uuid4()), user_id=current_user.user_id, **board_data.dict()
    )

    db.add(board)
    db.commit()
    db.refresh(board)

    return board


@router.put("/{board_id}", response_model=BoardSchema)
async def update_board(
    board_id: str,
    board_update: BoardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """게시글 정보 수정"""
    board = (
        db.query(Board)
        .filter(Board.board_id == board_id, Board.user_id == current_user.user_id)
        .first()
    )

    if board is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Board not found"
        )

    # 업데이트할 필드들
    update_data = board_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(board, field, value)

    db.commit()
    db.refresh(board)
    return board


@router.delete("/{board_id}")
async def delete_board(
    board_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """게시글 삭제"""
    board = (
        db.query(Board)
        .filter(Board.board_id == board_id, Board.user_id == current_user.user_id)
        .first()
    )

    if board is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Board not found"
        )

    db.delete(board)
    db.commit()

    return {"message": "Board deleted successfully"}


@router.post("/{board_id}/publish")
async def publish_board(
    board_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """게시글 발행"""
    board = (
        db.query(Board)
        .filter(Board.board_id == board_id, Board.user_id == current_user.user_id)
        .first()
    )

    if board is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Board not found"
        )

    # 게시글 상태를 발행됨으로 변경
    stmt = update(Board).where(Board.board_id == board_id).values(board_status=3)
    db.execute(stmt)
    db.commit()

    return {"message": "Board published successfully"}
