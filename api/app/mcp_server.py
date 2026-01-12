"""
MCP Server for OpenMemory with resilient memory client handling.

This module implements an MCP (Model Context Protocol) server that provides
memory operations for OpenMemory. The memory client is initialized lazily
to prevent server crashes when external dependencies (like Ollama) are
unavailable. If the memory client cannot be initialized, the server will
continue running with limited functionality and appropriate error messages.

Key features:
- Lazy memory client initialization
- Graceful error handling for unavailable dependencies
- Fallback to database-only mode when vector store is unavailable
- Proper logging for debugging connection issues
- Environment variable parsing for API keys
"""

import logging
import json
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from app.utils.memory import get_memory_client
from fastapi import FastAPI, Request
from fastapi.routing import APIRouter
import contextvars
import os
from dotenv import load_dotenv
from app.database import SessionLocal
from app.models import Memory, MemoryState, MemoryStatusHistory, MemoryAccessLog
from app.utils.db import get_user_and_app
import uuid
import datetime
from app.utils.permissions import check_memory_access_permissions
from qdrant_client import models as qdrant_models

# Load environment variables
load_dotenv()

# Initialize MCP
mcp = FastMCP("mem0-mcp-server")

# Don't initialize memory client at import time - do it lazily when needed
def get_memory_client_safe():
    """获取内存客户端的安全函数，包含错误处理。如果客户端无法初始化则返回None。"""
    try:
        return get_memory_client()
    except Exception as e:
        logging.warning(f"Failed to get memory client: {e}")
        return None

# Context variables for user_id and client_name
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id")
client_name_var: contextvars.ContextVar[str] = contextvars.ContextVar("client_name")

# Create a router for MCP endpoints
mcp_router = APIRouter(prefix="/mcp")

# Initialize SSE transport
sse = SseServerTransport("/mcp/messages/")

@mcp.tool(description="Add a new memory. This method is called everytime the user informs anything about themselves, their preferences, or anything that has any relevant information which can be useful in the future conversation. This can also be called when the user asks you to remember something.")
async def add_memories(text: str) -> str:
    """添加新记忆的工具函数
    
    Args:
        text: 要添加到记忆中的文本内容
        
    Returns:
        操作结果的字符串描述
    """
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)

    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    # 获取内存客户端，处理可能的初始化失败
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        db = SessionLocal()
        try:
            # 获取或创建用户和应用
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)

            # 检查应用是否处于活动状态
            if not app.is_active:
                return f"Error: App {app.name} is currently paused on OpenMemory. Cannot create new memories."

            # 通过内存客户端添加记忆
            response = memory_client.add(text,
                                         user_id=uid,
                                         metadata={
                                            "source_app": "openmemory",
                                            "mcp_client": client_name,
                                        })

            # 处理响应并更新数据库
            if isinstance(response, dict) and 'results' in response:
                for result in response['results']:
                    memory_id = uuid.UUID(result['id'])
                    memory = db.query(Memory).filter(Memory.id == memory_id).first()

                    if result['event'] == 'ADD':
                        # 处理添加新记忆的情况
                        if not memory:
                            memory = Memory(
                                id=memory_id,
                                user_id=user.id,
                                app_id=app.id,
                                content=result['memory'],
                                state=MemoryState.active
                            )
                            db.add(memory)
                        else:
                            # 如果记忆已存在，则更新状态和内容
                            memory.state = MemoryState.active
                            memory.content = result['memory']

                        # 创建历史记录条目
                        history = MemoryStatusHistory(
                            memory_id=memory_id,
                            changed_by=user.id,
                            old_state=MemoryState.deleted if memory else None,
                            new_state=MemoryState.active
                        )
                        db.add(history)

                    elif result['event'] == 'UPDATE':
                        # 处理更新现有记忆的情况
                        original_state_for_history = None
                        if memory: # 记忆在本地存在
                            original_state_for_history = memory.state
                            memory.content = result['memory']
                            memory.state = MemoryState.active
                            memory.updated_at = datetime.datetime.now(datetime.UTC)
                            logging.info(f"add_memories: Updated local memory ID {memory_id} based on UPDATE event.")
                        else: # 记忆在本地不存在 - 不一致状态
                            logging.warning(f"add_memories: Mem0 reported UPDATE for unknown memory ID: {memory_id}. Creating it locally.")
                            original_state_for_history = None # 实际上是新添加
                            memory = Memory(
                                id=memory_id,
                                user_id=user.id,
                                app_id=app.id,
                                content=result['memory'],
                                state=MemoryState.active
                            )
                            db.add(memory)

                        # 为更新或实际添加创建历史记录条目
                        history = MemoryStatusHistory(
                            memory_id=memory_id,
                            changed_by=user.id,
                            old_state=original_state_for_history, # 如果是实际添加则为None
                            new_state=MemoryState.active
                        )
                        db.add(history)

                    elif result['event'] == 'DELETE':
                        # 处理删除记忆的情况
                        if memory:
                            original_state_for_history = memory.state # 记录删除前的状态
                            memory.state = MemoryState.deleted
                            memory.deleted_at = datetime.datetime.now(datetime.UTC)
                            # 创建历史记录
                            history = MemoryStatusHistory(
                                memory_id=memory_id,
                                changed_by=user.id,
                                old_state=original_state_for_history, # 使用捕获的状态
                                new_state=MemoryState.deleted
                            )
                            db.add(history)
                        else:
                            logging.warning(f"add_memories: Mem0 reported DELETE for unknown memory ID: {memory_id}. No local action taken other than logging.")

                db.commit() # 处理完所有结果后提交一次

            # 返回格式化的字符串响应而非字典
            if isinstance(response, dict) and 'results' in response:
                result_count = len(response['results'])
                return f"Successfully processed {result_count} memory operation(s)"
            else:
                return "Memory added successfully"
        finally:
            db.close()
    except Exception as e:
        logging.exception(f"Error adding to memory: {e}")
        return f"Error adding to memory: {str(e)}"


@mcp.tool(description="Search through stored memories. This method is called EVERYTIME the user asks anything.")
async def search_memory(query: str) -> str:
    """搜索存储的记忆的工具函数
    
    Args:
        query: 搜索查询文本
        
    Returns:
        搜索结果的JSON字符串
    """
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    # 获取内存客户端，处理可能的初始化失败
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        db = SessionLocal()
        try:
            # 获取或创建用户和应用
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)
            logging.info(f"search_memory: user_id={uid}, client_name={client_name}, db_user_id={user.id}, app_id={app.id}")

            # 根据访问控制列表获取可访问的记忆ID
            user_memories = db.query(Memory).filter(Memory.user_id == user.id).all()
            logging.info(f"search_memory: Found {len(user_memories)} memories for user")
            accessible_memory_ids = [memory.id for memory in user_memories if check_memory_access_permissions(db, memory, app.id)]
            logging.info(f"search_memory: {len(accessible_memory_ids)} memories are accessible")
            
            # 构建Qdrant过滤条件
            # 注意：Qdrant中存储的user_id是User.id（UUID），不是User.user_id（字符串）
            conditions = [qdrant_models.FieldCondition(key="user_id", match=qdrant_models.MatchValue(value=str(user.id)))]
            logging.info(f"search_memory: Using user.id={user.id} for Qdrant filter")
            
            # 注意：不使用HasIdCondition进行权限过滤，因为：
            # 1. Qdrant中的ID与MySQL中的Memory.id不同（重建时生成的新ID）
            # 2. user_id过滤已经确保只返回该用户的记忆
            # 3. 权限检查将在返回结果后进行
            
            filters = qdrant_models.Filter(must=conditions)
            logging.info(f"search_memory: Using {len(conditions)} filter conditions (user_id only)")
            
            # 生成查询文本的嵌入向量
            logging.info(f"search_memory: Generating embeddings for query: {query}")
            embeddings = memory_client.embedding_model.embed(query, "search")
            logging.info(f"search_memory: Embeddings generated, length: {len(embeddings)}")
            
            # 在向量存储中执行相似性搜索
            logging.info(f"search_memory: Querying Qdrant with {len(conditions)} filter conditions")
            hits = memory_client.vector_store.client.query_points(
                collection_name=memory_client.vector_store.collection_name,
                query=embeddings,
                query_filter=filters,
                limit=10,
            )
            logging.info(f"search_memory: Qdrant query completed, got {len(hits.points)} points")

            # 处理搜索结果
            memories = hits.points
            logging.info(f"search_memory: Qdrant returned {len(memories)} results")
            memories = [
                {
                    "id": memory.id,
                    "memory": memory.payload["data"],
                    "hash": memory.payload.get("hash"),
                    "created_at": memory.payload.get("created_at"),
                    "updated_at": memory.payload.get("updated_at"),
                    "score": memory.score,
                }
                for memory in memories
            ]

            # Qdrant无结果时查MySQL兜底
            if not memories:
                logging.info(f"search_memory: No Qdrant results, trying MySQL fallback with query: {query}")
                
                # 将查询分词，支持多关键词搜索
                keywords = query.lower().split()
                from sqlalchemy import or_
                
                # 构建OR条件：任何一个关键词匹配都返回
                conditions = [Memory.content.ilike(f"%{keyword}%") for keyword in keywords if len(keyword) > 1]
                
                if conditions:
                    mysql_results = db.query(Memory).filter(
                        Memory.user_id == user.id,
                        or_(*conditions)
                    ).all()
                else:
                    # 如果没有有效关键词，使用原始查询
                    mysql_results = db.query(Memory).filter(
                        Memory.user_id == user.id,
                        Memory.content.ilike(f"%{query}%")
                    ).all()
                
                logging.info(f"search_memory: MySQL returned {len(mysql_results)} results")
                for memory in mysql_results:
                    # 检查权限
                    if memory.id in accessible_memory_ids:
                        memories.append({
                            "id": str(memory.id),
                            "memory": memory.content,
                            "hash": getattr(memory, "hash", None),
                            "created_at": memory.created_at.isoformat() if memory.created_at else None,
                            "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
                            "score": None,
                        })
                logging.info(f"search_memory: After permission filter, {len(memories)} memories accessible")

            # 为每个找到的记忆记录访问日志并更新last_accessed_at
            now = datetime.datetime.now(datetime.UTC)
            if isinstance(memories, dict) and 'results' in memories:
                print(f"Memories: {memories}")
                for memory_data in memories['results']:
                    if 'id' in memory_data:
                        memory_id = uuid.UUID(memory_data['id'])
                        
                        # 更新记忆的last_accessed_at字段
                        memory_obj = db.query(Memory).filter(Memory.id == memory_id).first()
                        if memory_obj:
                            memory_obj.last_accessed_at = now
                        
                        # 创建访问日志条目
                        access_log = MemoryAccessLog(
                            memory_id=memory_id,
                            app_id=app.id,
                            access_type="search",
                            metadata_={
                                "query": query,
                                "score": memory_data.get('score'),
                                "hash": memory_data.get('hash')
                            }
                        )
                        db.add(access_log)
                db.commit()
            else:
                logging.info(f"search_memory: Updating last_accessed_at for {len(memories)} memories")
                for memory in memories:
                    # Qdrant返回的是标准UUID格式（带连字符），需要转换为MySQL格式（无连字符）
                    qdrant_id = memory['id']
                    if isinstance(qdrant_id, str) and '-' in qdrant_id:
                        # 移除连字符以匹配MySQL中的格式
                        mysql_id = qdrant_id.replace('-', '')
                    else:
                        mysql_id = str(qdrant_id)
                    
                    logging.info(f"search_memory: Converting Qdrant ID {qdrant_id} to MySQL ID {mysql_id}")
                    
                    # 更新记忆的last_accessed_at和access_count字段
                    memory_obj = db.query(Memory).filter(Memory.id == mysql_id).first()
                    if memory_obj:
                        memory_obj.last_accessed_at = now
                        memory_obj.access_count = (memory_obj.access_count or 0) + 1
                        logging.info(f"search_memory: Updated last_accessed_at and access_count (now {memory_obj.access_count}) for memory {mysql_id}")
                    else:
                        logging.warning(f"search_memory: Memory {mysql_id} not found in database")
                    
                    # 创建访问日志条目（使用MySQL格式的ID）
                    access_log = MemoryAccessLog(
                        memory_id=mysql_id,
                        app_id=app.id,
                        access_type="search",
                        metadata_={
                            "query": query,
                            "score": memory.get('score'),
                            "hash": memory.get('hash')
                        }
                    )
                    db.add(access_log)
                db.commit()
                logging.info(f"search_memory: Committed {len(memories)} access logs and access_count updates")
            
            # 返回JSON格式的搜索结果
            return json.dumps(memories, indent=2, ensure_ascii=False)
        finally:
            db.close()
    except Exception as e:
        logging.exception(e)
        return f"Error searching memory: {e}"


@mcp.tool(description="List all memories in the user's memory")
async def list_memories() -> str:
    """列出用户所有记忆的工具函数
    
    Returns:
        用户可访问记忆列表的JSON字符串
    """
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    # 获取内存客户端，处理可能的初始化失败
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        db = SessionLocal()
        try:
            # 获取或创建用户和应用
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)

            # 获取所有记忆
            memories = memory_client.get_all(user_id=uid)
            filtered_memories = []

            # --- 详细日志用于调试 --- (已省略具体日志内容)
            # --- 结束详细日志 ---

            # 根据权限过滤记忆
            user_memories = db.query(Memory).filter(Memory.user_id == user.id).all()
            accessible_memory_ids = [memory.id for memory in user_memories if check_memory_access_permissions(db, memory, app.id)]

            # 处理不同格式的记忆数据
            if isinstance(memories, dict) and 'results' in memories:
                # 处理字典格式的响应
                if isinstance(memories['results'], list):
                    for memory_data_from_client in memories['results']:
                        if isinstance(memory_data_from_client, dict) and 'id' in memory_data_from_client:
                            memory_id_str = memory_data_from_client['id']
                            try:
                                memory_id = uuid.UUID(memory_id_str)
                                is_accessible = memory_id in accessible_memory_ids
                                
                                if is_accessible:
                                    # 创建访问日志条目
                                    access_log = MemoryAccessLog(
                                        memory_id=memory_id,
                                        app_id=app.id,
                                        access_type="list",
                                        metadata_={
                                            "hash": memory_data_from_client.get('hash')
                                        }
                                    )
                                    db.add(access_log)
                                    filtered_memories.append(memory_data_from_client)
                            except ValueError:
                                logging.warning(f"list_memories (dict format): Could not convert memory ID '{memory_id_str}' to UUID.")
                db.commit()
            elif isinstance(memories, list): # 旧版mem0格式或直接列表
                # 处理列表格式的响应
                for memory_data_from_client in memories:
                    if isinstance(memory_data_from_client, dict) and 'id' in memory_data_from_client:
                        memory_id_str = memory_data_from_client['id']
                        try:
                            memory_id = uuid.UUID(memory_id_str)
                            is_accessible = memory_id in accessible_memory_ids

                            if is_accessible:
                                # 更新记忆的last_accessed_at字段
                                memory_obj = db.query(Memory).filter(Memory.id == memory_id).first()
                                if memory_obj:
                                    memory_obj.last_accessed_at = datetime.datetime.now(datetime.UTC)
                                
                                # 创建访问日志条目
                                access_log = MemoryAccessLog(
                                    memory_id=memory_id,
                                    app_id=app.id,
                                    access_type="list",
                                    metadata_={
                                        "hash": memory_data_from_client.get('hash')
                                    }
                                )
                                db.add(access_log)
                                filtered_memories.append(memory_data_from_client)
                        except ValueError:
                            logging.warning(f"list_memories (list format): Could not convert memory ID '{memory_id_str}' to UUID.")
                db.commit()

            # 如果 Qdrant 没有数据，查 MySQL 兜底
            if not filtered_memories:
                for memory in user_memories:
                    filtered_memories.append({
                        "id": str(memory.id),
                        "memory": memory.content,
                        "hash": getattr(memory, "hash", None),
                        "created_at": memory.created_at.isoformat() if memory.created_at else None,
                        "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
                        "score": None,
                    })
                    
            # 返回JSON格式的记忆列表
            return json.dumps(filtered_memories, indent=2, ensure_ascii=False)
        finally:
            db.close()
    except Exception as e:
        logging.exception(f"Error getting memories: {e}")
        return f"Error getting memories: {e}"


@mcp.tool(description="Delete all memories in the user's memory")
async def delete_all_memories() -> str:
    """删除用户所有记忆的工具函数
    
    Returns:
        操作结果的字符串描述
    """
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    # 获取内存客户端，处理可能的初始化失败
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        db = SessionLocal()
        try:
            # 获取或创建用户和应用
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)

            # 获取用户可访问的记忆ID
            user_memories = db.query(Memory).filter(Memory.user_id == user.id).all()
            accessible_memory_ids = [memory.id for memory in user_memories if check_memory_access_permissions(db, memory, app.id)]

            # 仅删除可访问的记忆
            for memory_id in accessible_memory_ids:
                try:
                    # 从向量存储中删除
                    memory_client.delete(memory_id)
                except Exception as delete_error:
                    logging.warning(f"Failed to delete memory {memory_id} from vector store: {delete_error}")

            # 更新每个记忆的状态并创建历史记录条目
            now = datetime.datetime.now(datetime.UTC)
            for memory_id in accessible_memory_ids:
                memory = db.query(Memory).filter(Memory.id == memory_id).first()
                # 更新记忆状态
                memory.state = MemoryState.deleted
                memory.deleted_at = now

                # 创建历史记录条目
                history = MemoryStatusHistory(
                    memory_id=memory_id,
                    changed_by=user.id,
                    old_state=MemoryState.active,
                    new_state=MemoryState.deleted
                )
                db.add(history)

                # 创建访问日志条目
                access_log = MemoryAccessLog(
                    memory_id=memory_id,
                    app_id=app.id,
                    access_type="delete_all",
                    metadata_={"operation": "bulk_delete"}
                )
                db.add(access_log)

            db.commit()
            return "Successfully deleted all memories"
        finally:
            db.close()
    except Exception as e:
        logging.exception(f"Error deleting memories: {e}")
        return f"Error deleting memories: {e}"


@mcp_router.post("/messages/")
@mcp_router.post("/messages")
async def handle_sse_messages(request: Request):
    """处理SSE消息端点
    
    这个端点由FastMCP的SSE传输自动使用，用于接收客户端消息。
    """
    session_id = request.query_params.get("session_id")
    if not session_id:
        return {"error": "session_id required"}
    
    # 将请求传递给SSE传输处理
    return await sse.handle_post_message(request.scope, request.receive, request._send)


@mcp_router.get("/{client_name}/sse/{user_id}")
async def handle_sse(request: Request):
    """处理特定用户和客户端的SSE连接
    
    Args:
        request: FastAPI请求对象，包含路径参数中的user_id和client_name
    """
    # 从路径参数中提取user_id和client_name
    uid = request.path_params.get("user_id")
    user_token = user_id_var.set(uid or "")
    client_name = request.path_params.get("client_name")
    client_token = client_name_var.set(client_name or "")

    try:
        # 处理SSE连接
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            await mcp._mcp_server.run(
                read_stream,
                write_stream,
                mcp._mcp_server.create_initialization_options(),
            )
    finally:
        # 清理上下文变量
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)


def setup_mcp_server(app: FastAPI):
    """使用FastAPI应用设置MCP服务器
    
    Args:
        app: 要配置的FastAPI应用实例
    """
    mcp._mcp_server.name = f"mem0-mcp-server"

    # 在FastAPI应用中包含MCP路由器
    app.include_router(mcp_router)
