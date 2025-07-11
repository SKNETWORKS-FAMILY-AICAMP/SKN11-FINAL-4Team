import httpx
import logging
from typing import Dict, Optional, List
from datetime import datetime
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class InstagramPostingService:
    """Instagram Graph API를 사용한 게시글 업로드 서비스"""

    def __init__(self):
        self.base_url = "https://graph.facebook.com/v18.0"

    async def upload_image_to_instagram(
        self, image_url: str, access_token: str, instagram_id: str
    ) -> str:
        """이미지를 Instagram에 업로드하고 media_id 반환"""
        try:
            async with httpx.AsyncClient() as client:
                # 1. 이미지 URL을 Instagram에 등록
                response = await client.post(
                    f"{self.base_url}/{instagram_id}/media",
                    params={
                        "access_token": access_token,
                        "image_url": image_url,
                        "caption": "AI Generated Content",
                    },
                )

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

            # 2. 게시글 발행
            result = await self.publish_post_to_instagram(
                media_id, caption, access_token, instagram_id
            )

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
