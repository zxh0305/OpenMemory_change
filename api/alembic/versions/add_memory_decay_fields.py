"""add memory decay fields

Revision ID: add_memory_decay_fields
Revises: afd00efbd06b
Create Date: 2025-12-03 10:00:00.000000

为 Memory 表添加记忆衰退相关字段：
- decay_score: 衰退分数 (0-1)
- last_accessed_at: 最后访问时间
- access_count: 访问次数
- importance_score: 重要性分数 (0-1)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import DateTime, Integer, Float


# revision identifiers, used by Alembic.
revision = 'add_memory_decay_fields'
down_revision = 'afd00efbd06b'
branch_labels = None
depends_on = None


def upgrade():
    """添加记忆衰退相关字段"""
    # 添加新字段
    op.add_column('memories', sa.Column('decay_score', sa.Float(), nullable=False, server_default='1.0'))
    op.add_column('memories', sa.Column('last_accessed_at', sa.DateTime(), nullable=True))
    op.add_column('memories', sa.Column('access_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('memories', sa.Column('importance_score', sa.Float(), nullable=False, server_default='0.5'))
    
    # 创建索引以提高查询性能
    op.create_index('idx_memory_decay_score', 'memories', ['decay_score'])
    op.create_index('idx_memory_last_accessed', 'memories', ['last_accessed_at'])
    op.create_index('idx_memory_importance', 'memories', ['importance_score'])
    
    # 创建复合索引用于衰退查询
    op.create_index('idx_memory_state_decay', 'memories', ['state', 'decay_score'])


def downgrade():
    """移除记忆衰退相关字段"""
    # 删除索引
    op.drop_index('idx_memory_state_decay', table_name='memories')
    op.drop_index('idx_memory_importance', table_name='memories')
    op.drop_index('idx_memory_last_accessed', table_name='memories')
    op.drop_index('idx_memory_decay_score', table_name='memories')
    
    # 删除字段
    op.drop_column('memories', 'importance_score')
    op.drop_column('memories', 'access_count')
    op.drop_column('memories', 'last_accessed_at')
    op.drop_column('memories', 'decay_score')