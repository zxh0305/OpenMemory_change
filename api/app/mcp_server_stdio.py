#!/usr/bin/env python3
"""
MCP Server stdio entry point for direct client communication

This module provides a stdio-based entry point for the MCP server,
which is more reliable than SSE for most MCP clients.

Usage:
    python -m app.mcp_server_stdio

Or with Docker:
    docker exec -i openmemory-api python -m app.mcp_server_stdio
"""

import asyncio
import sys
import logging
import os

# 配置日志输出到stderr，避免干扰stdio通信
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)

logger = logging.getLogger(__name__)

# 确保当前目录在Python路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app.mcp_server import mcp

async def main():
    """Run MCP server with stdio transport"""
    try:
        logger.info("=" * 60)
        logger.info("Starting OpenMemory MCP Server (stdio transport)")
        logger.info("=" * 60)
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Available tools: {len(mcp._mcp_server._tools)}")
        
        # 列出可用工具
        for tool_name in mcp._mcp_server._tools.keys():
            logger.info(f"  - {tool_name}")
        
        logger.info("=" * 60)
        logger.info("MCP Server ready, waiting for client connection...")
        logger.info("=" * 60)
        
        # 运行MCP服务器（stdio模式）
        await mcp.run()
        
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
    except Exception as e:
        logger.error(f"Error running MCP server: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)