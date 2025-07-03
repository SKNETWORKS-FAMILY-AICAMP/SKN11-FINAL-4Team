from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv

from auth.router import auth_router
from auth.jwt_handler import get_current_user

load_dotenv()

app = FastAPI(
    title="Social Auth Backend API",
    description="FastAPI backend for social login authentication",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://localhost:3000",
        "https://273b-222-112-208-68.ngrok-free.app",
        "*",
        os.getenv("FRONTEND_URL", "http://localhost:3000")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])

@app.get("/")
async def root():
    return {"message": "Social Auth Backend API", "version": "1.0.0"}

@app.get("/api/protected")
async def protected_route(current_user: dict = Depends(get_current_user)):
    return {"message": "This is a protected route", "user": current_user}

