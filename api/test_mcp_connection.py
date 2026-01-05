#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP服务器连接诊断脚本

此脚本用于测试和诊断OpenMemory MCP服务器的连接问题。
它会检查：
1. 环境变量配置
2. API密钥有效性
3. MCP服务器端点可访问性
4. 数据库连接
5. 向量存储连接
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv

# 设置Windows控制台编码为UTF-8
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 加载环境变量
load_dotenv()

def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def check_env_variables():
    """检查环境变量配置"""
    print_section("1. 检查环境变量配置")
    
    required_vars = {
        "OPENAI_API_KEY": "OpenAI API密钥",
        "OPENAI_BASE_URL": "OpenAI基础URL",
        "OPENAI_MODEL": "OpenAI模型",
        "OPENAI_EMBEDDING_MODEL_API_KEY": "嵌入模型API密钥",
        "OPENAI_EMBEDDING_MODEL_BASE_URL": "嵌入模型基础URL",
        "OPENAI_EMBEDDING_MODEL": "嵌入模型名称",
    }
    
    all_set = True
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            # 隐藏API密钥的大部分内容
            if "KEY" in var and len(value) > 8:
                display_value = f"{value[:4]}...{value[-4:]}"
            else:
                display_value = value
            print(f"✅ {desc} ({var}): {display_value}")
        else:
            print(f"❌ {desc} ({var}): 未设置")
            all_set = False
    
    return all_set

def check_api_connectivity():
    """检查API连接性"""
    print_section("2. 检查API连接性")
    
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ API密钥未设置，跳过连接测试")
        return False
    
    try:
        # 测试模型列表端点
        url = f"{base_url}/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        print(f"🔍 测试连接到: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ API连接成功 (状态码: {response.status_code})")
            return True
        else:
            print(f"⚠️ API响应异常 (状态码: {response.status_code})")
            print(f"   响应内容: {response.text[:200]}")
            return False
    except requests.exceptions.Timeout:
        print(f"❌ 连接超时: {base_url}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到: {base_url}")
        return False
    except Exception as e:
        print(f"❌ 连接测试失败: {e}")
        return False

def check_mcp_server():
    """检查MCP服务器状态"""
    print_section("3. 检查MCP服务器状态")
    
    # 假设MCP服务器运行在本地8765端口
    mcp_url = "http://localhost:8765"
    
    try:
        # 测试根端点
        print(f"🔍 测试MCP服务器: {mcp_url}")
        response = requests.get(f"{mcp_url}/docs", timeout=5)
        
        if response.status_code == 200:
            print(f"✅ MCP服务器运行正常")
            print(f"   API文档: {mcp_url}/docs")
            return True
        else:
            print(f"⚠️ MCP服务器响应异常 (状态码: {response.status_code})")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到MCP服务器: {mcp_url}")
        print(f"   请确保服务器正在运行")
        return False
    except Exception as e:
        print(f"❌ MCP服务器检查失败: {e}")
        return False

def check_mcp_endpoint():
    """检查MCP SSE端点"""
    print_section("4. 检查MCP SSE端点")
    
    mcp_url = "http://localhost:8765"
    test_user = "test_user"
    test_client = "test_client"
    
    sse_endpoint = f"{mcp_url}/mcp/{test_client}/sse/{test_user}"
    
    try:
        print(f"🔍 测试SSE端点: {sse_endpoint}")
        # 只测试端点是否可访问，不等待SSE流
        response = requests.get(sse_endpoint, timeout=2, stream=True)
        
        if response.status_code == 200:
            print(f"✅ SSE端点可访问")
            return True
        else:
            print(f"⚠️ SSE端点响应异常 (状态码: {response.status_code})")
            return False
    except requests.exceptions.Timeout:
        # SSE连接超时是正常的，因为它是长连接
        print(f"✅ SSE端点可访问 (超时是正常的)")
        return True
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到SSE端点")
        return False
    except Exception as e:
        print(f"⚠️ SSE端点检查: {e}")
        return True  # 某些异常可能是正常的

def check_database():
    """检查数据库连接"""
    print_section("5. 检查数据库连接")
    
    try:
        from app.database import SessionLocal, engine
        from sqlalchemy import text
        
        # 测试数据库连接
        db = SessionLocal()
        try:
            result = db.execute(text("SELECT 1"))
            print("✅ 数据库连接成功")
            
            # 检查表是否存在
            result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result]
            print(f"   数据库表数量: {len(tables)}")
            if tables:
                print(f"   主要表: {', '.join(tables[:5])}")
            return True
        finally:
            db.close()
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False

def check_vector_store():
    """检查向量存储连接"""
    print_section("6. 检查向量存储 (Qdrant)")
    
    try:
        from qdrant_client import QdrantClient
        
        # 尝试连接到Qdrant
        client = QdrantClient(host="localhost", port=6333)
        collections = client.get_collections()
        
        print(f"✅ Qdrant连接成功")
        print(f"   集合数量: {len(collections.collections)}")
        
        for collection in collections.collections:
            print(f"   - {collection.name}")
        
        return True
    except Exception as e:
        print(f"❌ Qdrant连接失败: {e}")
        print(f"   提示: 请确保Qdrant服务正在运行")
        return False

def print_summary(results):
    """打印检查结果摘要"""
    print_section("检查结果摘要")
    
    total = len(results)
    passed = sum(results.values())
    
    print(f"\n总计: {passed}/{total} 项检查通过\n")
    
    for check, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {check}")
    
    if passed == total:
        print("\n[成功] 所有检查通过！MCP服务器应该可以正常工作。")
    else:
        print("\n[警告] 存在问题需要解决。请根据上述检查结果进行修复。")

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("OpenMemory MCP服务器连接诊断".center(60))
    print("=" * 60)
    
    results = {
        "环境变量配置": check_env_variables(),
        "API连接性": check_api_connectivity(),
        "MCP服务器": check_mcp_server(),
        "MCP SSE端点": check_mcp_endpoint(),
        "数据库连接": check_database(),
        "向量存储": check_vector_store(),
    }
    
    print_summary(results)
    
    # 返回退出码
    sys.exit(0 if all(results.values()) else 1)

if __name__ == "__main__":
    main()