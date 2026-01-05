"""
记忆衰退机制实现

基于时间和访问频率的记忆衰退算法，支持：
1. 指数衰减：基于时间的自然遗忘
2. 访问加成：频繁访问的记忆衰减更慢
3. 重要性权重：重要记忆不易衰退
4. 自动归档：衰退严重的记忆自动归档
"""

import datetime
import math
import logging
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import Memory, MemoryState, MemoryAccessLog, MemoryStatusHistory
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
    
    参数:
        days_since_last_access: 距离上次访问的天数
        half_life_days: 半衰期（天），默认30天
        
    返回:
        时间衰退分数 (0-1)
    """
    if days_since_last_access <= 0:
        return 1.0
    
    # 指数衰减公式
    decay_score = math.pow(0.5, days_since_last_access / half_life_days)
    return max(0.0, min(1.0, decay_score))


def calculate_access_boost(access_count: int, max_boost: float = 2.0) -> float:
    """
    计算基于访问频率的加成系数
    
    访问越多，衰减越慢（加成越大）
    
    参数:
        access_count: 访问次数
        max_boost: 最大加成倍数，默认2.0
        
    返回:
        访问加成系数 (1.0 - max_boost)
    """
    if access_count <= 0:
        return 1.0
    
    # 对数增长，避免无限增长
    boost = 1.0 + math.log(1 + access_count) * 0.2
    return min(boost, max_boost)


def calculate_decay_score(
    created_at: datetime.datetime,
    last_accessed_at: Optional[datetime.datetime],
    access_count: int,
    importance_score: float = 0.5,
    half_life_days: int = 30
) -> float:
    """
    计算综合衰退分数
    
    综合考虑：
    1. 时间衰减（基础分数）
    2. 访问频率加成
    3. 重要性权重
    
    参数:
        created_at: 创建时间
        last_accessed_at: 最后访问时间（None表示从未访问）
        access_count: 访问次数
        importance_score: 重要性分数 (0-1)
        half_life_days: 半衰期（天）
        
    返回:
        最终衰退分数 (0-1)，1.0表示完全新鲜，0.0表示完全衰退
    """
    now = datetime.datetime.now(datetime.UTC)
    
    # 确保所有datetime都有时区信息
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=datetime.UTC)
    if last_accessed_at and last_accessed_at.tzinfo is None:
        last_accessed_at = last_accessed_at.replace(tzinfo=datetime.UTC)
    
    # 计算距离上次访问的天数
    if last_accessed_at:
        days_since_access = (now - last_accessed_at).days
    else:
        days_since_access = (now - created_at).days
    
    # 1. 基础时间衰减
    time_decay = calculate_time_decay(days_since_access, half_life_days)
    
    # 2. 访问频率加成
    access_boost = calculate_access_boost(access_count)
    
    # 3. 重要性权重（重要记忆衰减更慢）
    importance_weight = 0.5 + (importance_score * 0.5)  # 0.5-1.0
    
    # 综合计算
    final_score = time_decay * access_boost * importance_weight
    
    # 确保在0-1范围内
    return max(0.0, min(1.0, final_score))


def update_memory_access_stats(
    db: Session,
    memory: Memory
) -> Tuple[int, Optional[datetime.datetime]]:
    """
    更新记忆的访问统计信息
    
    参数:
        db: 数据库会话
        memory: 记忆对象
        
    返回:
        (访问次数, 最后访问时间)
    """
    # 查询访问日志
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
    """
    更新单个记忆的衰退分数
    
    参数:
        db: 数据库会话
        memory: 记忆对象
        half_life_days: 半衰期（天）
        
    返回:
        更新后的衰退分数
    """
    # 获取访问统计
    access_count, last_accessed = update_memory_access_stats(db, memory)
    
    # 计算衰退分数
    decay_score = calculate_decay_score(
        memory.created_at,
        last_accessed,
        access_count,
        memory.importance_score,
        half_life_days
    )
    
    # 更新记忆
    memory.decay_score = decay_score
    memory.last_accessed_at = last_accessed
    memory.access_count = access_count
    memory.updated_at = datetime.datetime.now(datetime.UTC)
    
    return decay_score


def update_memory_decay_scores(
    db: Session,
    batch_size: int = 100,
    half_life_days: int = 30,
    user_id: Optional[str] = None
) -> int:
    """
    批量更新记忆的衰退分数
    
    参数:
        db: 数据库会话
        batch_size: 每批处理的记忆数量
        half_life_days: 半衰期（天）
        user_id: 可选，只更新特定用户的记忆
        
    返回:
        更新的记忆数量
    """
    logger.info(f"开始更新记忆衰退分数（半衰期: {half_life_days}天）...")
    
    total_updated = 0
    offset = 0
    
    while True:
        # 构建查询
        query = db.query(Memory).filter(
            Memory.state == MemoryState.active
        )
        
        if user_id:
            query = query.filter(Memory.user_id == user_id)
        
        # 分批获取记忆
        memories = query.offset(offset).limit(batch_size).all()
        
        if not memories:
            break
        
        # 更新每个记忆的衰退分数
        for memory in memories:
            try:
                update_single_memory_decay(db, memory, half_life_days)
                total_updated += 1
            except Exception as e:
                logger.error(f"更新记忆 {memory.id} 衰退分数失败: {e}")
        
        # 提交当前批次
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
    自动归档衰退严重的记忆
    
    参数:
        db: 数据库会话
        threshold: 衰退阈值，低于此值的记忆将被归档
        batch_size: 每批处理的记忆数量
        user_id: 可选，只处理特定用户的记忆
        
    返回:
        归档的记忆数量
    """
    logger.info(f"开始自动归档衰退记忆（阈值: {threshold}）...")
    
    # 构建查询
    query = db.query(Memory).filter(
        and_(
            Memory.state == MemoryState.active,
            Memory.decay_score < threshold
        )
    )
    
    if user_id:
        query = query.filter(Memory.user_id == user_id)
    
    # 获取需要归档的记忆
    memories_to_archive = query.limit(batch_size).all()
    
    if not memories_to_archive:
        logger.info("没有需要归档的记忆")
        return 0
    
    # 归档记忆
    now = datetime.datetime.now(datetime.UTC)
    archived_count = 0
    
    for memory in memories_to_archive:
        try:
            # 更新状态
            old_state = memory.state
            memory.state = MemoryState.archived
            memory.archived_at = now
            
            # 记录状态变更历史
            history = MemoryStatusHistory(
                memory_id=memory.id,
                changed_by=memory.user_id,
                old_state=old_state,
                new_state=MemoryState.archived
            )
            db.add(history)
            
            archived_count += 1
        except Exception as e:
            logger.error(f"归档记忆 {memory.id} 失败: {e}")
    
    db.commit()
    logger.info(f"自动归档完成，共归档 {archived_count} 条记忆")
    
    return archived_count


def get_decay_statistics(db: Session, user_id: Optional[str] = None) -> dict:
    """
    获取衰退统计信息
    
    参数:
        db: 数据库会话
        user_id: 可选，只统计特定用户的记忆
        
    返回:
        统计信息字典
    """
    query = db.query(Memory).filter(Memory.state == MemoryState.active)
    
    if user_id:
        query = query.filter(Memory.user_id == user_id)
    
    memories = query.all()
    
    if not memories:
        return {
            "total_memories": 0,
            "average_decay_score": 0.0,
            "high_decay_count": 0,
            "medium_decay_count": 0,
            "low_decay_count": 0
        }
    
    # 计算统计信息
    decay_scores = [m.decay_score for m in memories]
    avg_decay = sum(decay_scores) / len(decay_scores)
    
    high_decay = sum(1 for s in decay_scores if s >= 0.7)
    medium_decay = sum(1 for s in decay_scores if 0.3 <= s < 0.7)
    low_decay = sum(1 for s in decay_scores if s < 0.3)
    
    return {
        "total_memories": len(memories),
        "average_decay_score": round(avg_decay, 3),
        "high_decay_count": high_decay,  # 新鲜记忆
        "medium_decay_count": medium_decay,  # 中等衰退
        "low_decay_count": low_decay  # 严重衰退
    }


def restore_archived_memory(
    db: Session,
    memory_id: str,
    user_id: str
) -> bool:
    """
    恢复已归档的记忆
    
    参数:
        db: 数据库会话
        memory_id: 记忆ID
        user_id: 用户ID
        
    返回:
        是否成功恢复
    """
    memory = db.query(Memory).filter(
        Memory.id == memory_id,
        Memory.user_id == user_id,
        Memory.state == MemoryState.archived
    ).first()
    
    if not memory:
        return False
    
    # 恢复记忆
    old_state = memory.state
    memory.state = MemoryState.active
    memory.decay_score = 1.0  # 重置衰退分数
    memory.archived_at = None
    
    # 记录状态变更
    history = MemoryStatusHistory(
        memory_id=memory.id,
        changed_by=user_id,
        old_state=old_state,
        new_state=MemoryState.active
    )
    db.add(history)
    db.commit()
    
    logger.info(f"记忆 {memory_id} 已恢复")
    return True