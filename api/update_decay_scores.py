#!/usr/bin/env python3
"""
直接更新所有记忆的衰退分数
"""
import sys
import datetime
import math
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 数据库连接
DATABASE_URL = "sqlite:///./openmemory.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def calculate_decay_score(created_at, half_life_days=30):
    """计算衰退分数"""
    now = datetime.datetime.now(datetime.UTC)
    
    # 确保 created_at 有时区信息
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=datetime.UTC)
    
    days_since_creation = (now - created_at).days
    
    if days_since_creation <= 0:
        return 1.0
    
    # 指数衰减公式: score = 0.5^(days / half_life)
    decay_score = math.pow(0.5, days_since_creation / half_life_days)
    return max(0.0, min(1.0, decay_score))

def update_all_decay_scores():
    """更新所有记忆的衰退分数"""
    db = SessionLocal()
    
    try:
        print("=" * 60)
        print("🔄 开始更新记忆衰退分数...")
        print("=" * 60)
        
        # 查询所有活跃记忆
        result = db.execute(text("""
            SELECT id, created_at, decay_score
            FROM memories
            WHERE state = 'active'
        """))
        
        memories = result.fetchall()
        print(f"📊 找到 {len(memories)} 条活跃记忆")
        
        updated_count = 0
        for memory in memories:
            memory_id, created_at_str, old_decay_score = memory
            
            # 解析创建时间
            try:
                # 尝试多种时间格式
                for fmt in [
                    "%Y-%m-%d %H:%M:%S.%f",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f",
                    "%Y-%m-%dT%H:%M:%S"
                ]:
                    try:
                        created_at = datetime.datetime.strptime(created_at_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    # 如果所有格式都失败，尝试 fromisoformat
                    created_at = datetime.datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                
                # 计算新的衰退分数
                new_decay_score = calculate_decay_score(created_at, half_life_days=30)
                
                # 更新数据库
                # 更新数据库
                db.execute(
                    text("""
                        UPDATE memories
                        SET decay_score = :decay_score,
                            updated_at = :updated_at
                        WHERE id = :memory_id
                    """),
                    {
                        "decay_score": new_decay_score,
                        "updated_at": datetime.datetime.now(datetime.UTC),
                        "memory_id": memory_id
                    }
                )
                updated_count += 1
                
                # 显示更新信息
                days_old = (datetime.datetime.now(datetime.UTC) - created_at.replace(tzinfo=datetime.UTC)).days
                print(f"  ✅ {memory_id[:8]}... | {days_old}天前 | {old_decay_score:.2f} → {new_decay_score:.2f}")
                
            except Exception as e:
                print(f"  ❌ 处理记忆 {memory_id} 失败: {e}")
        
        # 提交更改
        db.commit()
        
        print("=" * 60)
        print(f"✅ 更新完成！共更新 {updated_count} 条记忆")
        print("=" * 60)
        # 显示统计信息
        result = db.execute(text("""
            SELECT
                COUNT(*) as total,
                AVG(decay_score) as avg_score,
                MIN(decay_score) as min_score,
                MAX(decay_score) as max_score
            FROM memories
            WHERE state = 'active'
        """))
        
        stats = result.fetchone()
        print(f"📊 统计信息:")
        print(f"   总记忆数: {stats[0]}")
        print(f"   平均衰退分数: {stats[1]:.3f}")
        print(f"   最低分数: {stats[2]:.3f}")
        print(f"   最高分数: {stats[3]:.3f}")
        
        return True
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = update_all_decay_scores()
    sys.exit(0 if success else 1)