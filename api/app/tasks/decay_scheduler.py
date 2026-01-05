"""
记忆衰退定时任务调度器

使用 APScheduler 实现定时更新记忆衰退分数和自动归档功能
"""

import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.database import SessionLocal
from app.utils.decay import (
    update_memory_decay_scores,
    auto_archive_decayed_memories,
    get_decay_statistics
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建调度器实例
scheduler = BackgroundScheduler()

# 从环境变量读取配置
DECAY_ENABLED = os.getenv("MEMORY_DECAY_ENABLED", "true").lower() == "true"
DECAY_HALF_LIFE_DAYS = int(os.getenv("MEMORY_DECAY_HALF_LIFE_DAYS", "30"))
DECAY_AUTO_ARCHIVE_THRESHOLD = float(os.getenv("MEMORY_DECAY_AUTO_ARCHIVE_THRESHOLD", "0.1"))
DECAY_UPDATE_HOUR = int(os.getenv("MEMORY_DECAY_UPDATE_HOUR", "2"))  # 默认凌晨2点
DECAY_UPDATE_MINUTE = int(os.getenv("MEMORY_DECAY_UPDATE_MINUTE", "0"))


def update_decay_job():
    """
    定时更新记忆衰退分数的任务
    
    该任务会：
    1. 更新所有活跃记忆的衰退分数
    2. 自动归档衰退严重的记忆
    3. 记录统计信息
    """
    if not DECAY_ENABLED:
        logger.info("记忆衰退功能已禁用，跳过更新")
        return
    
    db = SessionLocal()
    try:
        logger.info("=" * 60)
        logger.info("开始执行记忆衰退更新任务")
        logger.info(f"配置: 半衰期={DECAY_HALF_LIFE_DAYS}天, 归档阈值={DECAY_AUTO_ARCHIVE_THRESHOLD}")
        
        # 1. 更新衰退分数
        updated_count = update_memory_decay_scores(
            db,
            batch_size=100,
            half_life_days=DECAY_HALF_LIFE_DAYS
        )
        logger.info(f"✅ 已更新 {updated_count} 条记忆的衰退分数")
        
        # 2. 自动归档衰退严重的记忆
        archived_count = auto_archive_decayed_memories(
            db,
            threshold=DECAY_AUTO_ARCHIVE_THRESHOLD,
            batch_size=100
        )
        logger.info(f"✅ 已自动归档 {archived_count} 条衰退记忆")
        
        # 3. 获取统计信息
        stats = get_decay_statistics(db)
        logger.info("📊 衰退统计:")
        logger.info(f"   总记忆数: {stats['total_memories']}")
        logger.info(f"   平均衰退分数: {stats['average_decay_score']}")
        logger.info(f"   新鲜记忆 (≥0.7): {stats['high_decay_count']}")
        logger.info(f"   中等衰退 (0.3-0.7): {stats['medium_decay_count']}")
        logger.info(f"   严重衰退 (<0.3): {stats['low_decay_count']}")
        
        logger.info("记忆衰退更新任务完成")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ 记忆衰退更新任务失败: {e}", exc_info=True)
    finally:
        db.close()


def start_decay_scheduler():
    """
    启动记忆衰退调度器
    
    根据配置决定是否启用衰退功能，并设置定时任务
    """
    if not DECAY_ENABLED:
        logger.info("⚠️  记忆衰退功能已禁用（MEMORY_DECAY_ENABLED=false）")
        return
    
    try:
        # 添加定时任务：每天指定时间执行
        scheduler.add_job(
            update_decay_job,
            trigger=CronTrigger(hour=DECAY_UPDATE_HOUR, minute=DECAY_UPDATE_MINUTE),
            id='memory_decay_update',
            name='记忆衰退更新任务',
            replace_existing=True
        )
        
        # 启动调度器
        scheduler.start()
        
        logger.info("=" * 60)
        logger.info("🚀 记忆衰退调度器已启动")
        logger.info(f"⏰ 更新时间: 每天 {DECAY_UPDATE_HOUR:02d}:{DECAY_UPDATE_MINUTE:02d}")
        logger.info(f"📅 半衰期: {DECAY_HALF_LIFE_DAYS} 天")
        logger.info(f"📦 归档阈值: {DECAY_AUTO_ARCHIVE_THRESHOLD}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ 启动记忆衰退调度器失败: {e}", exc_info=True)


def stop_decay_scheduler():
    """
    停止记忆衰退调度器
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("记忆衰退调度器已停止")


def trigger_decay_update_now():
    """
    立即触发一次衰退更新（用于手动触发或测试）
    
    返回:
        是否成功触发
    """
    if not DECAY_ENABLED:
        logger.warning("记忆衰退功能已禁用，无法触发更新")
        return False
    
    try:
        logger.info("手动触发记忆衰退更新...")
        update_decay_job()
        return True
    except Exception as e:
        logger.error(f"手动触发衰退更新失败: {e}", exc_info=True)
        return False


def get_scheduler_status() -> dict:
    """
    获取调度器状态信息
    
    返回:
        调度器状态字典
    """
    if not DECAY_ENABLED:
        return {
            "enabled": False,
            "running": False,
            "message": "记忆衰退功能已禁用"
        }
    
    jobs = scheduler.get_jobs()
    next_run = None
    
    if jobs:
        job = jobs[0]
        next_run = job.next_run_time.isoformat() if job.next_run_time else None
    
    return {
        "enabled": True,
        "running": scheduler.running,
        "next_run_time": next_run,
        "update_schedule": f"{DECAY_UPDATE_HOUR:02d}:{DECAY_UPDATE_MINUTE:02d}",
        "half_life_days": DECAY_HALF_LIFE_DAYS,
        "archive_threshold": DECAY_AUTO_ARCHIVE_THRESHOLD,
        "jobs_count": len(jobs)
    }