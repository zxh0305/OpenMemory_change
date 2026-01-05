#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修复后的搜索
"""

import sys
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from app.utils.memory import get_memory_client
from app.database import SessionLocal
from app.models import Memory
from app.utils.db import get_user_and_app
from qdrant_client import models as qdrant_models

def test_search():
    """测试搜索"""
    print("=" * 60)
    print("测试修复后的搜索")
    print("=" * 60)
    
    try:
        client = get_memory_client()
        db = SessionLocal()
        
        # 获取用户
        user, app = get_user_and_app(db, user_id="user", app_id="openmemory")
        print(f"\n用户信息:")
        print(f"  User.user_id: {user.user_id}")
        print(f"  User.id: {user.id}")
        
        # 获取用户的记忆
        memories = db.query(Memory).filter(Memory.user_id == user.id).all()
        print(f"\nMySQL中的记忆: {len(memories)}")
        for m in memories[:3]:
            print(f"  - {m.content[:50]}")
        
        # 测试Qdrant过滤
        print(f"\n测试Qdrant过滤:")
        print(f"  使用user.id={user.id}")
        
        # 生成嵌入
        query = "我的名字和年龄"
        embeddings = client.embedding_model.embed(query, "search")
        
        # 测试1: 只用user_id过滤
        print(f"\n测试1: 只用user_id过滤")
        conditions = [qdrant_models.FieldCondition(key="user_id", match=qdrant_models.MatchValue(value=str(user.id)))]
        filters = qdrant_models.Filter(must=conditions)
        
        hits = client.vector_store.client.query_points(
            collection_name="openmemory",
            query=embeddings,
            query_filter=filters,
            limit=10,
        )
        print(f"  返回结果: {len(hits.points)}")
        for point in hits.points[:3]:
            print(f"    - Score: {point.score:.4f}, Content: {point.payload.get('data', '')[:50]}")
        
        # 测试2: 不用任何过滤
        print(f"\n测试2: 不用任何过滤")
        hits = client.vector_store.client.query_points(
            collection_name="openmemory",
            query=embeddings,
            limit=10,
        )
        print(f"  返回结果: {len(hits.points)}")
        for point in hits.points[:3]:
            print(f"    - Score: {point.score:.4f}, user_id: {point.payload.get('user_id')}, Content: {point.payload.get('data', '')[:50]}")
        
        db.close()
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_search()