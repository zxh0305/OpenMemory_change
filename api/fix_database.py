#!/usr/bin/env python3
"""
修复数据库迁移状态和添加缺失的字段
"""
import sqlite3
import sys

def fix_database():
    try:
        # 连接数据库
        conn = sqlite3.connect('openmemory.db')
        cursor = conn.cursor()
        
        print("=" * 60)
        print("🔧 开始修复数据库...")
        print("=" * 60)
        
        # 1. 检查并创建 alembic_version 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            )
        """)
        print("✅ alembic_version 表已就绪")
        
        # 2. 检查 memories 表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='memories'
        """)
        
        if cursor.fetchone():
            print("✅ memories 表存在")
            
            # 3. 检查 memories 表的列
            cursor.execute("PRAGMA table_info(memories)")
            columns = {row[1] for row in cursor.fetchall()}
            print(f"📋 当前 memories 表的列: {columns}")
            
            # 4. 添加缺失的衰退功能字段
            missing_columns = []
            
            if 'decay_score' not in columns:
                missing_columns.append('decay_score')
                cursor.execute("""
                    ALTER TABLE memories 
                    ADD COLUMN decay_score FLOAT DEFAULT 1.0
                """)
                print("✅ 添加 decay_score 字段")
            
            if 'last_accessed_at' not in columns:
                missing_columns.append('last_accessed_at')
                cursor.execute("""
                    ALTER TABLE memories 
                    ADD COLUMN last_accessed_at DATETIME
                """)
                print("✅ 添加 last_accessed_at 字段")
            
            if 'access_count' not in columns:
                missing_columns.append('access_count')
                cursor.execute("""
                    ALTER TABLE memories 
                    ADD COLUMN access_count INTEGER DEFAULT 0
                """)
                print("✅ 添加 access_count 字段")
            
            if 'importance_score' not in columns:
                missing_columns.append('importance_score')
                cursor.execute("""
                    ALTER TABLE memories 
                    ADD COLUMN importance_score FLOAT DEFAULT 0.5
                """)
                print("✅ 添加 importance_score 字段")
            
            if not missing_columns:
                print("✅ 所有衰退功能字段已存在")
            else:
                print(f"✅ 添加了缺失的字段: {', '.join(missing_columns)}")
        else:
            print("⚠️  memories 表不存在，需要运行完整迁移")
        
        # 5. 检查 archived_memories 表
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='archived_memories'
        """)
        
        if not cursor.fetchone():
            print("📦 创建 archived_memories 表...")
            cursor.execute("""
                CREATE TABLE archived_memories (
                    id VARCHAR(36) NOT NULL,
                    user_id VARCHAR(36) NOT NULL,
                    app_id VARCHAR(36),
                    content TEXT NOT NULL,
                    vector BLOB,
                    metadata TEXT,
                    state VARCHAR(20) DEFAULT 'archived',
                    created_at DATETIME,
                    updated_at DATETIME,
                    archived_at DATETIME,
                    deleted_at DATETIME,
                    decay_score FLOAT DEFAULT 0.0,
                    last_accessed_at DATETIME,
                    access_count INTEGER DEFAULT 0,
                    importance_score FLOAT DEFAULT 0.5,
                    PRIMARY KEY (id)
                )
            """)
            print("✅ archived_memories 表已创建")
        else:
            print("✅ archived_memories 表已存在")
        
        # 6. 更新 alembic 版本标记
        cursor.execute("DELETE FROM alembic_version")
        
        # 获取最新的迁移版本
        cursor.execute("""
            INSERT INTO alembic_version (version_num) 
            VALUES ('create_archived_memories_table')
        """)
        print("✅ 更新 alembic 版本标记")
        
        # 提交更改
        conn.commit()
        
        print("=" * 60)
        print("✅ 数据库修复完成！")
        print("=" * 60)
        
        # 显示统计信息
        cursor.execute("SELECT COUNT(*) FROM memories WHERE state != 'deleted'")
        memory_count = cursor.fetchone()[0]
        print(f"📊 活跃记忆数量: {memory_count}")
        
        cursor.execute("SELECT COUNT(*) FROM archived_memories")
        archived_count = cursor.fetchone()[0]
        print(f"📦 归档记忆数量: {archived_count}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = fix_database()
    sys.exit(0 if success else 1)