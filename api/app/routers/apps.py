from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc

from app.database import get_db
from app.models import App, Memory, MemoryAccessLog, MemoryState, User
from app.utils.db import get_or_create_user

"""
应用管理API路由

提供应用的管理功能：
- 查询应用列表
- 获取应用详情
- 查看应用创建的记忆
- 查看应用访问的记忆
- 更新应用状态
"""
router = APIRouter(prefix="/api/v1/apps", tags=["apps"])

# Helper functions
def get_app_or_404(db: Session, app_id: UUID, user_id: Optional[str] = None) -> App:
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    # If user_id is provided, verify the app belongs to the user
    if user_id:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user and app.owner_id != user.id:
            raise HTTPException(status_code=403, detail="App does not belong to this user")
    return app

# List all apps with filtering
@router.get("/")
async def list_apps(
    user_id: str,
    name: Optional[str] = None,
    is_active: Optional[bool] = None,
    sort_by: str = 'name',
    sort_direction: str = 'asc',
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    # Get or create user
    user = get_or_create_user(db, user_id)
    
    # Create a subquery for memory counts (filtered by user)
    memory_counts = db.query(
        Memory.app_id,
        func.count(Memory.id).label('memory_count')
    ).filter(
        Memory.user_id == user.id,
        Memory.state.in_([MemoryState.active, MemoryState.paused, MemoryState.archived])
    ).group_by(Memory.app_id).subquery()

    # Create a subquery for access counts (filtered by user's apps)
    access_counts = db.query(
        MemoryAccessLog.app_id,
        func.count(func.distinct(MemoryAccessLog.memory_id)).label('access_count')
    ).join(
        Memory, MemoryAccessLog.memory_id == Memory.id
    ).filter(
        Memory.user_id == user.id
    ).group_by(MemoryAccessLog.app_id).subquery()

    # Base query - filter by user's apps
    query = db.query(
        App,
        func.coalesce(memory_counts.c.memory_count, 0).label('total_memories_created'),
        func.coalesce(access_counts.c.access_count, 0).label('total_memories_accessed')
    ).filter(
        App.owner_id == user.id
    )

    # Join with subqueries
    query = query.outerjoin(
        memory_counts,
        App.id == memory_counts.c.app_id
    ).outerjoin(
        access_counts,
        App.id == access_counts.c.app_id
    )

    if name:
        query = query.filter(App.name.ilike(f"%{name}%"))

    if is_active is not None:
        query = query.filter(App.is_active == is_active)

    # Apply sorting
    if sort_by == 'name':
        sort_field = App.name
    elif sort_by == 'memories':
        sort_field = func.coalesce(memory_counts.c.memory_count, 0)
    elif sort_by == 'memories_accessed':
        sort_field = func.coalesce(access_counts.c.access_count, 0)
    else:
        sort_field = App.name  # default sort

    if sort_direction == 'desc':
        query = query.order_by(desc(sort_field))
    else:
        query = query.order_by(sort_field)

    total = query.count()
    apps = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "apps": [
            {
                "id": app[0].id,
                "name": app[0].name,
                "is_active": app[0].is_active,
                "total_memories_created": app[1],
                "total_memories_accessed": app[2]
            }
            for app in apps
        ]
    }

# Get app details
@router.get("/{app_id}")
async def get_app_details(
    app_id: UUID,
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    获取应用的详细信息。
    
    返回内容：
    - 应用状态（是否活跃）
    - 创建的记忆总数
    - 访问的记忆总数
    - 首次访问时间
    - 最后访问时间
    
    参数:
    - app_id: 应用ID（UUID格式，必填）
    - user_id: 用户ID（查询参数，必填）
    """
    app = get_app_or_404(db, app_id, user_id)

    # Get memory access statistics
    access_stats = db.query(
        func.count(MemoryAccessLog.id).label("total_memories_accessed"),
        func.min(MemoryAccessLog.accessed_at).label("first_accessed"),
        func.max(MemoryAccessLog.accessed_at).label("last_accessed")
    ).filter(MemoryAccessLog.app_id == app_id).first()

    return {
        "is_active": app.is_active,
        "total_memories_created": db.query(Memory)
            .filter(Memory.app_id == app_id)
            .count(),
        "total_memories_accessed": access_stats.total_memories_accessed or 0,
        "first_accessed": access_stats.first_accessed,
        "last_accessed": access_stats.last_accessed
    }

# List memories created by app
@router.get("/{app_id}/memories")
async def list_app_memories(
    app_id: UUID,
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    获取指定应用创建的所有记忆。
    
    功能说明：
    - 返回该应用创建的所有记忆
    - 包括活跃、暂停、归档状态的记忆
    - 支持分页查询
    - 按创建时间倒序排列
    
    参数:
    - app_id: 应用ID（必填）
    - user_id: 用户ID（查询参数，必填）
    - page: 页码（默认1）
    - page_size: 每页数量（默认10，最大100）
    """
    app = get_app_or_404(db, app_id, user_id)
    user = get_or_create_user(db, user_id)
    query = db.query(Memory).filter(
        Memory.app_id == app_id,
        Memory.user_id == user.id,
        Memory.state.in_([MemoryState.active, MemoryState.paused, MemoryState.archived])
    )
    # Add eager loading for categories
    query = query.options(joinedload(Memory.categories))
    total = query.count()
    memories = query.order_by(Memory.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "memories": [
            {
                "id": memory.id,
                "content": memory.content,
                "created_at": memory.created_at,
                "state": memory.state.value,
                "app_id": memory.app_id,
                "categories": [category.name for category in memory.categories],
                "metadata_": memory.metadata_
            }
            for memory in memories
        ]
    }

# List memories accessed by app
@router.get("/{app_id}/accessed")
async def list_app_accessed_memories(
    app_id: UUID,
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    获取指定应用访问过的所有记忆。
    
    功能说明：
    - 返回该应用访问过的所有记忆
    - 按访问次数排序
    - 显示每个记忆的访问次数
    - 支持分页查询
    
    参数:
    - app_id: 应用ID（必填）
    - user_id: 用户ID（查询参数，必填）
    - page: 页码（默认1）
    - page_size: 每页数量（默认10，最大100）
    
    返回内容：
    - 记忆列表（包含访问次数）
    - 按访问次数从高到低排序
    """
    app = get_app_or_404(db, app_id, user_id)
    user = get_or_create_user(db, user_id)
    
    # Get memories with access counts (filtered by user)
    query = db.query(
        Memory,
        func.count(MemoryAccessLog.id).label("access_count")
    ).join(
        MemoryAccessLog,
        Memory.id == MemoryAccessLog.memory_id
    ).filter(
        MemoryAccessLog.app_id == app_id,
        Memory.user_id == user.id
    ).group_by(
        Memory.id
    ).order_by(
        desc("access_count")
    )

    # Add eager loading for categories
    query = query.options(joinedload(Memory.categories))

    total = query.count()
    results = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "memories": [
            {
                "memory": {
                    "id": memory.id,
                    "content": memory.content,
                    "created_at": memory.created_at,
                    "state": memory.state.value,
                    "app_id": memory.app_id,
                    "app_name": memory.app.name if memory.app else None,
                    "categories": [category.name for category in memory.categories],
                    "metadata_": memory.metadata_
                },
                "access_count": count
            }
            for memory, count in results
        ]
    }


@router.put("/{app_id}")
async def update_app_details(
    app_id: UUID,
    user_id: str,
    is_active: bool,
    db: Session = Depends(get_db)
):
    """
    更新应用的状态（活跃/暂停）。
    
    功能说明：
    - 可以暂停或激活应用
    - 暂停的应用无法创建新记忆
    - 暂停的应用创建的记忆不会被查询返回
    
    参数:
    - app_id: 应用ID（必填）
    - user_id: 用户ID（查询参数，必填）
    - is_active: 是否活跃（查询参数，必填，true/false）
    
    使用场景：
    - 临时禁用某个应用
    - 管理应用的访问权限
    """
    app = get_app_or_404(db, app_id, user_id)
    app.is_active = is_active
    db.commit()
    return {"status": "success", "message": "Updated app details successfully"}
