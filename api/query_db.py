#!/usr/bin/env python3
"""
数据库查询工具 - 用于查看记忆数据
使用方法: docker exec openmemory-api python query_db.py [命令]
"""
import sqlite3
import sys
from datetime import datetime

def connect_db():
    """连接数据库"""
    return sqlite3.connect('openmemory.db')

def show_tables():
    """显示所有表"""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    print("\n📋 数据库表列表:")
    print("=" * 60)
    for row in cursor.fetchall():
        print(f"  • {row[0]}")
    conn.close()

def show_schema(table_name='memories'):
    """显示表结构"""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    print(f"\n📊 表结构: {table_name}")
    print("=" * 80)
    print(f"{'列名':<25} {'类型':<15} {'非空':<8} {'默认值':<15}")
    print("-" * 80)
    for row in cursor.fetchall():
        cid, name, type_, notnull, default, pk = row
        print(f"{name:<25} {type_:<15} {'是' if notnull else '否':<8} {str(default):<15}")
    conn.close()

def show_stats():
    """显示统计信息"""
    conn = connect_db()
    cursor = conn.cursor()
    
    # 活跃记忆统计
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            AVG(decay_score) as avg_decay,
            MIN(decay_score) as min_decay,
            MAX(decay_score) as max_decay,
            AVG(access_count) as avg_access
        FROM memories 
        WHERE state = 'active'
    """)
    
    row = cursor.fetchone()
    if row and row[0] > 0:
        total, avg_decay, min_decay, max_decay, avg_access = row
        print("\n📊 记忆统计")
        print("=" * 60)
        print(f"总记忆数: {total}")
        print(f"平均衰退分数: {avg_decay*100:.1f}%")
        print(f"最低衰退分数: {min_decay*100:.1f}%")
        print(f"最高衰退分数: {max_decay*100:.1f}%")
        print(f"平均访问次数: {avg_access:.1f}")
    else:
        print("\n⚠️  没有找到活跃记忆")
    
    # 归档记忆统计
    cursor.execute("SELECT COUNT(*) FROM archived_memories")
    archived_count = cursor.fetchone()[0]
    print(f"已归档记忆: {archived_count}")
    
    conn.close()

def show_memories(limit=10):
    """显示记忆列表"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            id,
            content,
            decay_score,
            importance_score,
            access_count,
            created_at,
            last_accessed_at
        FROM memories 
        WHERE state = 'active'
        ORDER BY decay_score ASC
        LIMIT ?
    """, (limit,))
    
    print(f"\n💾 活跃记忆列表 (前 {limit} 条，按衰退分数排序)")
    print("=" * 100)
    
    for row in cursor.fetchall():
        memory_id, content, decay, importance, access, created, last_access = row
        
        # 截断内容
        short_content = content[:60] + "..." if len(content) > 60 else content
        
        # 计算天数
        try:
            created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            days_old = (datetime.now() - created_dt.replace(tzinfo=None)).days
        except:
            days_old = 0
        
        # 衰退状态
        if decay >= 0.7:
            status = "🟢"
        elif decay >= 0.3:
            status = "🟠"
        else:
            status = "🔴"
        
        print(f"\n{status} ID: {memory_id[:12]}...")
        print(f"   内容: {short_content}")
        print(f"   衰退: {decay*100:.1f}% | 重要性: {importance*100:.1f}% | 访问: {access}次 | 创建: {days_old}天前")
        print("-" * 100)
    
    conn.close()

def show_archived(limit=10):
    """显示归档记忆"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            id,
            content,
            decay_score_at_archive,
            archived_at
        FROM archived_memories 
        ORDER BY archived_at DESC
        LIMIT ?
    """, (limit,))
    
    print(f"\n📦 已归档记忆 (最近 {limit} 条)")
    print("=" * 100)
    
    rows = cursor.fetchall()
    if not rows:
        print("  暂无归档记忆")
    else:
        for row in rows:
            memory_id, content, decay, archived = row
            short_content = content[:60] + "..." if len(content) > 60 else content
            
            print(f"\n🔴 ID: {memory_id[:12]}...")
            print(f"   内容: {short_content}")
            print(f"   归档时衰退分数: {decay*100:.1f}%")
            print(f"   归档时间: {archived}")
            print("-" * 100)
    
    conn.close()

def show_decay_distribution():
    """显示衰退分数分布"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            CASE 
                WHEN decay_score >= 0.7 THEN '🟢 新鲜 (≥70%)'
                WHEN decay_score >= 0.3 THEN '🟠 中等 (30-70%)'
                ELSE '🔴 严重 (<30%)'
            END as status,
            COUNT(*) as count,
            AVG(decay_score) as avg_score
        FROM memories
        WHERE state = 'active'
        GROUP BY status
        ORDER BY avg_score DESC
    """)
    
    print("\n📈 衰退分数分布")
    print("=" * 60)
    print(f"{'状态':<20} {'数量':<10} {'平均分数':<15}")
    print("-" * 60)
    
    for row in cursor.fetchall():
        status, count, avg = row
        print(f"{status:<20} {count:<10} {avg*100:.1f}%")
    
    conn.close()

def custom_query(sql):
    """执行自定义 SQL 查询"""
    conn = connect_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        # 获取列名
        if cursor.description:
            columns = [desc[0] for desc in cursor.description]
            print("\n查询结果:")
            print("=" * 100)
            print(" | ".join(columns))
            print("-" * 100)
            
            for row in rows:
                print(" | ".join(str(val) for val in row))
        else:
            print("查询执行成功")
            
    except Exception as e:
        print(f"❌ 查询错误: {e}")
    finally:
        conn.close()

def show_help():
    """显示帮助信息"""
    print("""
🔍 数据库查询工具使用指南

基本命令:
  docker exec openmemory-api python query_db.py [命令]

可用命令:
  tables          - 显示所有表
  schema [表名]   - 显示表结构 (默认: memories)
  stats           - 显示统计信息
  memories [数量] - 显示记忆列表 (默认: 10条)
  archived [数量] - 显示归档记忆 (默认: 10条)
  distribution    - 显示衰退分数分布
  sql "查询语句"  - 执行自定义SQL查询
  help            - 显示此帮助信息

示例:
  docker exec openmemory-api python query_db.py stats
  docker exec openmemory-api python query_db.py memories 20
  docker exec openmemory-api python query_db.py sql "SELECT * FROM users"
""")

def main():
    """主函数"""
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == 'tables':
        show_tables()
    elif command == 'schema':
        table = sys.argv[2] if len(sys.argv) > 2 else 'memories'
        show_schema(table)
    elif command == 'stats':
        show_stats()
    elif command == 'memories':
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        show_memories(limit)
    elif command == 'archived':
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        show_archived(limit)
    elif command == 'distribution':
        show_decay_distribution()
    elif command == 'sql':
        if len(sys.argv) < 3:
            print("❌ 请提供 SQL 查询语句")
            return
        custom_query(sys.argv[2])
    elif command == 'help':
        show_help()
    else:
        print(f"❌ 未知命令: {command}")
        show_help()

if __name__ == '__main__':
    main()