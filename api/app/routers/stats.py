from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Memory, App, MemoryState

"""
统计信息API路由

提供用户统计信息：
- 获取用户的总记忆数
- 获取用户的总应用数
- 获取用户的应用列表
"""
router = APIRouter(prefix="/api/v1/stats", tags=["stats"])

@router.get("/")
async def get_profile(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    获取用户的统计信息。
    
    返回内容：
    - total_memories: 用户的总记忆数（不包括已删除的）
    - total_apps: 用户的总应用数
    - apps: 用户的应用列表
    
    参数:
    - user_id: 用户ID（查询参数，必填）
    
    使用场景：
    - 显示用户概览信息
    - 统计用户数据
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get total number of memories
    total_memories = db.query(Memory).filter(Memory.user_id == user.id, Memory.state != MemoryState.deleted).count()

    # Get total number of apps
    apps = db.query(App).filter(App.owner == user)
    total_apps = apps.count()

    return {
        "total_memories": total_memories,
        "total_apps": total_apps,
        "apps": apps.all()
    }

