"""Add Instagram fields to AI_INFLUENCER table

Revision ID: 002_add_instagram_fields
Revises: 001_initial_ddl_based_migration
Create Date: 2025-06-30 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers
revision = '002_add_instagram_fields'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    """Add Instagram integration fields to AI_INFLUENCER table"""
    
    # Instagram 계정 연동 필드들 추가
    op.add_column('AI_INFLUENCER', sa.Column('instagram_id', sa.String(255), nullable=True, comment='연동된 인스타그램 계정 ID'))
    op.add_column('AI_INFLUENCER', sa.Column('instagram_username', sa.String(100), nullable=True, comment='인스타그램 사용자명'))
    op.add_column('AI_INFLUENCER', sa.Column('instagram_access_token', sa.Text, nullable=True, comment='인스타그램 액세스 토큰'))
    op.add_column('AI_INFLUENCER', sa.Column('instagram_account_type', sa.String(50), nullable=True, comment='인스타그램 계정 타입 (PERSONAL, BUSINESS, CREATOR)'))
    op.add_column('AI_INFLUENCER', sa.Column('instagram_connected_at', sa.TIMESTAMP, nullable=True, comment='인스타그램 계정 연동 일시'))
    op.add_column('AI_INFLUENCER', sa.Column('instagram_is_active', sa.Boolean, nullable=True, default=False, comment='인스타그램 연동 활성화 여부'))


def downgrade():
    """Remove Instagram integration fields from AI_INFLUENCER table"""
    
    # Instagram 관련 필드들 제거
    op.drop_column('AI_INFLUENCER', 'instagram_is_active')
    op.drop_column('AI_INFLUENCER', 'instagram_connected_at')
    op.drop_column('AI_INFLUENCER', 'instagram_account_type')
    op.drop_column('AI_INFLUENCER', 'instagram_access_token')
    op.drop_column('AI_INFLUENCER', 'instagram_username')
    op.drop_column('AI_INFLUENCER', 'instagram_id')