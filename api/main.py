import os
import datetime
import logging
from fastapi import FastAPI
from app.database import engine, Base, SessionLocal
from app.mcp_server import setup_mcp_server
from app.routers import memories_router, apps_router, stats_router, config_router
from app.routers.decay import router as decay_router
from app.routers.archived_memories import router as archived_memories_router
from fastapi_pagination import add_pagination
from fastapi.middleware.cors import CORSMiddleware
from app.models import User, App
from uuid import uuid4
from app.config import USER_ID, DEFAULT_APP_ID
from app.tasks import start_decay_scheduler, stop_decay_scheduler

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OpenMemory API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all tables (ignore if already exist)
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    # Tables may already exist, which is fine
    print(f"Note: Some tables may already exist: {e}")

# Check for USER_ID and create default user if needed (optional, controlled by env var)
# Note: This is just for convenience. The system supports multiple users and will
# automatically create users when needed via get_or_create_user().
def create_default_user():
    # Only create default user if CREATE_DEFAULT_USER is explicitly set to "true"
    create_default = os.getenv("CREATE_DEFAULT_USER", "false").lower() == "true"
    if not create_default:
        return
    
    db = SessionLocal()
    try:
        # Check if user exists
        user = db.query(User).filter(User.user_id == USER_ID).first()
        if not user:
            # Create default user
            user = User(
                id=uuid4(),
                user_id=USER_ID,
                name="Default User",
                created_at=datetime.datetime.now(datetime.UTC)
            )
            db.add(user)
            db.commit()
            print(f"Created default user: {USER_ID}")
    finally:
        db.close()


def create_default_app():
    # Only create default app if default user was created or already exists
    create_default = os.getenv("CREATE_DEFAULT_USER", "false").lower() == "true"
    if not create_default:
        return
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == USER_ID).first()
        if not user:
            return

        # Check if app already exists
        existing_app = db.query(App).filter(
            App.name == DEFAULT_APP_ID,
            App.owner_id == user.id
        ).first()

        if existing_app:
            return

        app = App(
            id=uuid4(),
            name=DEFAULT_APP_ID,
            owner_id=user.id,
            created_at=datetime.datetime.now(datetime.UTC),
            updated_at=datetime.datetime.now(datetime.UTC),
        )
        db.add(app)
        db.commit()
        print(f"Created default app: {DEFAULT_APP_ID} for user: {USER_ID}")
    finally:
        db.close()

# Create default user on startup (only if CREATE_DEFAULT_USER=true)
# Users are automatically created when needed, so this is optional
create_default_user()
create_default_app()

# Setup MCP server
setup_mcp_server(app)

# Include routers
app.include_router(memories_router)
app.include_router(apps_router)
app.include_router(stats_router)
app.include_router(config_router)
app.include_router(decay_router)  # 添加记忆衰退路由
app.include_router(archived_memories_router)  # 添加归档记忆路由

# Add pagination support
add_pagination(app)


# 应用启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动时执行的任务"""
    logger.info("=" * 60)
    logger.info("🚀 OpenMemory API 启动中...")
    logger.info("=" * 60)
    
    # 启动记忆衰退调度器
    try:
        start_decay_scheduler()
        logger.info("✅ 记忆衰退调度器启动成功")
    except Exception as e:
        logger.error(f"❌ 记忆衰退调度器启动失败: {e}")
    
    logger.info("=" * 60)
    logger.info("✅ OpenMemory API 启动完成")
    logger.info("📖 API 文档: http://localhost:8765/docs")
    logger.info("=" * 60)


# 应用关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行的清理任务"""
    logger.info("🛑 OpenMemory API 正在关闭...")
    
    # 停止记忆衰退调度器
    try:
        stop_decay_scheduler()
        logger.info("✅ 记忆衰退调度器已停止")
    except Exception as e:
        logger.error(f"❌ 停止记忆衰退调度器失败: {e}")
    
    logger.info("👋 OpenMemory API 已关闭")
