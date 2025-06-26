from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.board import Board
from app.schemas.board import BoardCreate, BoardResponse

router = APIRouter()


@router.get("/", response_model=List[BoardResponse])
def get_boards(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """게시글 목록 조회"""
    boards = db.query(Board).offset(skip).limit(limit).all()
    return boards


@router.get("/{board_uuid}", response_model=BoardResponse)
def get_board(board_uuid: str, db: Session = Depends(get_db)):
    """특정 게시글 조회"""
    board = db.query(Board).filter(Board.board_uuid == board_uuid).first()
    if board is None:
        raise HTTPException(status_code=404, detail="Board not found")
    return board


@router.post("/", response_model=BoardResponse)
def create_board(board: BoardCreate, db: Session = Depends(get_db)):
    """새 게시글 생성"""
    db_board = Board(**board.model_dump())
    db.add(db_board)
    db.commit()
    db.refresh(db_board)
    return db_board


@router.put("/{board_uuid}", response_model=BoardResponse)
def update_board(board_uuid: str, board_update: dict, db: Session = Depends(get_db)):
    """게시글 수정"""
    db_board = db.query(Board).filter(Board.board_uuid == board_uuid).first()
    if db_board is None:
        raise HTTPException(status_code=404, detail="Board not found")

    for field, value in board_update.items():
        if hasattr(db_board, field):
            setattr(db_board, field, value)

    db.commit()
    db.refresh(db_board)
    return db_board


@router.delete("/{board_uuid}")
def delete_board(board_uuid: str, db: Session = Depends(get_db)):
    """게시글 삭제"""
    db_board = db.query(Board).filter(Board.board_uuid == board_uuid).first()
    if db_board is None:
        raise HTTPException(status_code=404, detail="Board not found")

    db.delete(db_board)
    db.commit()
    return {"message": "Board deleted successfully"}
