"""
记忆衰退管理API路由

提供记忆衰退相关的API接口：
- 手动触发衰退更新
- 查询衰退统计
- 恢复归档记忆
- 调整记忆重要性
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
import logging

from app.database import get_db
from app.models import Memory, User, MemoryState
from app.utils.decay import (
    update_memory_decay_scores,
    auto_archive_decayed_memories,
    get_decay_statistics,
    restore_archived_memory,
    update_single_memory_decay
)
from app.tasks import trigger_decay_update_now, get_scheduler_status

router = APIRouter(prefix="/api/v1/decay", tags=["memory-decay"])
logger = logging.getLogger(__name__)


class TriggerDecayUpdateRequest(BaseModel):
    """触发衰退更新请求"""
    user_id: Optional[str] = Field(None, description="可选，只更新特定用户的记忆")
    half_life_days: int = Field(30, ge=1, le=365, description="半衰期（天）")
    auto_archive: bool = Field(True, description="是否自动归档衰退记忆")
    archive_threshold: float = Field(0.1, ge=0.0, le=1.0, description="归档阈值")


class UpdateImportanceRequest(BaseModel):
    """更新记忆重要性请求"""
    memory_id: str
    user_id: str
    importance_score: float = Field(..., ge=0.0, le=1.0, description="重要性分数 (0-1)")


class RestoreMemoryRequest(BaseModel):
    """恢复归档记忆请求"""
    memory_id: str
    user_id: str


@router.post("/trigger-update")
async def trigger_decay_update(
    request: TriggerDecayUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    手动触发记忆衰退更新
    
    该接口会：
    1. 更新记忆的衰退分数
    2. 可选：自动归档衰退严重的记忆
    
    参数:
        - user_id: 可选，只更新特定用户的记忆
        - half_life_days: 半衰期（天），默认30天
        - auto_archive: 是否自动归档，默认true
        - archive_threshold: 归档阈值，默认0.1
    """
    try:
        logger.info(f"手动触发衰退更新: user_id={request.user_id}, half_life={request.half_life_days}")
        
        # 更新衰退分数
        updated_count = update_memory_decay_scores(
            db,
            batch_size=100,
            half_life_days=request.half_life_days,
            user_id=request.user_id
        )
        
        archived_count = 0
        if request.auto_archive:
            # 自动归档
            archived_count = auto_archive_decayed_memories(
                db,
                threshold=request.archive_threshold,
                batch_size=100,
                user_id=request.user_id
            )
        
        # 获取统计信息
        stats = get_decay_statistics(db, user_id=request.user_id)
        
        return {
            "success": True,
            "message": "衰退更新完成",
            "updated_count": updated_count,
            "archived_count": archived_count,
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"触发衰退更新失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"衰退更新失败: {str(e)}")


@router.get("/statistics")
async def get_statistics(
    user_id: Optional[str] = Query(None, description="可选，只统计特定用户"),
    db: Session = Depends(get_db)
):
    """
    获取记忆衰退统计信息
    
    返回：
    - 总记忆数
    - 平均衰退分数
    - 各衰退等级的记忆数量
    """
    try:
        stats = get_decay_statistics(db, user_id=user_id)
        return {
            "success": True,
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"获取衰退统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


@router.get("/scheduler-status")
async def get_scheduler_info():
    """
    获取衰退调度器状态
    
    返回调度器的运行状态、下次执行时间等信息
    """
    try:
        status = get_scheduler_status()
        return {
            "success": True,
            "scheduler": status
        }
    except Exception as e:
        logger.error(f"获取调度器状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.post("/update-importance")
async def update_memory_importance(
    request: UpdateImportanceRequest,
    db: Session = Depends(get_db)
):
    """
    更新记忆的重要性分数
    
    重要性分数影响衰退速度：
    - 1.0: 非常重要，衰减最慢
    - 0.5: 普通重要性（默认）
    - 0.0: 不重要，衰减最快
    """
    try:
        # 验证用户
        user = db.query(User).filter(User.user_id == request.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        # 查找记忆
        memory = db.query(Memory).filter(
            Memory.id == request.memory_id,
            Memory.user_id == user.id
        ).first()
        
        if not memory:
            raise HTTPException(status_code=404, detail="记忆不存在")
        
        # 更新重要性分数
        old_importance = memory.importance_score
        memory.importance_score = request.importance_score
        
        # 重新计算衰退分数
        new_decay_score = update_single_memory_decay(db, memory)
        
        db.commit()
        
        logger.info(f"更新记忆 {request.memory_id} 重要性: {old_importance} -> {request.importance_score}")
        
        return {
            "success": True,
            "message": "重要性更新成功",
            "memory_id": request.memory_id,
            "old_importance": old_importance,
            "new_importance": request.importance_score,
            "new_decay_score": new_decay_score
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新重要性失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.post("/restore-memory")
async def restore_memory(
    request: RestoreMemoryRequest,
    db: Session = Depends(get_db)
):
    """
    恢复已归档的记忆
    
    将归档状态的记忆恢复为活跃状态，并重置衰退分数
    """
    try:
        # 验证用户
        user = db.query(User).filter(User.user_id == request.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        # 恢复记忆
        success = restore_archived_memory(db, request.memory_id, user.id)
        
        if not success:
            raise HTTPException(status_code=404, detail="记忆不存在或未归档")
        
        return {
            "success": True,
            "message": "记忆恢复成功",
            "memory_id": request.memory_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"恢复记忆失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")


@router.get("/decayed-memories")
async def get_decayed_memories(
    user_id: str = Query(..., description="用户ID"),
    threshold: float = Query(0.3, ge=0.0, le=1.0, description="衰退阈值"),
    limit: int = Query(50, ge=1, le=500, description="返回数量限制"),
    db: Session = Depends(get_db)
):
    """
    获取衰退严重的记忆列表
    
    返回衰退分数低于指定阈值的记忆
    """
    try:
        # 验证用户
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        # 查询衰退记忆
        memories = db.query(Memory).filter(
            Memory.user_id == user.id,
            Memory.state == MemoryState.active,
            Memory.decay_score < threshold
        ).order_by(Memory.decay_score.asc()).limit(limit).all()
        
        result = [
            {
                "id": str(memory.id),
                "content": memory.content[:100] + "..." if len(memory.content) > 100 else memory.content,
                "decay_score": memory.decay_score,
                "importance_score": memory.importance_score,
                "access_count": memory.access_count,
                "last_accessed_at": memory.last_accessed_at.isoformat() if memory.last_accessed_at else None,
                "created_at": memory.created_at.isoformat()
            }
            for memory in memories
        ]
        
        return {
            "success": True,
            "count": len(result),
            "threshold": threshold,
            "memories": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取衰退记忆失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")