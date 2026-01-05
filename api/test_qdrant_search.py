#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Qdrant搜索功能
"""

import sys
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from app.utils.memory import get_memory_client

def test_qdrant_search():
    """测试Qdrant搜索"""
    print("=" * 60)
    print("测试Qdrant搜索功能")
    print("=" * 60)
    
    try:
        # 获取内存客户端
        client = get_memory_client()
        
        # 测试查询
        queries = [
            "我的名字和年龄",
            "name and age",
            "age",
            "柳宗元"
        ]
        
        for query in queries:
            print(f"\n查询: {query}")
            print("-" * 60)
            
            try:
                # 生成嵌入
                embeddings = client.embedding_model.embed(query, "search")
                print(f"嵌入维度: {len(embeddings)}")
                
                # 不带过滤的搜索
                hits = client.vector_store.client.query_points(
                    collection_name="openmemory",
                    query=embeddings,
                    limit=5,
                )
                
                print(f"返回结果数: {len(hits.points)}")
                for i, point in enumerate(hits.points, 1):
                    print(f"  {i}. ID: {point.id}, Score: {point.score:.4f}")
                    if hasattr(point, 'payload') and 'data' in point.payload:
                        print(f"     内容: {point.payload['data'][:50]}...")
                
            except Exception as e:
                print(f"搜索失败: {e}")
        
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_qdrant_search()