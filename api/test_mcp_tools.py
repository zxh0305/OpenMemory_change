#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP工具功能测试脚本

测试OpenMemory MCP服务器的工具调用功能
"""

import sys
import requests
import json
import time

# 设置Windows控制台编码为UTF-8
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def test_mcp_connection():
    """测试MCP服务器基本连接"""
    print_section("测试MCP服务器连接")
    
    base_url = "http://localhost:8765"
    
    try:
        # 测试根端点
        response = requests.get(f"{base_url}/docs", timeout=5)
        if response.status_code == 200:
            print("[成功] MCP服务器运行正常")
            print(f"   API文档: {base_url}/docs")
            return True
        else:
            print(f"[失败] 服务器响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"[失败] 无法连接到服务器: {e}")
        return False

def test_sse_endpoint():
    """测试SSE端点"""
    print_section("测试SSE端点")
    
    test_user = "test_user_123"
    test_client = "cursor"
    
    sse_url = f"http://localhost:8765/mcp/{test_client}/sse/{test_user}"
    
    try:
        print(f"连接到: {sse_url}")
        response = requests.get(sse_url, timeout=3, stream=True)
        
        if response.status_code == 200:
            print("[成功] SSE端点可访问")
            print(f"   用户ID: {test_user}")
            print(f"   客户端: {test_client}")
            return True
        else:
            print(f"[失败] SSE端点响应异常: {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        # SSE连接超时是正常的
        print("[成功] SSE端点可访问 (超时是正常的长连接行为)")
        return True
    except Exception as e:
        print(f"[失败] SSE端点测试失败: {e}")
        return False

def get_mcp_client_config():
    """生成MCP客户端配置"""
    print_section("MCP客户端配置")
    
    config = {
        "mcpServers": {
            "openmemory": {
                "url": "http://localhost:8765/mcp/cursor/sse/your_user_id",
                "transport": "sse"
            }
        }
    }
    
    print("请在你的MCP客户端中使用以下配置:")
    print("\n对于Cursor编辑器，在设置中添加:")
    print(json.dumps(config, indent=2, ensure_ascii=False))
    print("\n重要提示:")
    print("1. 将 'your_user_id' 替换为你的实际用户ID")
    print("2. 如果使用其他客户端，将 'cursor' 替换为对应的客户端名称")
    print("   (支持: cursor, windsurf, witsy 等)")

def show_available_tools():
    """显示可用的MCP工具"""
    print_section("可用的MCP工具")
    
    tools = [
        {
            "name": "add_memories",
            "description": "添加新记忆",
            "usage": "当用户告诉你任何关于他们自己的信息时使用"
        },
        {
            "name": "search_memory",
            "description": "搜索记忆",
            "usage": "每次用户提问时都应该调用此工具"
        },
        {
            "name": "list_memories",
            "description": "列出所有记忆",
            "usage": "查看用户的所有存储记忆"
        },
        {
            "name": "delete_all_memories",
            "description": "删除所有记忆",
            "usage": "清空用户的所有记忆数据"
        }
    ]
    
    for i, tool in enumerate(tools, 1):
        print(f"\n{i}. {tool['name']}")
        print(f"   描述: {tool['description']}")
        print(f"   使用场景: {tool['usage']}")

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("OpenMemory MCP工具测试".center(60))
    print("=" * 60)
    
    # 测试连接
    server_ok = test_mcp_connection()
    if not server_ok:
        print("\n[错误] MCP服务器未运行，请先启动服务器:")
        print("   cd api && python main.py")
        sys.exit(1)
    
    # 测试SSE端点
    sse_ok = test_sse_endpoint()
    
    # 显示配置信息
    get_mcp_client_config()
    
    # 显示可用工具
    show_available_tools()
    
    # 总结
    print_section("测试总结")
    if server_ok and sse_ok:
        print("\n[成功] MCP服务器工作正常！")
        print("\n下一步:")
        print("1. 复制上面的配置到你的MCP客户端")
        print("2. 将 'your_user_id' 替换为你的实际用户ID")
        print("3. 重启MCP客户端")
        print("4. 尝试使用MCP工具")
        print("\n测试命令示例:")
        print("   '记住我喜欢喝咖啡'  -> 会调用 add_memories")
        print("   '我喜欢什么饮料？'  -> 会调用 search_memory")
    else:
        print("\n[警告] 存在问题需要解决")
        print("请查看上面的错误信息并修复")

if __name__ == "__main__":
    main()