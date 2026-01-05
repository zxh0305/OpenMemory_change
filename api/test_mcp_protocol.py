#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试MCP协议握手
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

def test_mcp_initialization():
    """测试MCP初始化握手"""
    print("=" * 60)
    print("测试MCP协议初始化")
    print("=" * 60)
    
    # 第1步：建立SSE连接
    sse_url = "http://localhost:8765/mcp/openmemory/sse/user"
    print(f"\n步骤1: 连接SSE端点")
    print(f"URL: {sse_url}")
    
    try:
        response = requests.get(sse_url, stream=True, timeout=3)
        print(f"状态码: {response.status_code}")
        
        if response.status_code != 200:
            print("[失败] SSE连接失败")
            return False
        
        print("[成功] SSE连接建立")
        
        # 第2步：读取SSE事件
        print(f"\n步骤2: 读取SSE事件")
        print("-" * 60)
        
        session_id = None
        message_endpoint = None
        
        for line in response.iter_lines(decode_unicode=True):
            if line:
                print(f"  {line}")
                
                # 解析endpoint事件
                if line.startswith("data: /mcp/messages"):
                    message_endpoint = line.split("data: ")[1]
                    # 提取session_id
                    if "session_id=" in message_endpoint:
                        session_id = message_endpoint.split("session_id=")[1]
                    print(f"\n[发现] 消息端点: {message_endpoint}")
                    print(f"[发现] Session ID: {session_id}")
                    break
            
            # 超时保护
            time.sleep(0.1)
        
        print("-" * 60)
        
        if not message_endpoint:
            print("\n[失败] 未收到消息端点信息")
            return False
        
        # 第3步：发送初始化请求
        print(f"\n步骤3: 发送MCP初始化请求")
        
        init_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        full_url = f"http://localhost:8765{message_endpoint}"
        print(f"POST到: {full_url}")
        print(f"消息: {json.dumps(init_message, indent=2)}")
        
        msg_response = requests.post(
            full_url,
            json=init_message,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        print(f"\n响应状态码: {msg_response.status_code}")
        print(f"响应内容: {msg_response.text}")
        
        if msg_response.status_code == 200:
            print("\n[成功] MCP初始化请求已发送")
            
            try:
                response_data = msg_response.json()
                print(f"解析后的响应: {json.dumps(response_data, indent=2)}")
                return True
            except:
                print("[警告] 响应不是JSON格式")
                return False
        else:
            print(f"\n[失败] 初始化请求失败")
            return False
            
    except requests.exceptions.Timeout:
        print("\n[超时] 连接超时")
        print("\n可能的原因:")
        print("  1. MCP服务器没有发送初始化消息")
        print("  2. SSE流在endpoint事件后停止")
        print("  3. 服务器等待客户端发送消息但客户端在等待服务器")
        return False
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("MCP协议测试".center(60))
    print("=" * 60)
    
    result = test_mcp_initialization()
    
    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)
    
    if result:
        print("\n[成功] MCP协议握手成功")
    else:
        print("\n[失败] MCP协议握手失败")
        print("\n建议:")
        print("  1. 检查MCP服务器是否正确实现了协议")
        print("  2. 查看服务器日志了解详细错误")
        print("  3. 确认FastMCP版本与客户端兼容")

if __name__ == "__main__":
    main()