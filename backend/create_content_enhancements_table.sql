-- Create content_enhancements table
CREATE TABLE IF NOT EXISTS content_enhancements (
    enhancement_id VARCHAR(36) NOT NULL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    original_content TEXT NOT NULL,
    enhanced_content TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    openai_model VARCHAR(50) NULL,
    openai_tokens_used INT NULL,
    openai_cost FLOAT NULL,
    board_id VARCHAR(36) NULL,
    influencer_id VARCHAR(36) NULL,
    enhancement_prompt TEXT NULL,
    improvement_notes TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
    approved_at DATETIME NULL,
    INDEX idx_content_enhancements_user_id (user_id),
    INDEX idx_content_enhancements_enhancement_id (enhancement_id)
);