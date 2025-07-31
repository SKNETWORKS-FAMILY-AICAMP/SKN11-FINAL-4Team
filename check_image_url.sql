-- AI_INFLUENCER 테이블에서 image_url 확인
SELECT 
    influencer_id,
    influencer_name,
    image_url,
    CASE 
        WHEN image_url IS NULL THEN 'NULL'
        WHEN image_url = '' THEN 'EMPTY'
        ELSE 'EXISTS'
    END as image_status
FROM AI_INFLUENCER
ORDER BY created_at DESC
LIMIT 10;

-- 특정 인플루언서의 image_url 업데이트 예시
-- UPDATE AI_INFLUENCER 
-- SET image_url = 'https://example.com/path/to/image.jpg'
-- WHERE influencer_id = 'your-influencer-id';