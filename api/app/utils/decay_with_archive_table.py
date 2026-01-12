"""
记忆衰退机制实现（使用独立归档表）

将衰退严重的记忆从 memories 表移动到 archived_memories 表
"""

import datetime
import math
import logging
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import (
    Memory, MemoryState, MemoryAccessLog, MemoryStatusHistory,
    ArchivedMemory, Category
)
from app.database import SessionLocal

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def calculate_time_decay(
    days_since_last_access: int,
    half_life_days: int = 30
) -> float:
    """
    计算基于时间的衰退分数（指数衰减）
    
    使用半衰期公式: score = 0.5^(days / half_life)
    """
    if days_since_last_access <= 0:
        return 1.0
    
    decay_score = math.pow(0.5, days_since_last_access / half_life_days)
    return max(0.0, min(1.0, decay_score))


def calculate_access_boost(access_count: int, max_boost: float = 2.0) -> float:
    """计算基于访问频率的加成系数"""
    if access_count <= 0:
        return 1.0
    
    boost = 1.0 + math.log(1 + access_count) * 0.2
    return min(boost, max_boost)


def calculate_decay_score(
    created_at: datetime.datetime,
    last_accessed_at: Optional[datetime.datetime],
    access_count: int,
    importance_score: float = 0.5,
    half_life_days: int = 30
) -> float:
    """计算综合衰退分数"""
    now = datetime.datetime.now(datetime.UTC)
    
    if last_accessed_at:
        days_since_access = (now - last_accessed_at).days
    else:
        days_since_access = (now - created_at).days
    
    time_decay = calculate_time_decay(days_since_access, half_life_days)
    access_boost = calculate_access_boost(access_count)
    importance_weight = 0.5 + (importance_score * 0.5)
    
    final_score = time_decay * access_boost * importance_weight
    return max(0.0, min(1.0, final_score))


def update_memory_access_stats(
    db: Session,
    memory: Memory
) -> Tuple[int, Optional[datetime.datetime]]:
    """更新记忆的访问统计信息"""
    access_logs = db.query(MemoryAccessLog).filter(
        MemoryAccessLog.memory_id == memory.id
    ).all()
    
    access_count = len(access_logs)
    last_accessed = None
    
    if access_logs:
        last_accessed = max(log.accessed_at for log in access_logs)
    
    return access_count, last_accessed


def update_single_memory_decay(
    db: Session,
    memory: Memory,
    half_life_days: int = 30
) -> float:
    """更新单个记忆的衰退分数"""
    access_count, last_accessed = update_memory_access_stats(db, memory)
    
    decay_score = calculate_decay_score(
        memory.created_at,
        last_accessed,
        access_count,
        memory.importance_score,
        half_life_days
    )
    
    memory.decay_score = decay_score
    memory.last_accessed_at = last_accessed
    memory.access_count = access_count
    memory.updated_at = datetime.datetime.now(datetime.UTC)
    
    return decay_score


def move_memory_to_archive(
    db: Session,
    memory: Memory
) -> ArchivedMemory:
    """
    将记忆从 memories 表移动到 archived_memories 表
    
    步骤：
    1. 获取记忆的分类信息
    2. 创建归档记忆记录
    3. 删除原记忆记录
    4. 记录状态变更历史
    """
    # 1. 获取分类信息
    categories = [cat.name for cat in memory.categories]
    
    # 2. 创建归档记忆记录
    archived_memory = ArchivedMemory(
        id=memory.id,  # 保持相同的ID
        user_id=memory.user_id,
        app_id=memory.app_id,
        content=memory.content,
        vector=memory.vector,
        metadata_=memory.metadata_,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
        archived_at=datetime.datetime.now(datetime.UTC),
        archived_from_state=memory.state,
        decay_score_at_archive=memory.decay_score,
        last_accessed_at=memory.last_accessed_at,
        access_count=memory.access_count,
        importance_score=memory.importance_score,
        categories_snapshot=categories
    )
    
    db.add(archived_memory)
    
    # 3. 记录状态变更历史
    history = MemoryStatusHistory(
        memory_id=memory.id,
        changed_by=memory.user_id,
        old_state=memory.state,
        new_state=MemoryState.archived
    )
    db.add(history)
    
    # 4. 删除原记忆记录
    db.delete(memory)
    
    logger.info(f"记忆 {memory.id} 已移动到归档表")
    
    return archived_memory


def update_memory_decay_scores(
    db: Session,
    batch_size: int = 100,
    half_life_days: int = 30,
    user_id: Optional[str] = None
) -> int:
    """批量更新记忆的衰退分数"""
    logger.info(f"开始更新记忆衰退分数（半衰期: {half_life_days}天）...")
    
    total_updated = 0
    offset = 0
    
    while True:
        query = db.query(Memory).filter(
            Memory.state == MemoryState.active
        )
        
        if user_id:
            query = query.filter(Memory.user_id == user_id)
        
        memories = query.offset(offset).limit(batch_size).all()
        
        if not memories:
            break
        
        for memory in memories:
            try:
                update_single_memory_decay(db, memory, half_life_days)
                total_updated += 1
            except Exception as e:
                logger.error(f"更新记忆 {memory.id} 衰退分数失败: {e}")
        
        db.commit()
        logger.info(f"已更新 {total_updated} 条记忆...")
        
        offset += batch_size
    
    logger.info(f"记忆衰退分数更新完成，共更新 {total_updated} 条记忆")
    return total_updated


def auto_archive_decayed_memories(
    db: Session,
    threshold: float = 0.1,
    batch_size: int = 100,
    user_id: Optional[str] = None
) -> int:
    """
    自动归档衰退严重的记忆（移动到归档表）
    """
    logger.info(f"开始自动归档衰退记忆（阈值: {threshold}）...")
    
    query = db.query(Memory).filter(
        and_(
            Memory.state == MemoryState.active,
            Memory.decay_score < threshold
        )
    )
    
    if user_id:
        query = query.filter(Memory.user_id == user_id)
    
    memories_to_archive = query.limit(batch_size).all()
    
    if not memories_to_archive:
        logger.info("没有需要归档的记忆")
        return 0
    
    archived_count = 0
    
    for memory in memories_to_archive:
        try:
            move_memory_to_archive(db, memory)
            archived_count += 1
        except Exception as e:
            logger.error(f"归档记忆 {memory.id} 失败: {e}")
            db.rollback()
    
    db.commit()
    logger.info(f"自动归档完成，共归档 {archived_count} 条记忆到 archived_memories 表")
    
    return archived_count


def restore_archived_memory(
    db: Session,
    memory_id: str,
    user_id: str
) -> bool:
    """
    从归档表恢复记忆到活跃表
    
    步骤：
    1. 从 archived_memories 表查找记忆
    2. 创建新的 Memory 记录
    3. 删除归档记录
    4. 记录状态变更
    """
    # 1. 查找归档记忆
    archived_memory = db.query(ArchivedMemory).filter(
        ArchivedMemory.id == memory_id,
        ArchivedMemory.user_id == user_id
    ).first()
    
    if not archived_memory:
        logger.warning(f"未找到归档记忆: {memory_id}")
        return False
    
    # 2. 创建新的活跃记忆
    memory = Memory(
        id=archived_memory.id,
        user_id=archived_memory.user_id,
        app_id=archived_memory.app_id,
        content=archived_memory.content,
        vector=archived_memory.vector,
        metadata_=archived_memory.metadata_,
        state=MemoryState.active,
        created_at=archived_memory.created_at,
        updated_at=datetime.datetime.now(datetime.UTC),
        decay_score=1.0,  # 重置衰退分数
        last_accessed_at=None,
        access_count=0,
        importance_score=archived_memory.importance_score
    )
    
    db.add(memory)
    
    # 3. 恢复分类关联
    if archived_memory.categories_snapshot:
        for cat_name in archived_memory.categories_snapshot:
            category = db.query(Category).filter(Category.name == cat_name).first()
            if category:
                memory.categories.append(category)
    
    # 4. 记录状态变更
    history = MemoryStatusHistory(
        memory_id=memory_id,
        changed_by=user_id,
        old_state=MemoryState.archived,
        new_state=MemoryState.active
    )
    db.add(history)
    
    # 5. 删除归档记录
    db.delete(archived_memory)
    
    db.commit()
    
    logger.info(f"记忆 {memory_id} 已从归档表恢复到活跃表")
    return True


def get_decay_statistics(db: Session, user_id: Optional[str] = None) -> dict:
    """获取衰退统计信息（包括归档表）"""
    # 活跃记忆统计
    query = db.query(Memory).filter(Memory.state == MemoryState.active)
    if user_id:
        query = query.filter(Memory.user_id == user_id)
    
    active_memories = query.all()
    
    # 归档记忆统计
    archived_query = db.query(ArchivedMemory)
    if user_id:
        archived_query = archived_query.filter(ArchivedMemory.user_id == user_id)
    
    archived_count = archived_query.count()
    
    if not active_memories:
        return {
            "total_active_memories": 0,
            "total_archived_memories": archived_count,
            "average_decay_score": 0.0,
            "high_decay_count": 0,
            "medium_decay_count": 0,
            "low_decay_count": 0
        }
    
    decay_scores = [m.decay_score for m in active_memories]
    avg_decay = sum(decay_scores) / len(decay_scores)
    
    high_decay = sum(1 for s in decay_scores if s >= 0.7)
    medium_decay = sum(1 for s in decay_scores if 0.3 <= s < 0.7)
    low_decay = sum(1 for s in decay_scores if s < 0.3)
    
    return {
        "total_active_memories": len(active_memories),
        "total_archived_memories": archived_count,
        "average_decay_score": round(avg_decay, 3),
        "high_decay_count": high_decay,
        "medium_decay_count": medium_decay,
        "low_decay_count": low_decay
    }


def get_archived_memories_list(
    db: Session,
    user_id: str,
    limit: int = 50,
    offset: int = 0
) -> List[ArchivedMemory]:
    """获取归档记忆列表"""
    return db.query(ArchivedMemory).filter(
        ArchivedMemory.user_id == user_id
    ).order_by(
        ArchivedMemory.archived_at.desc()
    ).offset(offset).limit(limit).all()