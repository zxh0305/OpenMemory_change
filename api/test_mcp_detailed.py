#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细的MCP连接测试脚本
用于诊断MCP协议超时问题
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

def test_sse_connection():
    """测试SSE连接并查看响应"""
    print("=" * 60)
    print("测试SSE连接")
    print("=" * 60)
    
    url = "http://localhost:8765/mcp/openmemory/sse/user"
    
    try:
        print(f"\n连接到: {url}")
        print("等待SSE响应...")
        
        response = requests.get(url, stream=True, timeout=10)
        
        print(f"\n状态码: {response.status_code}")
        print(f"响应头:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        print(f"\n接收SSE数据流 (前5秒):")
        print("-" * 60)
        
        start_time = time.time()
        for line in response.iter_lines(decode_unicode=True):
            if line:
                print(f"  {line}")
            
            # 只读取5秒的数据
            if time.time() - start_time > 5:
                print("\n[5秒后停止读取]")
                break
        
        print("-" * 60)
        print("\n[成功] SSE连接正常，数据流正常")
        return True
        
    except requests.exceptions.Timeout:
        print("\n[超时] 连接超时")
        print("这可能表示:")
        print("  1. 服务器没有发送初始化消息")
        print("  2. MCP协议握手失败")
        print("  3. SSE流没有正确建立")
        return False
    except Exception as e:
        print(f"\n[错误] {e}")
        return False

def test_messages_endpoint():
    """测试消息端点"""
    print("\n" + "=" * 60)
    print("测试消息端点")
    print("=" * 60)
    
    url = "http://localhost:8765/mcp/messages"
    
    try:
        print(f"\n发送POST请求到: {url}")
        response = requests.post(url, json={"test": "data"}, timeout=5)
        
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")
        
        if response.status_code == 200:
            print("\n[成功] 消息端点可访问")
            return True
        else:
            print(f"\n[警告] 消息端点返回非200状态码")
            return False
            
    except Exception as e:
        print(f"\n[错误] {e}")
        return False

def check_docker_logs():
    """检查Docker日志"""
    print("\n" + "=" * 60)
    print("检查Docker日志")
    print("=" * 60)
    
    import subprocess
    
    try:
        result = subprocess.run(
            ["docker-compose", "logs", "--tail=30", "openmemory-api"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        print("\n最近的日志:")
        print("-" * 60)
        print(result.stdout)
        print("-" * 60)
        
        # 检查是否有错误
        if "ERROR" in result.stdout or "Error" in result.stdout:
            print("\n[警告] 日志中发现错误信息")
            return False
        else:
            print("\n[成功] 日志看起来正常")
            return True
            
    except Exception as e:
        print(f"\n[错误] 无法获取Docker日志: {e}")
        return False

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("MCP连接详细诊断".center(60))
    print("=" * 60)
    
    results = {}
    
    # 测试消息端点
    results["消息端点"] = test_messages_endpoint()
    
    # 测试SSE连接
    results["SSE连接"] = test_sse_connection()
    
    # 检查Docker日志
    results["Docker日志"] = check_docker_logs()
    
    # 总结
    print("\n" + "=" * 60)
    print("诊断结果总结")
    print("=" * 60)
    
    for test, result in results.items():
        status = "[成功]" if result else "[失败]"
        print(f"{status} {test}")
    
    if all(results.values()):
        print("\n[结论] 所有测试通过，MCP服务器工作正常")
        print("\n如果客户端仍然超时，问题可能在于:")
        print("  1. 客户端配置不正确")
        print("  2. 客户端与服务器的MCP协议版本不兼容")
        print("  3. 网络防火墙阻止了连接")
    else:
        print("\n[结论] 发现问题，请查看上面的详细信息")

if __name__ == "__main__":
    main()