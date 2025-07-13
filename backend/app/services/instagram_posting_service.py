import httpx
import logging
import os
import requests
from typing import Dict, Optional, List
from datetime import datetime
from fastapi import HTTPException, status
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class InstagramPostingService:
    """Instagram Graph API를 사용한 게시글 업로드 서비스"""

    def __init__(self):
        self.base_url = "https://graph.instagram.com/v23.0"
        # 백엔드 서버 URL (설정에서 가져오기)
        from app.core.config import settings
        self.backend_url = settings.BACKEND_URL

    def _validate_image_url(self, image_url: str) -> bool:
        """이미지 URL이 인스타그램 API 요구사항을 만족하는지 확인"""
        try:
            # S3 URL 체크
            if 's3.amazonaws.com' in image_url:
                # S3 URL은 기본적으로 유효하다고 가정 (S3 서비스에서 이미 검증됨)
                return True
            
            # 이미지 파일 확장자 확인
            if not any(image_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                logger.warning(f"Unsupported image format: {image_url}")
                return False
            
            # Content-Type 확인
            response = requests.head(image_url, timeout=10)
            content_type = response.headers.get('content-type', '').lower()
            
            if not content_type.startswith('image/'):
                logger.warning(f"Invalid content-type: {content_type}")
                return False
                
            # 파일 크기 확인 (10MB 제한)
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 10 * 1024 * 1024:
                logger.warning(f"Image too large: {content_length} bytes")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Image validation failed: {e}")
            return False

    def _convert_to_public_url(self, image_url: str) -> str:
        """로컬 이미지 경로를 공개 URL로 변환"""
        if image_url.startswith('/uploads/'):
            # 고정된 안정적인 테스트 이미지 URL (실제 존재하는 이미지)
            test_image_url = "https://httpbin.org/image/png"
            
            selected_image = test_image_url
            logger.info(f"테스트용 공개 이미지 URL 사용: {image_url} -> {selected_image}")
            return selected_image
        elif image_url.startswith('http'):
            # 이미 공개 URL인 경우 그대로 반환
            return image_url
        else:
            # 상대 경로인 경우 공개 URL로 변환
            return urljoin(self.backend_url, f"/uploads/{image_url}")

    async def upload_image_to_instagram(
        self, image_url: str, access_token: str, instagram_id: str
    ) -> str:
        """이미지를 Instagram에 업로드하고 media_id 반환"""
        try:
            # 이미지 URL을 공개 URL로 변환
            public_image_url = self._convert_to_public_url(image_url)
            logger.info(f"Converting image URL: {image_url} -> {public_image_url}")
            
            # 로컬 URL인 경우 인스타그램 업로드 불가능
            if public_image_url.startswith('https://localhost') or public_image_url.startswith('http://localhost'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="로컬 이미지 URL은 인스타그램 API에서 접근할 수 없습니다. 공개 URL을 사용하거나 S3 등의 클라우드 스토리지를 사용하세요.",
                )
            
            async with httpx.AsyncClient() as client:
                print("access_token", access_token)
                # Instagram API 요청 데이터 로깅
                request_data = {
                    "image_url": public_image_url,
                }
                logger.info(f"Instagram API request data: {request_data}")
                logger.info(f"Instagram API endpoint: {self.base_url}/{instagram_id}/media")
                
                response = await client.post(
                    f"{self.base_url}/{instagram_id}/media",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    data=request_data,
                )
                print('여기 안됨')
                print("response", response.json())
                if response.status_code != 200:
                    logger.error(
                        f"Image upload failed: {response.status_code} - {response.text}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"이미지 업로드에 실패했습니다: {response.text}",
                    )
                data = response.json()
                media_id = data.get("id")

                if not media_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Media ID를 받지 못했습니다.",
                    )

                logger.info(f"Image uploaded successfully: {media_id}")
                return media_id

        except Exception as e:
            logger.error(f"Image upload error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"이미지 업로드 중 오류가 발생했습니다: {str(e)}",
            )

    async def publish_post_to_instagram(
        self, media_id: str, caption: str, access_token: str, instagram_id: str
    ) -> Dict:
        """Instagram에 게시글 발행"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/{instagram_id}/media_publish",
                    params={
                        "access_token": access_token,
                        "creation_id": media_id,
                        "caption": caption,
                    },
                )

                if response.status_code != 200:
                    logger.error(
                        f"Post publishing failed: {response.status_code} - {response.text}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"게시글 발행에 실패했습니다: {response.text}",
                    )

                data = response.json()
                logger.info(f"Post published successfully: {data.get('id')}")
                return data

        except Exception as e:
            logger.error(f"Post publishing error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"게시글 발행 중 오류가 발생했습니다: {str(e)}",
            )

    async def post_to_instagram(
        self, instagram_id: str, access_token: str, image_url: str, caption: str
    ) -> Dict:
        """전체 Instagram 게시글 업로드 프로세스"""
        try:
            logger.info(f"Starting Instagram post upload for account: {instagram_id}")

            # 1. 이미지 업로드
            media_id = await self.upload_image_to_instagram(
                image_url, access_token, instagram_id
            )
            print("media_id", media_id)
            # 2. 게시글 발행
            result = await self.publish_post_to_instagram(
                media_id, caption, access_token, instagram_id
            )
            print("result", result)
            logger.info(f"Instagram post completed successfully: {result.get('id')}")
            return {
                "success": True,
                "instagram_post_id": result.get("id"),
                "message": "인스타그램에 성공적으로 업로드되었습니다.",
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Instagram posting error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"인스타그램 업로드 중 오류가 발생했습니다: {str(e)}",
            )

    async def verify_instagram_permissions(
        self, access_token: str, instagram_id: str
    ) -> bool:
        """Instagram 권한 확인"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{instagram_id}",
                    params={
                        "access_token": access_token,
                        "fields": "id,username,account_type",
                    },
                )
                print("response", response.json())

                if response.status_code == 200:
                    data = response.json()
                    logger.info(
                        f"Instagram permissions verified: {data.get('username')}"
                    )
                    return True
                elif response.status_code == 400:
                    error_data = response.json()
                    if error_data.get("error", {}).get("code") == 190:
                        logger.error("Instagram access token is invalid or expired")
                        return False
                    else:
                        logger.error(
                            f"Instagram permissions check failed: {response.status_code}"
                        )
                        return False
                else:
                    logger.error(
                        f"Instagram permissions check failed: {response.status_code}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Instagram permissions check error: {str(e)}")
            return False

    async def get_instagram_post_info(
        self, post_id: str, access_token: str, instagram_id: str
    ) -> Dict:
        """인스타그램 게시물 정보 조회"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{post_id}",
                    params={
                        "access_token": access_token,
                        "fields": "id,media_type,media_url,thumbnail_url,permalink,timestamp,caption,like_count,comments_count"
                    }
                )

                if response.status_code != 200:
                    logger.error(
                        f"게시물 정보 조회 실패: {response.status_code} - {response.text}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"게시물 정보 조회에 실패했습니다: {response.text}",
                    )

                data = response.json()
                logger.info(f"게시물 정보 조회 성공: {post_id}")
                return data

        except Exception as e:
            logger.error(f"게시물 정보 조회 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"게시물 정보 조회 중 오류가 발생했습니다: {str(e)}",
            )

    async def get_user_instagram_posts(
        self, access_token: str, instagram_id: str, limit: int = 10
    ) -> Dict:
        """인스타그램 사용자의 게시물 목록 조회"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{instagram_id}/media",
                    params={
                        "access_token": access_token,
                        "fields": "id,media_type,media_url,thumbnail_url,permalink,timestamp,caption,like_count,comments_count",
                        "limit": limit
                    }
                )

                if response.status_code != 200:
                    logger.error(
                        f"게시물 목록 조회 실패: {response.status_code} - {response.text}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"게시물 목록 조회에 실패했습니다: {response.text}",
                    )

                data = response.json()
                logger.info(f"게시물 목록 조회 성공: {len(data.get('data', []))}개")
                return data

        except Exception as e:
            logger.error(f"게시물 목록 조회 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"게시물 목록 조회 중 오류가 발생했습니다: {str(e)}",
            )

    async def get_instagram_post_insights(
        self, post_id: str, access_token: str, instagram_id: str
    ) -> Dict:
        """인스타그램 게시물 인사이트(통계) 조회"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{post_id}/insights",
                    params={
                        "access_token": access_token,
                        "metric": "impressions,reach,profile_views,website_clicks"
                    }
                )

                if response.status_code != 200:
                    logger.error(
                        f"게시물 인사이트 조회 실패: {response.status_code} - {response.text}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"게시물 인사이트 조회에 실패했습니다: {response.text}",
                    )

                data = response.json()
                logger.info(f"게시물 인사이트 조회 성공: {post_id}")
                return data

        except Exception as e:
            logger.error(f"게시물 인사이트 조회 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"게시물 인사이트 조회 중 오류가 발생했습니다: {str(e)}",
            )

    async def get_instagram_post_comments(
        self, post_id: str, access_token: str, instagram_id: str, limit: int = 10
    ) -> Dict:
        """인스타그램 게시물 댓글 조회"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{post_id}/comments",
                    params={
                        "access_token": access_token,
                        "fields": "id,text,timestamp,username",
                        "limit": limit
                    }
                )

                if response.status_code != 200:
                    logger.error(
                        f"게시물 댓글 조회 실패: {response.status_code} - {response.text}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"게시물 댓글 조회에 실패했습니다: {response.text}",
                    )

                data = response.json()
                logger.info(f"게시물 댓글 조회 성공: {post_id}")
                return data

        except Exception as e:
            logger.error(f"게시물 댓글 조회 오류: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"게시물 댓글 조회 중 오류가 발생했습니다: {str(e)}",
            )
