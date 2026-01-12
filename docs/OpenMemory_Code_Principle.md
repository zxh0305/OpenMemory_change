# OpenMemory 记忆系统代码原理深度解析

> **文档版本**: v1.0
> **更新日期**: 2025年1月
> **适用项目**: OpenMemory_change

---

## 目录

- [一、整体架构概览](#一整体架构概览)
- [二、数据模型详解](#二数据模型详解)
- [三、记忆存入流程详解](#三记忆存入流程详解)
- [四、记忆读取流程详解](#四记忆读取流程详解)
- [五、记忆衰退机制详解](#五记忆衰退机制详解)
- [六、多用户记忆实现详解](#六多用户记忆实现详解)
- [七、双数据库同步机制](#七双数据库同步机制)
- [八、总结](#八总结)

---

## 一、整体架构概览

### 1.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              客户端层                                        │
│    ┌─────────────────┐              ┌─────────────────────┐                │
│    │   REST API      │              │   MCP 协议 (SSE)    │                │
│    │ /api/v1/memories│              │ /mcp/{client}/sse   │                │
│    └────────┬────────┘              └──────────┬──────────┘                │
└─────────────┼──────────────────────────────────┼───────────────────────────┘
              │                                  │
              ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            业务逻辑层                                        │
│    ┌─────────────────────────────────────────────────────────────────┐     │
│    │                    Mem0 Memory Client                           │     │
│    │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │     │
│    │  │  LLM (大模型) │  │  Embedder    │  │  Vector Store      │   │     │
│    │  │  事实提取     │  │  向量生成     │  │  (Qdrant Client)  │   │     │
│    │  └──────────────┘  └──────────────┘  └────────────────────┘   │     │
│    └─────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
              │                                  │
              ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            数据存储层                                        │
│    ┌─────────────────────────┐        ┌─────────────────────────┐          │
│    │       Qdrant            │        │     MySQL/SQLite        │          │
│    │   (向量数据库)           │        │    (关系数据库)         │          │
│    │                         │        │                         │          │
│    │  • embedding 向量        │        │  • 完整记忆记录          │          │
│    │  • 语义搜索              │        │  • 用户/应用/分类        │          │
│    │  • user_id 过滤         │        │  • 衰退分数/访问统计     │          │
│    │  • payload 数据          │        │  • 状态历史/访问日志     │          │
│    └─────────────────────────┘        └─────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 技术栈

| 组件 | 技术选型 | 用途 |
|------|---------|------|
| Web框架 | FastAPI | REST API 和 MCP 服务 |
| ORM | SQLAlchemy | 数据库操作 |
| 向量数据库 | Qdrant | 语义搜索 |
| 关系数据库 | MySQL/SQLite | 数据管理 |
| 记忆框架 | Mem0 | LLM + Embedding + 向量存储 |
| LLM | OpenAI/Ollama | 事实提取 |
| Embedding | OpenAI | 向量生成 |

---

## 二、数据模型详解

### 2.1 核心实体关系图

```
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│     User      │ 1    N  │     App       │ 1    N  │    Memory     │
│───────────────│────────▶│───────────────│────────▶│───────────────│
│ id (UUID)     │         │ id (UUID)     │         │ id (UUID)     │
│ user_id (str) │         │ owner_id (FK) │         │ user_id (FK)  │
│ name          │         │ name          │         │ app_id (FK)   │
│ email         │         │ is_active     │         │ content       │
│ metadata_     │         │ description   │         │ state         │
└───────────────┘         └───────────────┘         │ decay_score   │
                                                    │ access_count  │
                                                    │ importance    │
                                                    └───────────────┘
                                                            │
                                                            │ N:M
                                                            ▼
                                                    ┌───────────────┐
                                                    │   Category    │
                                                    │───────────────│
                                                    │ id (UUID)     │
                                                    │ name          │
                                                    │ description   │
                                                    └───────────────┘
```

### 2.2 Memory 模型核心字段

**文件位置**: `api/app/models.py`

```python
class Memory(Base):
    __tablename__ = "memories"

    # === 基础标识 ===
    id = Column(String(32), primary_key=True)      # UUID，无连字符
    user_id = Column(String(32), ForeignKey("users.id"))  # 关联用户
    app_id = Column(String(32), ForeignKey("apps.id"))    # 关联应用

    # === 记忆内容 ===
    content = Column(Text, nullable=False)         # 记忆文本内容
    vector = Column(Text)                          # 可选的向量存储
    metadata_ = Column(JSON, default=dict)         # 元数据（来源等）

    # === 状态管理 ===
    state = Column(Enum(MemoryState))              # active/paused/archived/deleted
    created_at = Column(DateTime)                  # 创建时间
    updated_at = Column(DateTime)                  # 更新时间
    archived_at = Column(DateTime)                 # 归档时间
    deleted_at = Column(DateTime)                  # 删除时间

    # === 衰退机制相关 ===
    decay_score = Column(Float, default=1.0)       # 衰退分数 (0-1)
    last_accessed_at = Column(DateTime)            # 最后访问时间
    access_count = Column(Integer, default=0)      # 访问次数
    importance_score = Column(Float, default=0.5)  # 重要性分数 (0-1)
```

### 2.3 记忆状态枚举

```python
class MemoryState(enum.Enum):
    active = "active"       # 活跃状态，可正常访问
    paused = "paused"       # 暂停状态，暂时不可访问
    archived = "archived"   # 归档状态，衰退后自动归档
    deleted = "deleted"     # 删除状态，软删除
```

### 2.4 辅助数据表

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| `users` | 用户管理 | id, user_id, name, email |
| `apps` | 应用管理 | id, owner_id, name, is_active |
| `categories` | 分类管理 | id, name, description |
| `memory_categories` | 记忆-分类关联 | memory_id, category_id |
| `archived_memories` | 归档记忆存储 | 完整记忆字段 + 归档快照 |
| `memory_status_history` | 状态变更历史 | memory_id, old_state, new_state |
| `memory_access_logs` | 访问日志 | memory_id, app_id, access_type |
| `access_controls` | 访问控制 | subject_type, object_type, effect |

---

## 三、记忆存入流程详解

### 3.1 存入流程图

```
用户输入文本
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤1: 身份验证和准备                                            │
│                                                                 │
│   get_or_create_user(db, user_id)  ──▶ 获取或创建用户           │
│   get_or_create_app(db, user, app)  ──▶ 获取或创建应用          │
│   检查 app.is_active                ──▶ 应用是否被暂停          │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤2: 调用 Mem0 Memory Client 处理                              │
│                                                                 │
│   memory_client.add(text, user_id, metadata)                    │
│                     │                                           │
│                     ▼                                           │
│         ┌─────────────────────────────┐                        │
│         │   LLM 大模型处理             │                        │
│         │   • 从文本中提取事实         │                        │
│         │   • 判断是 ADD/UPDATE/DELETE │                        │
│         │   • 返回结构化记忆           │                        │
│         └─────────────────────────────┘                        │
│                     │                                           │
│                     ▼                                           │
│         ┌─────────────────────────────┐                        │
│         │   Embedder 向量生成          │                        │
│         │   • 将文本转为 1536 维向量   │                        │
│         │   • 使用 OpenAI embedding   │                        │
│         └─────────────────────────────┘                        │
│                     │                                           │
│                     ▼                                           │
│         ┌─────────────────────────────┐                        │
│         │   Qdrant 向量存储            │                        │
│         │   • 存储 embedding + payload │                        │
│         │   • 返回生成的 UUID          │                        │
│         └─────────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
    │
    │  返回: { results: [{ id, memory, event: "ADD/UPDATE" }] }
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤3: 同步到 MySQL 数据库                                       │
│                                                                 │
│   for result in response['results']:                            │
│       if event == 'ADD':                                        │
│           创建新的 Memory 记录（使用 Qdrant 返回的相同 ID）       │
│       elif event == 'UPDATE':                                   │
│           更新已存在的 Memory 记录                               │
│       elif event == 'DELETE':                                   │
│           标记 Memory 为 deleted 状态                            │
│                                                                 │
│   创建 MemoryStatusHistory 记录状态变更                          │
│   db.commit()                                                   │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤4: 自动分类（SQLAlchemy 事件触发器）                         │
│                                                                 │
│   @event.listens_for(Memory, "after_insert")                    │
│   def after_memory_insert(mapper, connection, target):          │
│       categorize_memory(target, db)                             │
│                                                                 │
│   categorize_memory():                                          │
│       categories = get_categories_for_memory(content)  # 用LLM  │
│       for category in categories:                               │
│           关联 memory 和 category                               │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 关键代码解析

**文件位置**: `api/app/routers/memories.py`

```python
@router.post("/")
async def create_memory(request: CreateMemoryRequest, db: Session = Depends(get_db)):
    # 1. 获取或创建用户
    user = get_or_create_user(db, request.user_id)

    # 2. 获取或创建应用
    app_obj = db.query(App).filter(App.name == request.app, App.owner_id == user.id).first()
    if not app_obj:
        app_obj = App(name=request.app, owner_id=user.id)
        db.add(app_obj)
        db.commit()

    # 3. 检查应用状态
    if not app_obj.is_active:
        raise HTTPException(status_code=403, detail="App is paused")

    # 4. 调用 Mem0 客户端
    memory_client = get_memory_client()
    qdrant_response = memory_client.add(
        request.text,
        user_id=request.user_id,
        metadata={
            "source_app": "openmemory",
            "mcp_client": request.app,
        }
    )

    # 5. 处理响应，同步到 MySQL
    for result in qdrant_response['results']:
        if result['event'] in ['ADD', 'UPDATE']:
            memory_id = UUID(result['id'])  # 使用 Qdrant 生成的 ID
            memory = Memory(
                id=memory_id,                           # 关键：ID 一致
                user_id=user.id,
                app_id=app_obj.id,
                content=result.get('memory'),           # LLM 提取的事实
                state=MemoryState.active
            )
            db.add(memory)

    db.commit()
    return memory
```

### 3.3 Mem0 客户端配置

**文件位置**: `api/app/utils/memory.py`

```python
def get_default_memory_config():
    return {
        # 向量存储配置 - Qdrant
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "openmemory",
                "host": "mem0_store",           # Docker 服务名
                "port": 6333,
                "embedding_model_dims": 1536,   # OpenAI 默认维度
            },
        },
        # LLM 配置 - 用于事实提取
        "llm": {
            "provider": "openai",               # 或 ollama/deepseek
            "config": {
                "model": "gpt-4o-mini",
                "temperature": 0.1,             # 低温度保证稳定性
                "max_tokens": 2000,
            },
        },
        # Embedder 配置 - 用于向量生成
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "text-embedding-3-small",
                "embedding_dims": 1536,
            },
        },
    }
```

### 3.4 故障转移机制

当 Mem0 客户端或 Qdrant 不可用时，系统会自动降级到仅 MySQL 模式：

```python
try:
    memory_client = get_memory_client()
    if not memory_client:
        raise Exception("Memory client is not available")
except Exception as client_error:
    logging.warning(f"Memory client unavailable: {client_error}")

    # 直接写入 MySQL 数据库，不依赖 Qdrant 和 LLM
    memory = Memory(
        id=uuid4(),  # 本地生成 UUID
        user_id=user.id,
        app_id=app_obj.id,
        content=request.text,  # 原始文本，未经 LLM 处理
        state=MemoryState.active
    )
    db.add(memory)
    db.commit()
```

---

## 四、记忆读取流程详解

### 4.1 搜索流程图

```
用户输入查询
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤1: 身份验证                                                  │
│   get_user_and_app(db, user_id, client_name)                    │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤2: 获取权限范围                                              │
│                                                                 │
│   user_memories = db.query(Memory).filter(user_id == user.id)   │
│   accessible_ids = [m.id for m in user_memories                 │
│                     if check_memory_access_permissions(m, app)] │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤3: 向量搜索 (Qdrant)                                         │
│                                                                 │
│   # 3.1 生成查询向量                                            │
│   embeddings = memory_client.embedding_model.embed(query)       │
│                                                                 │
│   # 3.2 构建过滤条件（只过滤 user_id）                           │
│   conditions = [FieldCondition(key="user_id", match=user.id)]   │
│   filters = Filter(must=conditions)                             │
│                                                                 │
│   # 3.3 执行向量相似度搜索                                       │
│   hits = memory_client.vector_store.client.query_points(        │
│       collection_name="openmemory",                             │
│       query=embeddings,                                         │
│       query_filter=filters,                                     │
│       limit=10,                                                 │
│   )                                                             │
└─────────────────────────────────────────────────────────────────┘
    │
    │  ┌─────────────────────────────────────┐
    │  │ 如果 Qdrant 无结果，MySQL 兜底       │
    │  │                                     │
    │  │ keywords = query.split()            │
    │  │ conditions = [ilike(f"%{kw}%")]     │
    │  │ mysql_results = db.query(Memory)    │
    │  │     .filter(or_(*conditions)).all() │
    │  └─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤4: 更新访问统计                                              │
│                                                                 │
│   for memory in results:                                        │
│       memory.last_accessed_at = now                             │
│       memory.access_count += 1                                  │
│                                                                 │
│       access_log = MemoryAccessLog(                             │
│           memory_id=memory.id,                                  │
│           app_id=app.id,                                        │
│           access_type="search",                                 │
│           metadata_={"query": query, "score": score}            │
│       )                                                         │
│       db.add(access_log)                                        │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
返回搜索结果（按相似度排序）
```

### 4.2 权限检查逻辑

**文件位置**: `api/app/utils/permissions.py`

```python
def check_memory_access_permissions(db: Session, memory: Memory, app_id: UUID) -> bool:
    """
    权限检查的三层验证：
    1. 记忆状态必须是 active
    2. 应用必须存在且处于活跃状态
    3. 通过 AccessControl 表的细粒度控制
    """

    # 第一层：检查记忆状态
    if memory.state != MemoryState.active:
        return False

    # 第二层：检查应用状态
    app = db.query(App).filter(App.id == app_id).first()
    if not app or not app.is_active:
        return False

    # 第三层：检查 ACL 访问控制
    accessible_memory_ids = get_accessible_memory_ids(db, app_id)

    # None 表示没有限制，所有记忆都可访问
    if accessible_memory_ids is None:
        return True

    # 检查是否在允许列表中
    return memory.id in accessible_memory_ids
```

### 4.3 ID 格式转换

Qdrant 和 MySQL 的 ID 格式不同，需要转换：

```python
# Qdrant: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" (带连字符)
# MySQL:  "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"     (无连字符)

# 转换逻辑：
qdrant_id = memory['id']
if isinstance(qdrant_id, str) and '-' in qdrant_id:
    mysql_id = qdrant_id.replace('-', '')  # 移除连字符
else:
    mysql_id = str(qdrant_id)

# 用 mysql_id 查询数据库
memory_obj = db.query(Memory).filter(Memory.id == mysql_id).first()
```

---

## 五、记忆衰退机制详解

### 5.1 衰退算法公式

```
最终衰退分数 = 时间衰减 × 访问加成 × 重要性权重
```

#### 5.1.1 时间衰减（指数衰减）

```
time_decay = 0.5^(days_since_access / half_life)
```

| 天数 | 衰退分数 | 说明 |
|------|---------|------|
| 0天 | 1.0 | 完全新鲜 |
| 30天 | 0.5 | 衰减一半（半衰期） |
| 60天 | 0.25 | 衰减3/4 |
| 90天 | 0.125 | 衰减7/8 |

#### 5.1.2 访问加成（对数增长）

```
access_boost = 1.0 + log(1 + access_count) × 0.2
最大值限制为 2.0
```

| 访问次数 | 加成系数 |
|---------|---------|
| 0次 | 1.0 |
| 10次 | 1.48 |
| 50次 | 1.78 |
| 100次 | 1.92 |

#### 5.1.3 重要性权重

```
importance_weight = 0.5 + (importance_score × 0.5)
```

| 重要性分数 | 权重 | 效果 |
|-----------|------|------|
| 0.0 | 0.5 | 加速衰退 |
| 0.5 | 0.75 | 正常衰退 |
| 1.0 | 1.0 | 减缓衰退 |

### 5.2 衰退计算代码

**文件位置**: `api/app/utils/decay.py`

```python
def calculate_decay_score(
    created_at: datetime,
    last_accessed_at: Optional[datetime],
    access_count: int,
    importance_score: float = 0.5,
    half_life_days: int = 30
) -> float:
    """计算综合衰退分数"""

    now = datetime.now(UTC)

    # 计算距离上次访问的天数
    if last_accessed_at:
        days_since_access = (now - last_accessed_at).days
    else:
        days_since_access = (now - created_at).days  # 从未访问过

    # 1. 基础时间衰减（指数衰减）
    time_decay = math.pow(0.5, days_since_access / half_life_days)

    # 2. 访问频率加成（对数增长）
    access_boost = 1.0 + math.log(1 + access_count) * 0.2
    access_boost = min(access_boost, 2.0)  # 限制最大值

    # 3. 重要性权重
    importance_weight = 0.5 + (importance_score * 0.5)

    # 综合计算
    final_score = time_decay * access_boost * importance_weight

    # 确保在 0-1 范围内
    return max(0.0, min(1.0, final_score))
```

### 5.3 自动归档流程

```
┌─────────────────────────────────────────────────────────────────┐
│                      定时任务触发                                │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤1: 批量更新衰退分数                                          │
│                                                                 │
│   update_memory_decay_scores(db, batch_size=100, half_life=30)  │
│                                                                 │
│   for memory in active_memories:                                │
│       new_score = calculate_decay_score(...)                    │
│       memory.decay_score = new_score                            │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤2: 自动归档低分记忆                                          │
│                                                                 │
│   auto_archive_decayed_memories(db, threshold=0.1)              │
│                                                                 │
│   memories_to_archive = Memory.query.filter(                    │
│       state == active,                                          │
│       decay_score < 0.1    # 阈值                               │
│   )                                                             │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 步骤3: 移动到归档表                                              │
│                                                                 │
│   1. 保存分类快照                                               │
│   2. 创建 ArchivedMemory 记录                                   │
│   3. 删除原 Memory 记录                                         │
│   4. 记录状态变更历史                                            │
└─────────────────────────────────────────────────────────────────┘
```

### 5.4 归档和恢复代码

**文件位置**: `api/app/utils/decay_with_archive_table.py`

```python
def move_memory_to_archive(db: Session, memory: Memory) -> ArchivedMemory:
    """将记忆从 memories 表移动到 archived_memories 表"""

    # 1. 保存分类快照
    categories = [cat.name for cat in memory.categories]

    # 2. 创建归档记录
    archived = ArchivedMemory(
        id=memory.id,  # 保持 ID 不变
        content=memory.content,
        user_id=memory.user_id,
        app_id=memory.app_id,
        decay_score_at_archive=memory.decay_score,
        categories_snapshot=categories,
        archived_at=datetime.now(UTC),
    )
    db.add(archived)

    # 3. 记录状态变更
    history = MemoryStatusHistory(
        memory_id=memory.id,
        old_state=memory.state,
        new_state=MemoryState.archived,
    )
    db.add(history)

    # 4. 删除原记忆
    db.delete(memory)

    return archived


def restore_archived_memory(db: Session, memory_id: str, user_id: str) -> bool:
    """从归档表恢复记忆"""

    archived = db.query(ArchivedMemory).filter(
        ArchivedMemory.id == memory_id,
        ArchivedMemory.user_id == user_id
    ).first()

    if not archived:
        return False

    # 创建新的活跃记忆（重置衰退相关字段）
    memory = Memory(
        id=archived.id,
        content=archived.content,
        state=MemoryState.active,
        decay_score=1.0,        # 重置
        access_count=0,         # 重置
        last_accessed_at=None,  # 重置
    )
    db.add(memory)

    # 恢复分类关联
    for cat_name in archived.categories_snapshot:
        category = db.query(Category).filter(Category.name == cat_name).first()
        if category:
            memory.categories.append(category)

    # 删除归档记录
    db.delete(archived)

    db.commit()
    return True
```

---

## 六、多用户记忆实现详解

### 6.1 多用户数据隔离架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        数据隔离层级                              │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                     用户级隔离                             │ │
│  │                                                           │ │
│  │   User A (id="user_001")         User B (id="user_002")   │ │
│  │   ├── App: cursor               ├── App: cursor          │ │
│  │   │   ├── Memory 1              │   ├── Memory 5         │ │
│  │   │   └── Memory 2              │   └── Memory 6         │ │
│  │   └── App: claude               └── App: vscode          │ │
│  │       └── Memory 3                  └── Memory 7         │ │
│  │                                                           │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                     应用级隔离                             │ │
│  │                                                           │ │
│  │   同一用户的不同应用可以有独立的记忆                         │ │
│  │   App.is_active 可以单独控制某个应用的访问                  │ │
│  │                                                           │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                     记忆级隔离                             │ │
│  │                                                           │ │
│  │   AccessControl 表支持细粒度权限控制：                      │ │
│  │   • allow/deny 特定记忆给特定应用                          │ │
│  │   • 支持应用级别的全部允许/拒绝                            │ │
│  │                                                           │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 用户识别的两种方式

#### 方式1: REST API

```python
# 每次请求通过参数传递 user_id

@router.post("/")
async def create_memory(request: CreateMemoryRequest, db: Session):
    # 从请求体获取 user_id
    user_id = request.user_id  # 例如: "john_doe"

    # 获取或创建用户（自动创建新用户）
    user = get_or_create_user(db, user_id)
    # user.id = "abc123..."  (系统生成的 UUID)
    # user.user_id = "john_doe"  (用户提供的标识)
```

#### 方式2: MCP 协议

```python
# 通过 SSE 连接路径和 ContextVar 存储

# SSE 连接 URL: /mcp/{client_name}/sse/{user_id}
# 例如: /mcp/cursor/sse/john_doe

# Context Variables 存储用户信息
user_id_var: ContextVar[str] = ContextVar("user_id")
client_name_var: ContextVar[str] = ContextVar("client_name")

@mcp_router.get("/{client_name}/sse/{user_id}")
async def handle_sse(request: Request):
    # 从路径提取并存储
    uid = request.path_params.get("user_id")
    user_id_var.set(uid)

    client_name = request.path_params.get("client_name")
    client_name_var.set(client_name)
```

### 6.3 Qdrant 中的用户过滤

```python
# Qdrant 中的数据结构
{
    "id": "uuid-xxxx",
    "vector": [0.1, 0.2, ...],  # 1536 维向量
    "payload": {
        "data": "记忆内容文本",
        "user_id": "abc123...",      # User.id (UUID)，用于过滤
        "hash": "内容哈希",
        "created_at": "时间戳",
        "source_app": "openmemory",
        "mcp_client": "cursor",
    }
}

# 搜索时的用户过滤
async def search_memory(query: str):
    # 构建过滤条件：只返回当前用户的记忆
    conditions = [
        qdrant_models.FieldCondition(
            key="user_id",
            match=qdrant_models.MatchValue(value=str(user.id))
        )
    ]

    filters = qdrant_models.Filter(must=conditions)

    # 执行搜索
    hits = memory_client.vector_store.client.query_points(
        collection_name="openmemory",
        query=embeddings,
        query_filter=filters,  # 关键：用户过滤
        limit=10,
    )
```

### 6.4 自动创建用户和应用

**文件位置**: `api/app/utils/db.py`

```python
def get_or_create_user(db: Session, user_id: str) -> User:
    """获取或创建用户 - 自动注册"""
    user = db.query(User).filter(User.user_id == user_id).first()

    if not user:
        # 自动创建新用户
        user = User(user_id=user_id)  # id 自动生成 UUID
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


def get_or_create_app(db: Session, user: User, app_id: str) -> App:
    """获取或创建应用 - 每个用户独立"""
    # 查询：属于该用户的、名称匹配的应用
    app = db.query(App).filter(
        App.owner_id == user.id,
        App.name == app_id
    ).first()

    if not app:
        # 自动创建新应用
        app = App(owner_id=user.id, name=app_id)
        db.add(app)
        db.commit()
        db.refresh(app)

    return app


def get_user_and_app(db: Session, user_id: str, app_id: str):
    """一次性获取用户和应用"""
    user = get_or_create_user(db, user_id)
    app = get_or_create_app(db, user, app_id)
    return user, app
```

---

## 七、双数据库同步机制

### 7.1 数据分布对比

| 维度 | Qdrant (向量数据库) | MySQL/SQLite (关系数据库) |
|------|-------------------|-------------------------|
| **存储内容** | embedding向量, payload数据 | 完整记录, 关系数据 |
| **主要用途** | 语义相似度搜索 | 数据管理, CRUD |
| **查询方式** | 向量相似度 + 字段过滤 | SQL 条件查询 |
| **事务支持** | 无 | 完整 ACID |
| **故障处理** | 可降级到 MySQL | 主存储，无降级 |

### 7.2 Qdrant 存储结构

```json
{
    "id": "uuid-xxxx",
    "vector": [0.1, 0.2, ..., 0.5],  // 1536 维
    "payload": {
        "data": "记忆内容文本",
        "user_id": "abc123...",
        "hash": "内容哈希值",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "source_app": "openmemory",
        "mcp_client": "cursor"
    }
}
```

### 7.3 ID 一致性保证

```python
# 创建记忆时，确保 Qdrant 和 MySQL 使用相同的 ID

# 1. Mem0 客户端在 Qdrant 中创建记忆并返回 ID
qdrant_response = memory_client.add(text, user_id=user_id, ...)
# 返回: { "results": [{ "id": "uuid-xxxx", "memory": "...", "event": "ADD" }] }

# 2. 使用 Qdrant 返回的 ID 创建 MySQL 记录
for result in qdrant_response['results']:
    memory_id = UUID(result['id'])  # 使用 Qdrant 生成的 ID

    memory = Memory(
        id=memory_id,  # 关键：使用相同的 ID
        user_id=user.id,
        content=result['memory'],
    )
    db.add(memory)
```

### 7.4 MySQL 故障转移搜索

```python
# 当 Qdrant 无结果时，使用 MySQL 兜底

if not memories:
    logging.info("No Qdrant results, trying MySQL fallback")

    # 分词搜索
    keywords = query.lower().split()
    conditions = [Memory.content.ilike(f"%{kw}%") for kw in keywords]

    mysql_results = db.query(Memory).filter(
        Memory.user_id == user.id,
        or_(*conditions)  # 任意关键词匹配
    ).all()

    # 转换为统一格式
    for memory in mysql_results:
        memories.append({
            "id": str(memory.id),
            "memory": memory.content,
            "score": None,  # MySQL 不提供相似度分数
        })
```

---

## 八、总结

### 8.1 核心设计理念

| 设计点 | 实现方式 | 优势 |
|--------|---------|------|
| **双数据库** | Qdrant + MySQL | 语义搜索 + 完整管理 |
| **自动提取** | LLM 事实提取 | 从对话中提取有价值信息 |
| **记忆衰退** | 时间×访问×重要性 | 模拟人类记忆特点 |
| **多用户隔离** | user_id 全链路过滤 | 数据安全隔离 |
| **故障转移** | MySQL 兜底搜索 | 高可用性 |
| **状态追踪** | 历史表 + 日志表 | 完整审计能力 |

### 8.2 数据流总结

```
用户输入 "我喜欢蓝色"
    │
    ▼
LLM 提取事实: "用户喜欢蓝色"
    │
    ▼
Embedder 生成向量: [0.1, 0.2, ..., 0.5] (1536维)
    │
    ├──▶ Qdrant: 存储向量 + payload
    │
    └──▶ MySQL: 存储完整记录 + 衰退字段
    │
    ▼
自动分类: ["偏好", "颜色"]
    │
    ▼
随时间衰退: decay_score 从 1.0 逐渐下降
    │
    ▼
当 decay_score < 0.1 时自动归档到 ArchivedMemory
```

### 8.3 关键代码文件索引

| 文件 | 功能 |
|------|------|
| `api/app/models.py` | 数据模型定义 |
| `api/app/utils/memory.py` | Mem0 客户端配置 |
| `api/app/routers/memories.py` | REST API 路由 |
| `api/app/mcp_server.py` | MCP 协议服务 |
| `api/app/utils/decay.py` | 衰退算法 |
| `api/app/utils/decay_with_archive_table.py` | 归档表实现 |
| `api/app/utils/db.py` | 用户/应用管理 |
| `api/app/utils/permissions.py` | 权限检查 |
| `api/app/database.py` | 数据库连接 |

### 8.4 设计亮点

1. **仿生记忆**: 模拟人类记忆特点 - 可存储、可遗忘、常用的记得更牢、重要的不易忘记
2. **双存储架构**: Qdrant 负责快速语义搜索，MySQL 负责完整数据管理和业务逻辑
3. **自动降级**: 当向量数据库不可用时，自动降级到关系数据库搜索
4. **完整审计**: 状态变更历史和访问日志支持完整的数据追溯
5. **细粒度权限**: 支持用户级、应用级、记忆级的访问控制

---

## 附录 A: API 接口列表

### 记忆管理

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/v1/memories/` | 创建记忆 |
| GET | `/api/v1/memories/` | 列出记忆 |
| GET | `/api/v1/memories/{id}` | 获取记忆详情 |
| PUT | `/api/v1/memories/{id}` | 更新记忆 |
| DELETE | `/api/v1/memories/` | 批量删除记忆 |
| POST | `/api/v1/memories/filter` | 高级过滤查询 |
| POST | `/api/v1/memories/actions/pause` | 暂停记忆 |
| POST | `/api/v1/memories/actions/archive` | 归档记忆 |

### MCP 协议

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/mcp/{client}/sse/{user_id}` | SSE 连接 |
| POST | `/mcp/messages/` | 消息处理 |

### MCP 工具

| 工具名 | 功能 |
|--------|------|
| `add_memories` | 添加记忆 |
| `search_memory` | 搜索记忆 |
| `list_memories` | 列出所有记忆 |
| `delete_all_memories` | 删除所有记忆 |

---

## 附录 B: 环境变量配置

```bash
# 数据库
DATABASE_URL=mysql://user:pass@host:3306/openmemory

# OpenAI 配置
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# Embedding 配置
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_MODEL_DIMS=1536
OPENAI_EMBEDDING_MODEL_API_KEY=sk-xxx
OPENAI_EMBEDDING_MODEL_BASE_URL=https://api.openai.com/v1

# Qdrant 配置 (Docker)
QDRANT_HOST=mem0_store
QDRANT_PORT=6333
```

---

*文档结束*
