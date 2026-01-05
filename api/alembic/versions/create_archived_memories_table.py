"""create archived memories table

Revision ID: create_archived_memories_table
Revises: add_memory_decay_fields
Create Date: 2025-12-03 11:00:00.000000

创建独立的归档记忆表 archived_memories
用于存储衰退后从 memories 表移动过来的记忆
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import DateTime, Integer, Float, Text, JSON, Enum


# revision identifiers, used by Alembic.
revision = 'create_archived_memories_table'
down_revision = 'add_memory_decay_fields'
branch_labels = None
depends_on = None


def upgrade():
    """创建归档记忆表"""
    
    # 创建 MemoryState 枚举类型（如果数据库支持）
    memory_state_enum = sa.Enum('active', 'paused', 'archived', 'deleted', name='memorystate')
    
    # 创建 archived_memories 表
    op.create_table(
        'archived_memories',
        # 基本字段
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('user_id', sa.String(32), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('app_id', sa.String(32), sa.ForeignKey('apps.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('vector', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        
        # 原始时间信息
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        
        # 归档相关信息
        sa.Column('archived_at', sa.DateTime(), nullable=False),
        sa.Column('archived_from_state', memory_state_enum, nullable=False),
        
        # 衰退信息快照
        sa.Column('decay_score_at_archive', sa.Float(), nullable=False),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
        sa.Column('access_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('importance_score', sa.Float(), nullable=False, server_default='0.5'),
        
        # 分类快照
        sa.Column('categories_snapshot', sa.JSON(), nullable=True),
    )
    
    # 创建索引
    op.create_index('idx_archived_user_time', 'archived_memories', ['user_id', 'archived_at'])
    op.create_index('idx_archived_app_time', 'archived_memories', ['app_id', 'archived_at'])
    op.create_index('idx_archived_decay', 'archived_memories', ['decay_score_at_archive'])
    op.create_index('idx_archived_created', 'archived_memories', ['created_at'])
    op.create_index('idx_archived_user_id', 'archived_memories', ['user_id'])
    op.create_index('idx_archived_app_id', 'archived_memories', ['app_id'])


def downgrade():
    """删除归档记忆表"""
    # 删除索引
    op.drop_index('idx_archived_app_id', table_name='archived_memories')
    op.drop_index('idx_archived_user_id', table_name='archived_memories')
    op.drop_index('idx_archived_created', table_name='archived_memories')
    op.drop_index('idx_archived_decay', table_name='archived_memories')
    op.drop_index('idx_archived_app_time', table_name='archived_memories')
    op.drop_index('idx_archived_user_time', table_name='archived_memories')
    
    # 删除表
    op.drop_table('archived_memories')
    
    # 删除枚举类型（如果需要）
    # op.execute('DROP TYPE IF EXISTS memorystate')