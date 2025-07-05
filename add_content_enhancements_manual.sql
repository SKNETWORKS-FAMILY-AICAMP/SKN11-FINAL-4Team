-- ===================================================
-- content_enhancements 테이블 수동 추가
-- 설명: QA 쌍 생성 프롬프트 관리용 테이블
-- ===================================================

USE AIMEX_MAIN;

-- content_enhancements 테이블이 존재하지 않는 경우에만 생성
CREATE TABLE IF NOT EXISTS `content_enhancements` (
  `enhancement_id` varchar(36) NOT NULL COMMENT 'QA 프롬프트 관리 고유 식별자',
  `user_id` varchar(36) NOT NULL COMMENT '사용자 고유 식별자',
  `original_content` text NOT NULL COMMENT '원본 콘텐츠 (QA 생성 대상 텍스트)',
  `enhanced_content` text NOT NULL COMMENT '생성된 QA 쌍들',
  `status` varchar(20) DEFAULT 'pending' COMMENT '처리 상태 (pending, processing, completed, failed)',
  `openai_model` varchar(50) DEFAULT NULL COMMENT '사용된 OpenAI 모델',
  `openai_tokens_used` int DEFAULT NULL COMMENT '사용된 OpenAI 토큰 수',
  `openai_cost` float DEFAULT NULL COMMENT 'OpenAI 비용',
  `board_id` varchar(36) DEFAULT NULL COMMENT '연관된 게시글 ID',
  `influencer_id` varchar(36) DEFAULT NULL COMMENT '연관된 인플루언서 ID',
  `enhancement_prompt` text DEFAULT NULL COMMENT 'QA 쌍 생성에 사용된 프롬프트',
  `improvement_notes` text DEFAULT NULL COMMENT 'QA 생성 개선 사항 노트',
  `approved_at` datetime DEFAULT NULL COMMENT 'QA 쌍 승인 시간',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '생성 시간',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정 시간',
  PRIMARY KEY (`enhancement_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_board_id` (`board_id`),
  KEY `idx_influencer_id` (`influencer_id`),
  KEY `idx_status` (`status`),
  CONSTRAINT `fk_content_enhancements_user` FOREIGN KEY (`user_id`) REFERENCES `USER` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_content_enhancements_board` FOREIGN KEY (`board_id`) REFERENCES `BOARD` (`board_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_content_enhancements_influencer` FOREIGN KEY (`influencer_id`) REFERENCES `AI_INFLUENCER` (`influencer_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='QA 쌍 생성 프롬프트 관리 테이블';

-- 테이블 생성 확인
SELECT 'content_enhancements 테이블이 성공적으로 생성되었습니다.' AS message; 