#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重建Qdrant向量存储

由于向量维度不匹配导致Qdrant损坏，需要重建集合
"""

import sys
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from app.utils.memory import get_memory_client
from app.database import SessionLocal
from app.models import Memory
from qdrant_client import models

def rebuild_qdrant():
    """重建Qdrant集合"""
    print("=" * 60)
    print("重建Qdrant向量存储")
    print("=" * 60)
    
    try:
        # 获取内存客户端
        client = get_memory_client()
        
        # 删除旧集合
        print("\n步骤1: 删除旧集合...")
        try:
            client.vector_store.client.delete_collection("openmemory")
            print("✅ 旧集合已删除")
        except Exception as e:
            print(f"⚠️ 删除旧集合失败（可能不存在）: {e}")
        
        # 创建新集合
        print("\n步骤2: 创建新集合（1024维）...")
        client.vector_store.client.create_collection(
            collection_name="openmemory",
            vectors_config=models.VectorParams(
                size=1024,  # BAAI/bge-large-zh-v1.5的维度
                distance=models.Distance.COSINE
            )
        )
        print("✅ 新集合已创建")
        
        # 从MySQL重新索引所有记忆
        print("\n步骤3: 从MySQL重新索引记忆...")
        db = SessionLocal()
        try:
            memories = db.query(Memory).filter(Memory.state == 'active').all()
            print(f"找到 {len(memories)} 条活跃记忆")
            
            success_count = 0
            points = []
            
            for i, memory in enumerate(memories, 1):
                try:
                    print(f"  处理 {i}/{len(memories)}: {memory.content[:50]}...")
                    
                    # 生成嵌入向量
                    # 生成嵌入向量
                    embeddings = client.embedding_model.embed(memory.content, "add")
                    
                    # 将32位十六进制ID转换为标准UUID格式（带连字符）
                    # MySQL: c4c7a0fc9c6648418dfd823550b92e87
                    # UUID:  c4c7a0fc-9c66-4841-8dfd-823550b92e87
                    memory_id_hex = str(memory.id)
                    if len(memory_id_hex) == 32 and '-' not in memory_id_hex:
                        # 转换为标准UUID格式
                        memory_id_uuid = f"{memory_id_hex[:8]}-{memory_id_hex[8:12]}-{memory_id_hex[12:16]}-{memory_id_hex[16:20]}-{memory_id_hex[20:]}"
                    else:
                        memory_id_uuid = memory_id_hex
                    
                    print(f"    MySQL ID: {memory_id_hex} -> UUID: {memory_id_uuid}")
                    
                    # 使用转换后的UUID格式
                    point = models.PointStruct(
                        id=memory_id_uuid,
                        vector=embeddings,
                        payload={
                            "data": memory.content,
                            "user_id": str(memory.user_id),
                            "hash": getattr(memory, 'hash', None),
                            "created_at": memory.created_at.isoformat() if memory.created_at else None,
                            "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
                        }
                    )
                    points.append(point)
                    success_count += 1
                except Exception as e:
                    print(f"    ❌ 失败: {e}")
            
            # 批量插入所有点
            if points:
                print(f"\n批量插入 {len(points)} 个向量...")
                client.vector_store.client.upsert(
                    collection_name="openmemory",
                    points=points
                )
            
            print(f"\n✅ 成功重新索引 {success_count}/{len(memories)} 条记忆")
            
        finally:
            db.close()
        
        # 验证
        print("\n步骤4: 验证重建结果...")
        count = client.vector_store.client.count("openmemory")
        print(f"✅ Qdrant中现有 {count.count} 个向量")
        
        # 测试搜索
        print("\n步骤5: 测试搜索...")
        test_queries = ["age", "name", "柳宗元"]
        for query in test_queries:
            try:
                embeddings = client.embedding_model.embed(query, "search")
                hits = client.vector_store.client.query_points(
                    collection_name="openmemory",
                    query=embeddings,
                    limit=3,
                )
                print(f"  查询'{query}': 返回 {len(hits.points)} 个结果")
            except Exception as e:
                print(f"  查询'{query}': 失败 - {e}")
        
        print("\n" + "=" * 60)
        print("✅ 重建完成！")
        print("=" * 60)
        print("\n现在可以正常使用MCP搜索功能了。")
        
    except Exception as e:
        print(f"\n❌ 重建失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    rebuild_qdrant()